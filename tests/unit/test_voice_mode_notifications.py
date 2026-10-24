"""Real voice state transitions and native delivery; no acoustic claims."""
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from desktop.main import DesktopApp, load_preferences, save_preferences
from desktop.notifications import NotificationRateLimit, VoiceModeFeed
from hanni.core.activity import Activity
from hanni.core.interaction import InteractionState
from hanni.core import interaction as interaction_module
from hanni.dashboard import voice as voice_module
from hanni.dashboard.voice import VoiceControl
from hanni.speech.relevance import SpeechRelevanceClassifier
from hanni.speech.attention import SpeechAttentionRouter
from hanni.speech.types import TranscriptRecord


@pytest.fixture
def voice(monkeypatch):
    state=InteractionState()
    monkeypatch.setattr(voice_module,'interaction',state)
    monkeypatch.setattr(interaction_module,'interaction',state)
    monkeypatch.setattr(voice_module,'activity',Activity())
    control=VoiceControl()
    pump=SimpleNamespace(closed=False,paused=False,failed=False,running=lambda:False)
    def pause(): pump.paused=True
    def resume(): pump.paused=False
    pump.pause,pump.resume=pause,resume
    classifier=SpeechRelevanceClassifier()
    registry=SimpleNamespace(context=SimpleNamespace(emergency_stop=SimpleNamespace(guard=lambda _:None)))
    control.bind(pump,classifier,registry,'hanni')
    return control,state


def action(control,name):
    return control.execute({'id':str(uuid4()),'action':name})


def test_listen_followups_processing_and_speaking_emit_only_mode_changes(voice):
    control,state=voice; feed=VoiceModeFeed()
    assert feed.observe(control.snapshot())==['HANNI is in standby. Say "Hanni" to start listening.']
    assert feed.observe(action(control,'listen'))==['HANNI is listening.']
    assert feed.observe(action(control,'listen'))==[]
    state.responding(True)
    assert control.snapshot()['state']=='processing'
    assert feed.observe(control.snapshot())==[]
    state.responding(False)
    with state.synthesis():
        assert control.snapshot()['state']=='processing'
        assert not control.snapshot()['speaking']
        assert feed.observe(control.snapshot())==[]
    state.playback=SimpleNamespace(active=True)
    try:
        assert control.snapshot()['state']=='speaking'
        assert feed.observe(control.snapshot())==[]
    finally:
        state.playback=None
    state.engaged(False)
    assert feed.observe(control.snapshot())==['HANNI is in standby. Say "Hanni" to start listening.']
    assert feed.observe(control.snapshot())==[]


def test_fast_wake_and_standby_between_polls_are_preserved(voice):
    control,state=voice; feed=VoiceModeFeed(); feed.observe(control.snapshot())
    state.engaged(True); state.engaged(False)
    assert feed.observe(control.snapshot())==['HANNI is listening.',
        'HANNI is in standby. Say "Hanni" to start listening.']
    assert feed.observe(control.snapshot())==[]


def test_original_wake_and_disengage_router_generate_mode_alerts(voice):
    control,state=voice; feed=VoiceModeFeed(); feed.observe(control.snapshot())
    router=SpeechAttentionRouter(control.classifier)
    first=router.route(TranscriptRecord(text='Hanni, what time is it?',started_at=0,ended_at=0))
    assert first.decision.wake_word_detected
    assert feed.observe(control.snapshot())==['HANNI is listening.']
    last=router.route(TranscriptRecord(text="that's all",started_at=0,ended_at=0))
    assert last.decision.disengaged
    assert feed.observe(control.snapshot())==['HANNI is in standby. Say "Hanni" to start listening.']


def test_mute_and_capture_failure_report_off_without_fabricating_standby(voice):
    control,state=voice; feed=VoiceModeFeed(); feed.observe(control.snapshot())
    feed.observe(action(control,'listen'))
    assert feed.observe(action(control,'mute'))==['HANNI is not listening. Microphone muted.']
    assert feed.observe(control.snapshot())==[]
    action(control,'unmute'); feed.observe(action(control,'listen'))
    control.pump.failed=True
    assert feed.observe(control.snapshot())==['HANNI is not listening. Voice is unavailable.']


def test_startup_and_unmute_into_standby_get_one_current_mode_notification(voice):
    control,state=voice; feed=VoiceModeFeed()
    ready=control.snapshot()
    disabled={**ready,'state':'disabled','available':False,'listening_mode':False}
    assert feed.observe(disabled)==[]
    assert feed.observe(disabled)==[]
    assert feed.observe(ready)==['HANNI is in standby. Say "Hanni" to start listening.']
    assert feed.observe(action(control,'mute'))==['HANNI is not listening. Microphone muted.']
    assert feed.observe(action(control,'unmute'))==['HANNI is in standby. Say "Hanni" to start listening.']
    assert feed.observe(control.snapshot())==[]


def test_backend_restart_never_replays_old_mode_events_and_stale_snapshots_are_ignored(voice):
    control,state=voice; feed=VoiceModeFeed(); feed.observe(control.snapshot())
    old=control.snapshot()
    state.engaged(True); latest=control.snapshot(); feed.observe(latest)
    assert feed.observe(old)==[]
    restarted={**latest,'mode_session':'new-session','mode_revision':20,
        'mode_events':[{'revision':19,'engaged':False},{'revision':20,'engaged':True}]}
    assert feed.observe(restarted)==['HANNI is listening.']
    assert feed.observe(restarted)==[]


def test_journal_and_reconnect_backlog_are_bounded(voice):
    control,state=voice; feed=VoiceModeFeed(); feed.observe(control.snapshot())
    for index in range(101): state.engaged(index%2==0)
    snapshot=control.snapshot()
    assert len(snapshot['mode_events'])==32
    assert feed.observe(snapshot)==['HANNI is listening.']
    assert all(set(event)=={'revision','engaged'} for event in snapshot['mode_events'])
    assert feed.observe({'listening_mode':True,'mode_session':[],'mode_revision':0})==[]


def test_voice_alerts_are_enabled_separately_persist_and_are_not_suppressed_by_general_rate_limit(tmp_path,voice):
    control,state=voice
    preferences=load_preferences(tmp_path/'window.json')
    assert preferences['voice_notifications'] and preferences['notifications']
    request=Mock(side_effect=lambda url,path,**kw: {'token':'ephemeral'} if path.startswith('/api/chat') else control.snapshot())
    app=DesktopApp(SimpleNamespace(url='http://127.0.0.1:8765',request=request),tmp_path,'HANNI OS',preferences)
    app.tray=SimpleNamespace(HAS_NOTIFICATION=True,notify=Mock())
    app.notification_limit=NotificationRateLimit(maximum=0)
    app.observe_voice_notifications()
    state.engaged(True); app.observe_voice_notifications()
    state.engaged(False); app.observe_voice_notifications()
    app.observe_voice_notifications()
    assert app.tray.notify.call_count==3
    assert app.tray.notify.call_args.args==('HANNI is in standby. Say "Hanni" to start listening.','HANNI OS')
    assert all(call.args[1] in {'/api/chat?before=1','/api/voice'} for call in request.call_args_list)
    assert request.call_args_list[-1].kwargs=={'token':'ephemeral'}
    app.preferences['voice_notifications']=False
    before=request.call_count; app.observe_voice_notifications()
    assert request.call_count==before and app.voice_notification_feed is None
    save_preferences(tmp_path/'window.json',app.preferences)
    assert not load_preferences(tmp_path/'window.json')['voice_notifications']
