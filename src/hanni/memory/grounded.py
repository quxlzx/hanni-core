"""Read-only bounded personal packages; every entry is data, never authority."""
from datetime import datetime, timezone
import json
import time

from hanni.memory.privacy import validate_memory_text, validate_memory_record
from hanni.memory.retrieval import MemoryContext, MEMORY_DATA_POLICY, context_terms
from hanni.logs.redaction import secret_registry_revision


class GroundedPersonalContext:
    def __init__(self, base, *, max_bytes=4000, clock=time.time):
        if type(max_bytes) is not int or not 128 <= max_bytes <= 16000:
            raise ValueError('Invalid personal-context budget.')
        self.base, self.max_bytes, self.clock = base, max_bytes, clock
        self.conversation, self.observations = (), ()
        self.last_metrics = {}
        self.privacy_categories = frozenset({'memory'})

    def invalidate(self):
        self.conversation, self.observations = (), ()
        if callable(getattr(self.base,'invalidate',None)): self.base.invalidate()

    def set_ephemeral(self, *, conversation=(), observations=()):
        self.conversation, self.observations = tuple(conversation)[-4:], tuple(observations)[-4:]

    def retrieve(self, goal):
        started=time.perf_counter(); now=self.clock(); terms=context_terms(goal)
        privacy_revision=secret_registry_revision()
        recalled=self.base.retrieve(goal)
        package={'kind':'bounded_personal_context','policy':MEMORY_DATA_POLICY,
                 'assembled_at':datetime.fromtimestamp(now,timezone.utc).isoformat(),
                 'memories':[], 'temporary_conversation':[], 'live_observations':[], 'conflicts':[]}
        accepted=[]
        def fits():
            return len(json.dumps(package,ensure_ascii=False,allow_nan=False).encode())<=self.max_bytes
        from hanni.memory.integration import needs_project_context
        if recalled.text and needs_project_context(goal) and getattr(self.base,'project_context',None) is not None:
            lines=[]
            for line in recalled.text.splitlines():
                if len(('\n'.join(lines+[line])).encode())<=self.max_bytes//2: lines.append(line)
            if lines: package['scoped_project_workflow_data']='\n'.join(lines)
        groups={}
        for match in recalled.matches:
            record=match.record
            # Re-read after retrieval; deletion/correction cannot reuse a cached fact.
            store=getattr(self.base,'store',None)
            if store is not None:
                current=store.get(record.id)
                if current is None or current.to_dict()!=record.to_dict(): continue
            try: validate_memory_record(record,max_chars=4000)
            except ValueError: continue
            entry=record.to_dict()
            entry['context_kind']=('inferred_preference' if record.semantic_status=='inference'
                else 'historical_observation' if record.semantic_status in {'historical','verified_outcome'}
                else 'owner_plan' if record.semantic_status=='plan'
                else 'owner_statement' if record.source.startswith('owner_extracted:')
                else 'explicit_owner_fact' if record.source in {'owner_explicit','owner_statement','owner_capture','owner','owner_correction'}
                    or record.source.startswith('owner_explicit:')
                else 'unverified_claim')
            entry['current_state_verified']=False
            if record.fact_key: groups.setdefault(record.fact_key,[]).append(entry)
            package['memories'].append(entry)
            if fits(): accepted.append(match)
            else: package['memories'].pop()
        for key,entries in groups.items():
            if len({e['fact_value'] for e in entries})>1:
                package['conflicts'].append({'fact_key':key,'state':'unresolved_owner_correction_required'})
                if not fits(): package['conflicts'].pop()
                for entry in package['memories']:
                    if entry['fact_key']==key: entry['conflicted']=True
        # Project/workflow context has already passed its original scoped provider.
        if recalled.text and not recalled.matches:
            package['scoped_project_workflow_data']=recalled.text
            if not fits(): package.pop('scoped_project_workflow_data')
        for message in self.conversation:
            if message.get('role')!='user' or not terms.intersection(context_terms(str(message.get('content','')))): continue
            try: validate_memory_text(message['content'],max_chars=1000)
            except (ValueError,KeyError): continue
            package['temporary_conversation'].append({'content':message['content'],'source':'current_owner_conversation',
                'context_kind':'temporary_conversation','durable':False,'confidence':None})
            package['temporary_conversation'][-1]['observed_at']=message.get('observed_at')
            if not fits(): package['temporary_conversation'].pop()
        for observation in self.observations:
            stamp=observation.get('sampled_at')
            if type(stamp) not in (int,float) or not 0<=now-stamp<=60: continue
            if observation.get('verification')!='VERIFIED': continue
            if not terms.intersection(context_terms(observation.get('source','')+' '+observation.get('subject',''))): continue
            try:
                validate_memory_text(json.dumps(observation,ensure_ascii=False,allow_nan=False),max_chars=2000)
            except (ValueError,TypeError): continue
            package['live_observations'].append(dict(observation,context_kind='live_observation',durable=False))
            if not fits(): package['live_observations'].pop()
        self.privacy_categories=frozenset({'memory'} | ({'project'} if any(m.record.project_id for m in accepted)
            or 'scoped_project_workflow_data' in package else set()))
        present=bool(package['memories'] or package['temporary_conversation'] or package['live_observations']
                     or package.get('scoped_project_workflow_data'))
        text=json.dumps(package,ensure_ascii=False,allow_nan=False) if present and fits() and privacy_revision==secret_registry_revision() else ''
        self.last_metrics={'records':len(accepted),'bytes':len(text.encode()),
                           'latency_ms':(time.perf_counter()-started)*1000,'network_calls':0}
        return MemoryContext(text,tuple(accepted) if text else ())
