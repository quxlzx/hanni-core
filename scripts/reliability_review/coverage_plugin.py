"""Optional verification-only observation of registry handlers.

Use: PYTHONPATH=scripts python -m pytest -p reliability_review.coverage_plugin
Set HANNI_RELIABILITY_COVERAGE to a review artifact path. No request arguments,
tool messages/data, prompts, credentials or descriptions are inspected/stored.
This profiler does not replace registry methods/handlers or grant authority.
"""
from collections import Counter
import json
import os
from pathlib import Path
import re
import sys
import threading

_lock=threading.RLock()
_active={}
_counts=Counter()
_observer_errors=0
_old_profile=None
_old_thread_profile=None

def _safe(value):
    return value if isinstance(value,str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,256}",value) else "unknown"

def _profile(frame,event,arg):
    global _observer_errors
    try:
        parent=frame.f_back
        with _lock:
            if event=="call":
                if frame.f_code.co_name=="_execute" and frame.f_code.co_filename.replace("\\","/").endswith("/hanni/tools/base.py"):
                    _active[id(frame)]={"frame":frame,"entered":False,"module":"unknown"}
                elif parent is not None and id(parent) in _active:
                    slot=_active[id(parent)]
                    definition=parent.f_locals.get("definition")
                    handler=getattr(definition,"handler",None)
                    code=getattr(handler,"__code__",None)
                    if code is None:
                        code=getattr(getattr(handler,"__call__",None),"__code__",None)
                    if frame.f_code is code:
                        slot["entered"]=True
                        slot["module"]=_safe(frame.f_globals.get("__name__"))
            elif event=="return" and id(frame) in _active:
                slot=_active.pop(id(frame))
                definition=frame.f_locals.get("definition")
                identifier=_safe(getattr(definition,"name",None))
                # Only supported metadata fields are selected, never raw results.
                ok=arg.ok if type(arg).__name__=="ToolResult" else None
                verification=getattr(arg,"verification",None) if type(arg).__name__=="ToolResult" else None
                v=verification if isinstance(verification,dict) else {}
                origin=("production_builtin" if slot["module"].startswith("hanni.tools.")
                        else "production_mcp_adapter" if slot["module"].startswith("hanni.mcp.")
                        else "fixture_or_other")
                key=(identifier,slot["entered"],slot["module"],origin,ok,_safe(v.get("status")),_safe(v.get("method")),_safe(v.get("scope")))
                _counts[key]+=1
    except Exception:
        _observer_errors+=1

def pytest_sessionstart(session):
    global _old_profile,_old_thread_profile
    _old_profile=sys.getprofile()
    _old_thread_profile=threading.getprofile()
    if _old_profile or _old_thread_profile:
        raise RuntimeError("Registry coverage requires a dedicated process without another profiler.")
    sys.setprofile(_profile)
    threading.setprofile(_profile)

def pytest_sessionfinish(session,exitstatus):
    sys.setprofile(_old_profile)
    threading.setprofile(_old_thread_profile)
    rows=[]
    for key,count in sorted(_counts.items(),key=lambda pair:str(pair[0])):
        name,entered,module,origin,ok,status,method,scope=key
        rows.append(dict(capability_id=name,handler_entered=entered,handler_module=module,
            handler_origin=origin,response_ok=ok,verification_status=status,
            verification_method=method,verification_scope=scope,count=count))
    path=Path(os.environ.get("HANNI_RELIABILITY_COVERAGE","data/hanni-reliability-v2-review/handler-coverage.json"))
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(dict(exitstatus=exitstatus,observer_errors=_observer_errors,
        disclosure="Python registry call/return profiling only. Production modules and controlled test handlers distinguished; adapter dependencies may be mocked. Direct handlers outside registry and subprocesses not captured. No raw argument/message/result text stored. Profiling overhead is not benchmark latency.",
        observations=rows),indent=2),encoding="utf8")

