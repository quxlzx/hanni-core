"""Owner-scoped CPU sandbox jobs; model lifecycle stays in Control Center.

Configuration is private deployment state, never inferred from a model plan.
Submission crosses the original tool registry and has no automatic write retry.
"""
from copy import deepcopy
import hashlib
import ipaddress
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import subprocess
import threading
import secrets
import time
from urllib.parse import urlsplit

def canonical_json(value, *, maximum):
    encoded=json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)
    if len(encoded.encode())>maximum:
        raise ValueError('Sandbox payload exceeds its bounded size.')
    return encoded

ROLES = {'manager': ('wonyoung-strata', 'planning', 'LangGraph'),
         'coder': ('hanni-swift', 'coding', 'OpenCode'),
         'editor': ('athena-p40', 'coding', 'Aider'),
         'researcher': ('athena-p6000', 'analysis', 'GPT Researcher')}
TASK_FIELDS = {'task_id', 'project_id', 'goal', 'roles', 'files', 'checks'}


def digest(value):
    return hashlib.sha256(canonical_json(value, maximum=262144).encode()).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', value):
        raise ValueError('Choose a bounded lowercase deployment/task identifier.')
    return value


def validate_task(task):
    if not isinstance(task, dict) or not TASK_FIELDS<=set(task) or set(task)-TASK_FIELDS-{'check_files'}:
        raise ValueError('Task requires task_id, goal, roles, files and owner-selected checks.')
    identifier(task['task_id'])
    identifier(task['project_id'])
    if not isinstance(task['goal'], str) or not 1 <= len(task['goal']) <= 4000:
        raise ValueError('Task goal is empty or too large.')
    roles = task['roles']
    if not isinstance(roles, list) or not roles or len(roles) > 4 or len(set(roles)) != len(roles) or any(r not in ROLES for r in roles):
        raise ValueError('Choose one to four fixed specialist roles; Qwen 9B is excluded.')
    files = task['files']
    if not isinstance(files, dict) or len(files) > 64:
        raise ValueError('Provide at most 64 explicit source snapshots, not host paths.')
    for name, content in files.items():
        path = PurePosixPath(name)
        if (not isinstance(name, str) or not name or len(name) > 200 or path.is_absolute()
                or any(p in {'', '.', '..'} or p.startswith('.') for p in name.split('/'))
                or '\\' in name or ':' in name or not isinstance(content, str)):
            raise ValueError('Snapshot files must have safe relative names and textual contents.')
        if any(p in {'node_modules', 'venv', '__pycache__'} for p in path.parts):
            raise ValueError('Dependency directories are not source snapshots.')
    checks = task['checks']
    if not isinstance(checks, list) or not 1 <= len(checks) <= 8:
        raise ValueError('At least one explicit independent check is required.')
    for command in checks:
        if (not isinstance(command, list) or not command or len(command) > 16
                or command[0] not in {'python', 'pytest', 'npm'}
                or any(not isinstance(arg, str) or len(arg) > 512 or '\x00' in arg for arg in command)):
            raise ValueError('Checks require bounded argv lists with approved test runners.')
    check_files=task.get('check_files',[])
    if (not isinstance(check_files,list) or len(check_files)>16
            or any(not isinstance(name,str) or name not in files for name in check_files)
            or len(check_files)!=len(set(check_files))):
        raise ValueError('Independent check files must name exact approved snapshot files.')
    if set(roles)&{'coder','editor'} and not check_files:
        raise ValueError('Coding tasks require explicit immutable owner check files.')
    canonical_json(task, maximum=131072)
    # Source credentials are never placed in ConfigMaps or model context.
    from hanni.memory.privacy import validate_memory_text
    validate_memory_text(json.dumps(task), max_chars=131072)
    return deepcopy(task)


def validate_deployment(value):
    fields = {'version', 'enabled', 'context', 'namespace', 'image', 'runtime_class',
              'node_selector', 'gateway_url', 'models', 'deadline_seconds',
              'storage_claim', 'authorized_projects'}
    if not isinstance(value, dict) or set(value) != fields or value['version'] != 1 or type(value['enabled']) is not bool:
        raise ValueError('Invalid sandbox deployment contract.')
    for key in ('context', 'namespace', 'runtime_class', 'storage_claim'):
        identifier(value[key])
    if value['runtime_class'] not in {'gvisor', 'kata'}:
        raise ValueError('A verified gVisor or Kata runtime is required.')
    if not isinstance(value['image'], str) or not re.fullmatch(r'[a-zA-Z0-9./:_-]+@sha256:[a-f0-9]{64}', value['image']):
        raise ValueError('Sandbox image must be pinned by digest.')
    if value['node_selector'] != {'hanni.ai/worker-class':'cpu','hanni.ai/sandbox-enabled':'true'}:
        raise ValueError('Both explicit CPU-worker and sandbox-enabled labels are required.')
    projects=value['authorized_projects']
    if not isinstance(projects,list) or not projects or len(projects)>16:
        raise ValueError('One to sixteen specific owner-authorized project IDs are required.')
    for project in projects:identifier(project)
    parts = urlsplit(value['gateway_url'])
    try:
        address = ipaddress.ip_address(parts.hostname)
    except (ValueError, TypeError):
        raise ValueError('Gateway must use an existing literal private address.') from None
    if (parts.scheme not in {'http', 'https'} or not (address.is_private or address in ipaddress.ip_network('100.64.0.0/10'))
            or address.is_loopback or address.is_unspecified or address.is_multicast
            or parts.username or parts.password or parts.query or parts.fragment or parts.path != '/api/sandbox/v1' or not parts.port):
        raise ValueError('Gateway requires an existing private authenticated /v1 endpoint.')
    if value['enabled'] and (value['image'].endswith('0'*64)
            or address.is_reserved or address in ipaddress.ip_network('192.0.2.0/24')):
        raise ValueError('Example image/gateway placeholders cannot enable live deployment.')
    if not isinstance(value['models'], dict) or set(value['models']) != set(ROLES):
        raise ValueError('All four model aliases require explicit registered identities.')
    for model in value['models'].values():
        if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', model):
            raise ValueError('Invalid registered model alias.')
    if type(value['deadline_seconds']) is not int or not 30 <= value['deadline_seconds'] <= 900:
        raise ValueError('Sandbox duration must be between 30 and 900 seconds.')
    return deepcopy(value)


def manifests(deployment, task):
    deployment, task = validate_deployment(deployment), validate_task(task)
    if task['project_id'] not in deployment['authorized_projects']:
        raise ValueError('Project is outside the configured owner-approved sandbox scope.')
    name = 'hanni-' + task['task_id']
    binding = digest({'deployment': deployment, 'task': task})
    metadata = {'name': name, 'namespace': deployment['namespace'],
                'labels': {'app': 'hanni-sandbox', 'hanni-task': task['task_id']},
                'annotations': {'hanni/task-binding': binding}}
    env = [{'name': 'HANNI_GATEWAY_URL', 'value': deployment['gateway_url']},
           {'name': 'HANNI_MODELS', 'value': json.dumps(deployment['models'])},
           {'name': 'HANNI_GATEWAY_TOKEN', 'valueFrom': {'secretKeyRef': {'name': 'hanni-token-'+task['task_id'], 'key': 'token'}}},
           {'name': 'HOME', 'value': '/workspace/home'}, {'name': 'TMPDIR', 'value': '/workspace/tmp'},
           {'name': 'PYTHONDONTWRITEBYTECODE', 'value': '1'}]
    config = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': metadata,
              'immutable': True, 'data': {'task.json': json.dumps(task)}}
    job = {'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': metadata,
           'spec': {'backoffLimit': 0, 'podReplacementPolicy':'Failed', 'activeDeadlineSeconds': deployment['deadline_seconds'],
                    'ttlSecondsAfterFinished': 86400,
                    'template': {'metadata': {'labels': metadata['labels']}, 'spec': {
                        'runtimeClassName': deployment['runtime_class'], 'restartPolicy': 'Never',
                        'automountServiceAccountToken': False, 'nodeSelector': deployment['node_selector'],
                        'securityContext': {'runAsNonRoot': True, 'runAsUser': 10001, 'runAsGroup': 10001,
                                            'fsGroup': 10001, 'seccompProfile': {'type': 'RuntimeDefault'}},
                        'containers': [{'name': 'harness', 'image': deployment['image'], 'imagePullPolicy': 'IfNotPresent',
                                        'command': ['python', '/opt/hanni/worker.py'], 'env': env,
                                        'securityContext': {'allowPrivilegeEscalation': False,
                                            'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}},
                                        'resources': {'requests': {'cpu': '500m', 'memory': '4Gi', 'ephemeral-storage':'512Mi'},
                                                      'limits': {'cpu': '2', 'memory': '4Gi', 'ephemeral-storage': '2Gi'}},
                                        'volumeMounts': [{'name': 'task', 'mountPath': '/input', 'readOnly': True},
                                                         {'name': 'work', 'mountPath': '/workspace'},
                                                         {'name':'shared','mountPath':'/snapshot','readOnly':True,
                                                          'subPath':'projects/'+task['project_id']+'/inputs'},
                                                         {'name':'shared','mountPath':'/results',
                                                          'subPath':'projects/'+task['project_id']+'/results/'+task['task_id']}]}],
                        'volumes': [{'name': 'task', 'configMap': {'name': name}},
                                    {'name': 'work', 'emptyDir': {'sizeLimit': '2Gi'}},
                                    {'name':'shared','persistentVolumeClaim':{'claimName':deployment['storage_claim']}}]}}}}
    return {'binding': binding, 'name': name, 'objects': [config, job],
            'authority': 'Exact owner-approved snapshots and sandbox-local effects only',
            'completion': 'A finished job is not independently verified task completion'}


class SandboxJobs:
    def __init__(self, data_dir, *, run=subprocess.run, admission=None):
        self.root = Path(data_dir) / 'cluster-harnesses'
        self.run, self.admission = run, admission
        self.lock = threading.RLock()

    def deployment(self, *, require_enabled=True):
        path = self.root / 'deployment.json'
        if not path.is_file() or path.is_symlink():
            raise ValueError('Sandbox deployment is not configured; no cluster operation was attempted.')
        if path.stat().st_size > 16384:
            raise ValueError('Sandbox deployment exceeds its size limit.')
        value = validate_deployment(json.loads(path.read_text()))
        if require_enabled and not value['enabled']:
            raise ValueError('Sandbox deployment is disabled.')
        return value

    def _command(self, deployment, arguments, payload=None):
        executable = shutil.which('kubectl')
        if not executable:
            raise ValueError('kubectl is unavailable; no cluster operation was attempted.')
        result = self.run([executable, '--context='+deployment['context'], '--namespace='+deployment['namespace'],
                           '--request-timeout=10s', *arguments], input=payload, capture_output=True,
                          timeout=15, text=True, encoding='utf-8', errors='replace',
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise ValueError('Cluster request failed; reconcile state before retrying a write.')
        if len(result.stdout.encode()) > 262144:
            raise ValueError('Cluster response exceeds the bounded receipt size.')
        return result.stdout

    def _admit(self, deployment, task, context=None, request=None):
        if context is not None:
            context.emergency_stop.guard('sandbox job submission')
        if request is not None and request.execution_guard:
            request.execution_guard()
        if self.admission is None:
            raise ValueError('The original model router is unavailable; sandbox inference is not authorized.')
        self.admission(deployment, task)

    def _sandbox_evidence(self, deployment):
        namespace = json.loads(self._command(deployment, ['get', 'namespace', deployment['namespace'], '-o', 'json']))
        labels = namespace.get('metadata', {}).get('labels', {})
        if labels.get('pod-security.kubernetes.io/enforce') != 'restricted':
            raise ValueError('Restricted Pod Security admission is not evidenced.')
        runtime = json.loads(self._command(deployment, ['get', 'runtimeclass', deployment['runtime_class'], '-o', 'json']))
        if runtime.get('handler') not in {'runsc', 'kata', 'kata-qemu'}:
            raise ValueError('Sandbox runtime isolation is not evidenced.')
        storage=json.loads(self._command(deployment,['get','pvc',deployment['storage_claim'],'-o','json']))
        if storage.get('status',{}).get('phase')!='Bound' or 'ReadWriteMany' not in storage.get('spec',{}).get('accessModes',[]):
            raise ValueError('Bound shared ReadWriteMany sandbox storage is not evidenced.')
        nodes=json.loads(self._command(deployment,['get','nodes','-l',
            'hanni.ai/worker-class=cpu,hanni.ai/sandbox-enabled=true','-o','json']))
        eligible=[node for node in nodes.get('items',[]) if not node.get('spec',{}).get('unschedulable')
                  and any(c.get('type')=='Ready' and c.get('status')=='True'
                          for c in node.get('status',{}).get('conditions',[]))]
        if not eligible:raise ValueError('No actual ready CPU sandbox worker is evidenced.')
        policy = json.loads(self._command(deployment, ['get', 'networkpolicy', 'hanni-sandbox-egress', '-o', 'json']))
        expected = network_policy(deployment)
        if policy.get('spec') != expected['spec']:
            raise ValueError('Exact gateway-only sandbox network policy is not evidenced.')
        # Another policy can add egress even if the named restriction is correct.
        policies = json.loads(self._command(deployment, ['get', 'networkpolicy', '-o', 'json']))
        if len(policies.get('items', [])) != 1:
            raise ValueError('Dedicated sandbox namespace must have exactly the reviewed network policy.')
        quota=json.loads(self._command(deployment,['get','resourcequota','hanni-sandbox-quota','-o','json']))
        if quota.get('spec')!=resource_quota(deployment)['spec']:
            raise ValueError('The exact bounded sandbox namespace resource quota is not evidenced.')
        jobs = json.loads(self._command(deployment, ['get', 'jobs', '-o', 'json']))
        if sum(bool(j.get('status', {}).get('active')) for j in jobs.get('items', [])) >= 2:
            raise ValueError('The bounded sandbox concurrency limit is occupied.')

    def preview(self, task):
        return manifests(self.deployment(require_enabled=False), task)

    def _connect(self):
        if self.root.is_symlink():
            raise ValueError('Sandbox state cannot use a symbolic link.')
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / 'jobs.sqlite3'
        if path.is_symlink():
            raise ValueError('Sandbox journal cannot use a symbolic link.')
        db = sqlite3.connect(path)
        db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,binding TEXT,state TEXT,uid TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS leases(token_hash TEXT PRIMARY KEY,task_id TEXT,expires REAL,remaining INTEGER,models TEXT,deployment TEXT)')
        return db

    def submit(self, task, expected_binding, *, context=None, request=None):
        task = validate_task(task)
        with self.lock:
            deployment = self.deployment()
            preview = manifests(deployment, task)
            if preview['binding'] != expected_binding:
                raise ValueError('Task or deployment changed; review the new preview.')
            self._admit(deployment, task, context, request)
            self._sandbox_evidence(deployment)
            if self.deployment()!=deployment:
                raise ValueError('Deployment changed during preflight; review the new scope.')
            self._admit(deployment, task, context, request)
            with self._connect() as db:
                old = db.execute('SELECT binding,state,uid FROM jobs WHERE id=?', (task['task_id'],)).fetchone()
                if old:
                    if old[0] != expected_binding:
                        raise ValueError('Task identity already belongs to a different scope.')
                    return {'task_id': task['task_id'], 'state': old[1], 'uid': old[2],
                            'duplicate_suppressed': True, 'task_complete': False}
                # A durable intent precedes either external write. An absent
                # acknowledgment must never cause an automatic second create.
                db.execute('INSERT INTO jobs VALUES(?,?,?,NULL)', (task['task_id'], expected_binding, 'uncertain'))
                token=secrets.token_urlsafe(32)
                from hanni.logs.redaction import register_secret
                register_secret('sandbox:'+task['task_id'],token)
                db.execute('INSERT INTO leases VALUES(?,?,?,?,?,?)',
                    (hashlib.sha256(token.encode()).hexdigest(),task['task_id'],time.time()+deployment['deadline_seconds'],
                     20,json.dumps({role:deployment['models'][role] for role in task['roles']}),digest(deployment)))
                db.commit()
                try:
                    if self.deployment()!=deployment:
                        raise ValueError('Deployment changed before dispatch.')
                    self._admit(deployment,task,context,request)
                    secret={'apiVersion':'v1','kind':'Secret','metadata':{
                        'name':'hanni-token-'+task['task_id'],'namespace':deployment['namespace'],
                        'labels':{'app':'hanni-sandbox','hanni-task':task['task_id']},
                        'annotations':{'hanni/task-binding':expected_binding}},
                        'type':'Opaque','stringData':{'token':token}}
                    self._command(deployment, ['create', '-f', '-', '-o', 'json'],
                                  json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': [secret,*preview['objects']]}))
                    self._admit(self.deployment(), task, context, request)
                    if self.deployment() != deployment:
                        raise ValueError('Deployment changed during submission; reconcile the uncertain job.')
                    job = json.loads(self._command(deployment, ['get', 'job', preview['name'], '-o', 'json']))
                    if job.get('metadata', {}).get('annotations', {}).get('hanni/task-binding') != expected_binding:
                        raise ValueError('Job evidence does not match the approved scope.')
                    uid = job['metadata']['uid']
                    db.execute('UPDATE jobs SET state=?,uid=? WHERE id=?', ('submitted', uid, task['task_id']))
                    db.commit()
                except (ValueError, OSError, subprocess.TimeoutExpired, KeyError, json.JSONDecodeError):
                    return {'task_id': task['task_id'], 'state': 'uncertain', 'task_complete': False,
                            'reason': 'Submission acknowledgment is uncertain; do not repeat the write automatically.'}
            return {'task_id': task['task_id'], 'state': 'submitted', 'uid': uid, 'task_complete': False}

    def inspect(self, task_id):
        identifier(task_id)
        deployment = self.deployment()
        with self._connect() as db:
            old = db.execute('SELECT binding,state,uid FROM jobs WHERE id=?', (task_id,)).fetchone()
        if not old:
            raise ValueError('Only HANNI-journaled sandbox jobs can be inspected.')
        job = json.loads(self._command(deployment, ['get', 'job', 'hanni-'+task_id, '-o', 'json']))
        meta = job.get('metadata', {})
        if meta.get('annotations', {}).get('hanni/task-binding') != old[0] or old[2] and meta.get('uid') != old[2]:
            raise ValueError('Job identity changed; evidence was rejected.')
        return {'task_id': task_id, 'uid': meta.get('uid'), 'job_status': job.get('status', {}),
                'journal_state': old[1], 'task_complete': False,
                'reason': 'Sandbox completion is advisory until artifacts are independently checked.'}

    def result(self, task_id):
        identity = self.inspect(task_id)
        text = self._command(self.deployment(), ['logs', 'job/hanni-'+task_id, '--tail=1', '--limit-bytes=131072'])
        if not text.startswith('HANNI_RESULT '):
            raise ValueError('No bounded sandbox result envelope is available.')
        receipt = json.loads(text[len('HANNI_RESULT '):])
        if (not isinstance(receipt, dict) or receipt.get('task_id') != task_id
                or receipt.get('task_complete') is not False or not isinstance(receipt.get('artifacts'), dict)):
            raise ValueError('Sandbox result is malformed; completion was not established.')
        for name, artifact in receipt['artifacts'].items():
            validate_task({'task_id':task_id,'project_id':'receipt','goal':'Validate returned source snapshot',
                           'roles':['manager'],'files':{name:artifact['content']},'checks':[['pytest']]})
            if hashlib.sha256(artifact['content'].encode()).hexdigest() != artifact.get('sha256'):
                raise ValueError('Sandbox artifact checksum does not match its contents.')
        with self._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS results(id TEXT PRIMARY KEY,uid TEXT,payload TEXT)')
            prior=db.execute('SELECT uid,payload FROM results WHERE id=?',(task_id,)).fetchone()
            encoded=canonical_json(receipt,maximum=131072)
            if prior and prior!=(identity['uid'],encoded):
                raise ValueError('Result changed after collection; prior evidence is preserved.')
            db.execute('INSERT OR IGNORE INTO results VALUES(?,?,?)',(task_id,identity['uid'],encoded))
        return {**receipt, 'job_uid': identity['uid'], 'evidence_scope':'untrusted_sandbox_output',
                'task_complete':False, 'applied_to_owner_project':False}

    def cancel(self, task_id, expected_uid):
        with self.lock:
            receipt = self.inspect(task_id)
            if receipt['uid'] != expected_uid or not isinstance(expected_uid, str) or not expected_uid:
                raise ValueError('Review the exact current sandbox UID before cancellation.')
            deployment = self.deployment()
            with self._connect() as db:
                db.execute('DELETE FROM leases WHERE task_id=?',(task_id,))
            path = '/apis/batch/v1/namespaces/'+deployment['namespace']+'/jobs/hanni-'+task_id
            options = {'apiVersion': 'v1', 'kind': 'DeleteOptions', 'preconditions': {'uid': expected_uid},
                       'propagationPolicy': 'Foreground', 'gracePeriodSeconds': 1}
            try:
                self._command(deployment, ['delete', '--raw='+path, '-f', '-'], json.dumps(options))
            except (ValueError, OSError, subprocess.TimeoutExpired):
                return {'task_id': task_id, 'state': 'cancel_uncertain', 'task_complete': False}
            with self._connect() as db:
                db.execute('UPDATE jobs SET state=? WHERE id=?', ('cancel_requested', task_id))
            return {'task_id': task_id, 'state': 'cancel_requested', 'task_complete': False}

    def stop_all(self):
        # Lease revocation is local and happens before best-effort cancellation
        # of exact owned jobs. Unknown write acknowledgments stay uncertain.
        with self._connect() as db:
            db.execute('DELETE FROM leases')
            active=list(db.execute("SELECT id,uid FROM jobs WHERE state IN ('submitted','uncertain')"))
        outcomes=[]
        for task_id,uid in active:
            try:
                if not uid:uid=self.inspect(task_id)['uid']
                outcomes.append(self.cancel(task_id,uid))
            except (ValueError,OSError,subprocess.TimeoutExpired):
                outcomes.append({'task_id':task_id,'state':'cancel_uncertain','task_complete':False})
        return outcomes

    def cleanup(self, task_id, expected_uid):
        identity=self.inspect(task_id)
        if identity['uid']!=expected_uid:
            raise ValueError('Cleanup requires the exact journaled job UID.')
        terminal=any(c.get('type') in {'Complete','Failed'} and c.get('status')=='True'
                     for c in identity['job_status'].get('conditions',[]))
        if not terminal:raise ValueError('Only an observed terminal job can be cleaned up.')
        deployment=self.deployment()
        with self._connect() as db:
            binding=db.execute('SELECT binding FROM jobs WHERE id=?',(task_id,)).fetchone()[0]
            db.execute('DELETE FROM leases WHERE task_id=?',(task_id,))
        try:
            for kind,name in (('secrets','hanni-token-'+task_id),('configmaps','hanni-'+task_id)):
                obj=json.loads(self._command(deployment,['get',kind,name,'-o','json']))
                meta=obj.get('metadata',{})
                if meta.get('annotations',{}).get('hanni/task-binding')!=binding:
                    raise ValueError('Cleanup object differs from the approved task binding.')
                path='/api/v1/namespaces/'+deployment['namespace']+'/'+kind+'/'+name
                body={'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':meta['uid']}}
                self._command(deployment,['delete','--raw='+path,'-f','-'],json.dumps(body))
            result=self.cancel(task_id,expected_uid)
        except (ValueError,OSError,KeyError,subprocess.TimeoutExpired):
            return {'task_id':task_id,'state':'cleanup_uncertain','task_complete':False}
        return {**result,'state':'cleanup_requested','durable_results_deleted':False}

    def gateway(self, token, payload, *, engine, guard):
        """Task-only pure inference over the original model engine, never tools."""
        if not isinstance(token,str) or not 20<=len(token)<=128:
            raise ValueError('Sandbox inference credential is invalid.')
        if (not isinstance(payload,dict) or set(payload)-{'model','messages','max_tokens','temperature','stream','chat_template_kwargs'}
                or payload.get('stream',False) is not False):
            raise ValueError('Only bounded nonstreaming text inference is supported; native tool turns require an original transport extension.')
        budget=payload.get('max_tokens',2048)
        if type(budget) is not int or not 1<=budget<=2048:
            raise ValueError('Sandbox output exceeds the approved budget.')
        models=None
        with self.lock, self._connect() as db:
            # Every HTTP request creates its own adapter. Fence budget reads
            # across adapters/processes, not just this instance's Python lock.
            db.execute('BEGIN IMMEDIATE')
            key=hashlib.sha256(token.encode()).hexdigest()
            row=db.execute('SELECT task_id,expires,remaining,models,deployment FROM leases WHERE token_hash=?',(key,)).fetchone()
            if not row or row[1]<=time.time() or row[2]<=0:
                raise ValueError('Sandbox inference scope expired, exhausted or revoked.')
            task_id=row[0];models=json.loads(row[3]);deployment_binding=row[4]
            job=db.execute('SELECT state FROM jobs WHERE id=?',(task_id,)).fetchone()
            if not job or job[0] not in {'submitted','uncertain'}:
                raise ValueError('Sandbox task is no longer admitted.')
            role=next((r for r,m in models.items() if m==payload.get('model')),None)
            if role is None:raise ValueError('Model is outside the approved sandbox roles.')
            db.execute('UPDATE leases SET remaining=remaining-1 WHERE token_hash=?',(key,))
        from hanni.models.adaptive import ModelRequest
        worker,category,_=ROLES[role]
        request=ModelRequest(task_category=category,complexity='complex',interactive=False,
            output_tokens=budget,privacy_categories=frozenset({'project','conversation','sensitive'}))
        def admission():
            guard()
            if digest(self.deployment())!=deployment_binding:
                raise ValueError('Sandbox deployment changed; inference scope was withdrawn.')
            selected=engine.select(request,allowed_endpoint_ids={'worker:'+worker})['endpoint']
            if selected is None or selected['model_id']!=models[role]:
                raise ValueError('Sandbox model identity or original eligibility changed.')
            with self._connect() as db:
                row=db.execute('SELECT expires FROM leases WHERE token_hash=?',(key,)).fetchone()
                if not row or row[0]<=time.time():raise ValueError('Sandbox inference was revoked or expired.')
        admission()
        text=engine.execute(payload['messages'],request=request,admission=admission,
            endpoint_id='worker:'+worker,max_fallbacks=0,max_tokens=budget,temperature=0,
            workflow_id='sandbox_'+task_id,step_id=role)
        admission()
        return {'object':'chat.completion','model':models[role],
                'choices':[{'index':0,'message':{'role':'assistant','content':text},'finish_reason':'stop'}]}


def network_policy(deployment):
    deployment = validate_deployment(deployment)
    parts = urlsplit(deployment['gateway_url'])
    address = ipaddress.ip_address(parts.hostname)
    return {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
            'metadata': {'name': 'hanni-sandbox-egress', 'namespace': deployment['namespace']},
            'spec': {'podSelector': {}, 'policyTypes': ['Ingress', 'Egress'], 'ingress': [],
                     'egress': [{'to': [{'ipBlock': {'cidr': str(address)+('/32' if address.version == 4 else '/128')}}],
                                 'ports': [{'protocol': 'TCP', 'port': parts.port}]}]}}


def resource_quota(deployment):
    deployment=validate_deployment(deployment)
    return {'apiVersion':'v1','kind':'ResourceQuota',
            'metadata':{'name':'hanni-sandbox-quota','namespace':deployment['namespace']},
            'spec':{'hard':{'pods':'2','requests.cpu':'4','limits.cpu':'4',
                            'requests.memory':'8Gi','limits.memory':'8Gi',
                            'requests.ephemeral-storage':'4Gi','limits.ephemeral-storage':'4Gi',
                            'count/jobs.batch':'16','count/configmaps':'16','count/secrets':'16'}}}
