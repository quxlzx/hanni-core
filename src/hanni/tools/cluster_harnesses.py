"""Opt-in sandbox capabilities on the original audited tool boundary."""
from hanni.compute.harnesses import ROLES, SandboxJobs
from hanni.tools.base import ToolDefinition, ToolResult
from pathlib import Path


def definitions(config, *, data_dir=None):
    root=Path(data_dir or config.paths.data_dir)
    # An absent private deployment adds no tool-menu overhead to everyday QA.
    if not (root / 'cluster-harnesses/deployment.json').exists():
        return ()

    def admission(deployment, task):
        from hanni.models.adaptive import ModelRequest, current
        engine = current(config)
        if engine is None or engine.data_dir.resolve()!=root.resolve():
            raise ValueError('The original model router is unavailable.')
        for role in task['roles']:
            worker_id, category, _ = ROLES[role]
            request = ModelRequest(task_category=category, complexity='complex', interactive=False,
                privacy_categories=frozenset({'project', 'conversation', 'sensitive'}), output_tokens=2048)
            selection = engine.select(request, allowed_endpoint_ids={'worker:'+worker_id})
            row = selection['endpoint']
            if row is None or row['model_id'] != deployment['models'][role]:
                raise ValueError('Required specialist lacks current original identity/capability/privacy/resource admission: '+role)

    jobs = SandboxJobs(root, admission=admission)

    def handle(operation):
        def execute(args, context, request):
            if operation == 'preview': result = jobs.preview(args['task'])
            elif operation == 'submit': result = jobs.submit(args['task'], args['preview_binding'], context=context, request=request)
            elif operation == 'status': result = jobs.inspect(args['task_id'])
            elif operation == 'result': result = jobs.result(args['task_id'])
            elif operation == 'cleanup': result = jobs.cleanup(args['task_id'], args['expected_uid'])
            else: result = jobs.cancel(args['task_id'], args['expected_uid'])
            certain=result.get('state') not in {'uncertain','cancel_uncertain','cleanup_uncertain'}
            return ToolResult('cluster.task_'+operation, certain,
                              'Sandbox '+operation+' evidence returned; task completion is not established.', result,
                              verification={'status':'VERIFIED' if operation == 'preview' else 'UNVERIFIED',
                                            'scope':'bounded_manifest' if operation == 'preview' else 'cluster_receipt_only'})
        return execute

    tools = []
    for operation, schema in (
        ('preview', {'task':dict}), ('submit', {'task':dict, 'preview_binding':str}),
        ('status', {'task_id':str}), ('result', {'task_id':str}), ('cancel', {'task_id':str, 'expected_uid':str}),
        ('cleanup', {'task_id':str, 'expected_uid':str})):
        write = operation in {'submit','cancel','cleanup'}
        output=({'binding':'string','name':'string','objects':'array'} if operation=='preview'
                else {'task_id':'string','uid':'string','job_status':'object','task_complete':'boolean'} if operation=='status'
                else {'task_id':'string','job_uid':'string','artifacts':'object','checks':'array','task_complete':'boolean'} if operation=='result'
                else {'task_id':'string','state':'string','task_complete':'boolean'})
        tools.append(ToolDefinition('cluster.task_'+operation,
            'Sandbox CPU specialist '+operation+' for LangGraph manager, OpenCode coder, Aider editor and GPT Researcher; exact owner scope, no Qwen 9B.',
            3 if write else 0, 3 if write else 0, schema,
            output, handle(operation),
            side_effect='external_action' if write else 'read', retry_attempts=1,
            requires_confirmation_if=(lambda _: 'Confirm this exact scoped sandbox operation.') if write else None,
            background_allowed=True, retry_safe=not write,
            tags=('cluster','sandbox','coding','research','project','harness'),
            argument_constraints={key:{'required':True,'nullable':False} for key in schema}))
    return tuple(tools)
