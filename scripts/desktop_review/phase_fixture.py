"""Real isolated Phase 2 workspace records; only telemetry/replies are synthetic.

Private CRUD is never mocked: requests pass the original DashboardServer token,
Host/Origin checks, DesktopFeatures adapter, ToolRegistry and migrated stores.
No calendar provider, voice session or vision implementation is fabricated.
"""
from __future__ import annotations

from datetime import date, timedelta
import json
import urllib.request
from uuid import uuid4

from fixture import ROOT, ReviewFixture


class DisconnectedReviewVault:
    """Existing GoogleAccess offline seam; never reads user Credential Manager."""
    def labels(self):
        return ('personal', 'school')

    def get(self, account):
        return None

    def preferences(self):
        return {}


class PhaseReviewFixture(ReviewFixture):
    def __enter__(self):
        super().__enter__()
        try:
            self.sample['activity']={'input_level':0,'speaking':False,'microphone_active':False}
            self.sample['interaction'].update(response_in_progress=False,tts_speaking=False,voice_engaged=False)
            # Registry tools share this actual GoogleAccess object. Override
            # only its documented offline vault seam before any account reads.
            # Local data_dir does not isolate Windows Credential Manager.
            self.server.features.registry.google_access._vault = DisconnectedReviewVault()
            self.seeded=[]
            project=self.operation('project.create', {
                'name':'Desktop release review',
                'description':'Isolated verification project. These local records exercise the real store.',
            })['project']
            self.operation('project.create', {'name':'Cluster maintenance','description':'Review fixture project for repair follow-up.'})
            self.operation('note.create', {'project_id':project['id'], 'title':'Review notes',
                'body':'Check small-window readability and keep unavailable capabilities explicit. This note is a local verification fixture.'})
            self.operation('link.create', {'project_id':project['id'], 'label':'Interface architecture',
                'target':str(ROOT/'docs/HANNI_OS.md'),'kind':'file'})
            today=date.today()
            self.operation('task.create', {'title':'Check desktop window layouts','course':'Interface review',
                'due':today.isoformat(),'priority':'high','project_id':project['id']})
            self.operation('task.create', {'title':'Review cluster repair status','course':'Maintenance',
                'due':(today+timedelta(days=2)).isoformat(),'priority':'normal','project_id':None})
            task=self.operation('task.create', {'title':'Capture native shortcut behavior','course':'Interface review',
                'due':None,'priority':'low','project_id':project['id']})['task']
            self.operation('task.update', {'task_id':task['id'],'expected_fingerprint':task['fingerprint'],
                'title':task['title'],'course':task['course'],'due':None,'priority':task['priority'],
                'project_id':task['project_id'],'status':'completed'})
            memories=self.server.features.memory_store()
            memories.remember('Review fixture preference: use compact task rows.',source='owner_explicit')
            memories.remember('Review fixture project: inspect native Windows interactions.',source='owner_explicit')
            self.workspace_seed_disclosure='Real isolated registry-gated task/project/note/link records and original MemoryStore entries, with synthetic review content. GoogleAccess uses an explicitly empty offline vault rather than user Windows Credential Manager; calendar disconnected. No voice/vision session.'
            return self
        except BaseException:
            super().__exit__(None,None,None)
            raise

    def operation(self, operation, data):
        body={'id':str(uuid4()),'operation':operation,'data':data,'confirmed':True}
        request=urllib.request.Request(self.url+'api/productivity',
            data=json.dumps(body).encode(),method='POST',headers={
                'Content-Type':'application/json','Origin':self.url.rstrip('/'),
                'X-Hanni-Token':self.hub.token,
            })
        with urllib.request.urlopen(request,timeout=5) as response:
            result=json.load(response)
        self.seeded.append({'operation':operation,'id':body['id']})
        return result
