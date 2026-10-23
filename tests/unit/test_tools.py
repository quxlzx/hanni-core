from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from hanni.config.schema import PermissionLevel, PermissionProfile, PermissionsConfig
from hanni.core.identity import Actor
from hanni.core.shutdown import EmergencyStop, FileStopStateStore, MemoryStopStateStore, StopSource
from hanni.tools.audit import ToolAuditLog
from hanni.tools.base import ConfirmationRequired, ToolContext, ToolPermissionError, ToolRegistry, ToolRequest
from hanni.tools.files import definitions as file_definitions
from hanni.tools.powershell import dangerous_reason
from hanni.tools.router import VoiceToolRouter
from hanni.tools.system import definitions as system_definitions
from hanni.tools.windows import definitions as windows_definitions

def permissions() -> PermissionsConfig:
    levels = tuple((PermissionLevel(i, f'l{i}', '-', i < 3) for i in range(4)))
    profiles = {'owner': PermissionProfile('owner', 2, False), 'everyone_else': PermissionProfile('everyone_else', -1, True)}
    return PermissionsConfig(levels, profiles)

class ToolsTests(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        ctx = ToolContext(permissions(), EmergencyStop(MemoryStopStateStore()), ToolAuditLog(self.tmp))
        self.registry = ToolRegistry(ctx)
        for d in (*system_definitions(), *windows_definitions(), *file_definitions()):
            self.registry.register(d)

    def test_system_stats_executes_for_owner(self) -> None:
        result = self.registry.execute(ToolRequest('system.stats', {}, source='test'))
        self.assertTrue(result.ok)
        self.assertIn('cpu_percent', result.data)

    def test_non_owner_cannot_use_tools(self) -> None:
        with self.assertRaises(ToolPermissionError):
            self.registry.execute(ToolRequest('system.stats', {}, actor_profile='everyone_else'))

    def test_level_three_delete_requires_confirmation(self) -> None:
        target = self.tmp / 'delete-me.txt'
        target.write_text('x')
        with self.assertRaises(ConfirmationRequired):
            self.registry.execute(ToolRequest('file.delete', {'path': str(target)}))
        self.assertTrue(target.exists())
        result = self.registry.execute(ToolRequest('file.delete', {'path': str(target)}, confirmed=True))
        self.assertTrue(result.ok)
        self.assertFalse(target.exists())
        rows = ToolAuditLog(self.tmp).tail()
        self.assertTrue(any((row['tool'] == 'file.delete' and (not row['ok']) for row in rows)))

    def test_emergency_stop_blocks_tools(self) -> None:
        self.registry.context.emergency_stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal('test'), reason='test')
        with self.assertRaises(Exception):
            self.registry.execute(ToolRequest('system.stats', {}))

    def test_external_persisted_stop_blocks_next_tool_execution(self) -> None:
        store = FileStopStateStore.for_data_dir(self.tmp)
        long_lived_stop = EmergencyStop(store)
        ctx = ToolContext(permissions(), long_lived_stop, ToolAuditLog(self.tmp))
        registry = ToolRegistry(ctx)
        for definition in system_definitions():
            registry.register(definition)
        external = EmergencyStop(FileStopStateStore.for_data_dir(self.tmp))
        external.trip(source=StopSource.LOCAL_TERMINAL, requested_by=Actor.local('test-laptop'), reason='external')
        with self.assertRaises(Exception):
            registry.execute(ToolRequest('system.stats', {}))

    def test_app_open_uses_alias(self) -> None:
        definition = self.registry.get('app.open')
        with patch('hanni.tools.windows.subprocess.Popen') as popen, patch('hanni.tools.windows._known_launch_command', return_value=None), patch('hanni.tools.windows._find_start_menu_shortcut', return_value=None):
            result = definition.handler({'app': 'VS Code'}, self.registry.context, ToolRequest('app.open', {'app': 'VS Code'}))
        self.assertTrue(result.ok)
        self.assertIn('code', popen.call_args.args[0])
        self.assertEqual(result.data['outcome'], 'process_started')
        self.assertFalse(result.data['verified'])
        self.assertEqual(result.message, 'Started VS Code.')

    def test_notepad_direct_start_reports_process_creation(self) -> None:
        definition = self.registry.get('app.open')
        with patch('hanni.tools.windows.subprocess.Popen') as popen, patch('hanni.tools.windows._known_launch_command', return_value=None), patch('hanni.tools.windows._find_start_menu_shortcut', return_value=None):
            popen.return_value.pid = 4321
            result = definition.handler({'app': 'Notepad'}, self.registry.context, ToolRequest('app.open', {'app': 'Notepad'}))
        self.assertEqual(popen.call_args.args[0], ['notepad.exe'])
        self.assertEqual(result.data['process_id'], 4321)
        self.assertEqual(result.message, 'Started Notepad.')

    def test_app_open_rejects_cmd_metacharacters(self) -> None:
        definition = self.registry.get('app.open')
        with self.assertRaises(ValueError):
            definition.handler({'app': 'notepad & calc'}, self.registry.context, ToolRequest('app.open', {'app': 'notepad & calc'}))

    def test_audit_log_is_written(self) -> None:
        self.registry.execute(ToolRequest('system.stats', {}, source='test'))
        rows = ToolAuditLog(self.tmp).tail()
        self.assertEqual(rows[-1]['tool'], 'system.stats')
        self.assertTrue(rows[-1]['ok'])

    def test_file_write_audit_does_not_copy_file_contents(self) -> None:
        target = self.tmp / 'private.txt'
        secret_text = 'this is private file content'
        result = self.registry.execute(ToolRequest('file.write', {'path': str(target), 'text': secret_text}, source='test'))
        self.assertTrue(result.ok)
        raw = ToolAuditLog(self.tmp).path.read_text(encoding='utf-8')
        self.assertNotIn(secret_text, raw)
        self.assertIn('[CONTENT:', raw)

    def test_file_list_dir_can_filter_folders(self) -> None:
        (self.tmp / 'folder-a').mkdir()
        (self.tmp / 'file-a.txt').write_text('x')
        result = self.registry.execute(ToolRequest('file.list_dir', {'path': str(self.tmp), 'kind': 'folder'}, source='test'))
        self.assertEqual([row['name'] for row in result.data['entries']], ['folder-a'])

    def test_file_mkdir_creates_real_folder(self) -> None:
        target = self.tmp / 'm8-test'
        result = self.registry.execute(ToolRequest('file.mkdir', {'path': str(target)}, source='test'))
        self.assertTrue(result.ok)
        self.assertTrue(target.is_dir())
        self.assertTrue(result.data['created'])

    def test_file_locate_resolves_exact_existing_folder(self) -> None:
        target = self.tmp / 'hanni-m8-lab'
        target.mkdir()
        result = self.registry.execute(ToolRequest('file.locate', {'name': 'hanni-m8-lab', 'kind': 'folder', 'root': str(self.tmp)}, source='test'))
        self.assertTrue(result.ok)
        self.assertEqual(len(result.data['matches']), 1)
        self.assertEqual(Path(result.data['matches'][0]['path']), target.resolve())

    def test_recursive_folder_delete_requires_confirmation(self) -> None:
        target = self.tmp / 'delete-folder'
        target.mkdir()
        (target / 'inside.txt').write_text('x')
        request = ToolRequest('file.delete', {'path': str(target), 'recursive': True}, source='test')
        with self.assertRaises(ConfirmationRequired):
            self.registry.execute(request)
        self.assertTrue(target.exists())
        result = self.registry.execute(ToolRequest('file.delete', {'path': str(target), 'recursive': True}, confirmed=True, source='test'))
        self.assertTrue(result.ok)
        self.assertFalse(target.exists())

    def test_gpu_tool_filters_permission_placeholders_and_uses_vram(self) -> None:
        with patch('hanni.tools.system._windows_gpu_utilization', return_value={100: 0.0, 200: 0.0}), patch('hanni.tools.system._windows_gpu_dedicated_memory', return_value={200: 2048.0}), patch('hanni.tools.system._nvidia_process_memory', return_value={100: {'pid': 100, 'name': '[Insufficient Permissions]', 'vram_mb': None}, 200: {'pid': 200, 'name': 'Code.exe', 'vram_mb': None}}):
            result = self.registry.execute(ToolRequest('gpu.top_processes', {'limit': 5}, source='test'))
        self.assertNotIn('Insufficient Permissions', result.message)
        self.assertIn('Code.exe', result.message)
        self.assertIn('2048', result.message)

class VoiceToolRouterTests(unittest.TestCase):

    def setUp(self) -> None:
        self.router = VoiceToolRouter()

    def test_open_vs_code(self) -> None:
        match = self.router.route('Can you open VS Code')
        self.assertIsNotNone(match)
        self.assertEqual(match.request.name, 'app.open')
        self.assertEqual(match.request.arguments['app'], 'VS Code')

    def test_top_cpu(self) -> None:
        match = self.router.route("Show me what's using the most CPU")
        self.assertIsNotNone(match)
        self.assertEqual(match.request.name, 'process.top_cpu')

    def test_unknown_conversation_is_not_a_tool(self) -> None:
        self.assertIsNone(self.router.route('Tell me a joke'))

    def test_active_window_routes_to_windows_metadata_tool(self) -> None:
        match = self.router.route('What is my active window right now?')
        self.assertIsNotNone(match)
        self.assertEqual(match.request.name, 'ui.active_window')

    def test_list_downloads_routes_to_directory_listing(self) -> None:
        match = self.router.route('Hanyi, list the files in my download folder')
        self.assertIsNotNone(match)
        self.assertEqual(match.request.name, 'file.list_dir')
        self.assertEqual(match.request.arguments['path'], '~/Downloads')

    def test_list_what_is_in_downloads_routes_to_directory_listing(self) -> None:
        for phrase in ('can you list what is in my download folders', "what's in my Downloads folder", 'show me what is inside my downloads'):
            match = self.router.route(phrase)
            self.assertIsNotNone(match, phrase)
            self.assertEqual(match.request.name, 'file.list_dir', phrase)
            self.assertEqual(match.request.arguments['path'], '~/Downloads', phrase)
            self.assertEqual(match.request.arguments['kind'], 'all', phrase)

    def test_create_folder_in_downloads_routes_to_mkdir(self) -> None:
        match = self.router.route('Create a folder called m8-test in my Downloads folder')
        self.assertIsNotNone(match)
        self.assertEqual(match.request.name, 'file.mkdir')
        self.assertEqual(match.request.arguments['path'], '~/Downloads/m8-test')

    def test_create_file_on_desktop_routes_to_write(self) -> None:
        match = self.router.route('create a file on my desktop called honeytest.txt')
        self.assertIsNotNone(match)
        self.assertEqual(match.request.name, 'file.write')
        self.assertTrue(str(match.request.arguments['path']).endswith('Desktop/honeytest.txt'))

    def test_natural_powershell_current_date_is_translated_to_code(self) -> None:
        match = self.router.route('run PowerShell and tell me the current date')
        self.assertIsNotNone(match)
        self.assertEqual(match.request.name, 'powershell.run')
        self.assertIn('Get-Date', match.request.arguments['command'])

    def test_list_folders_in_download_routes_to_folder_filter(self) -> None:
        match = self.router.route('List my folders in my download')
        self.assertIsNotNone(match)
        self.assertEqual(match.request.name, 'file.list_dir')
        self.assertEqual(match.request.arguments['path'], '~/Downloads')
        self.assertEqual(match.request.arguments['kind'], 'folder')

    def test_how_do_you_open_is_not_an_execution_intent(self) -> None:
        self.assertIsNone(self.router.route('How do you open Riot Client?'))

    def test_top_memory_natural_phrases(self) -> None:
        for phrase in ("What's eating my ram right now?", 'What is using most of my RAM right now?', 'What is being used most by my memory?', 'Which process is hogging memory?'):
            match = self.router.route(phrase)
            self.assertIsNotNone(match, phrase)
            self.assertEqual(match.request.name, 'process.top_memory', phrase)

    def test_top_gpu_natural_phrases(self) -> None:
        for phrase in ("What's using the most GPU right now?", "What's eating my GPU?", 'What is using most of my VRAM?', 'But using the most of my GPU right now.'):
            match = self.router.route(phrase)
            self.assertIsNotNone(match, phrase)
            self.assertEqual(match.request.name, 'gpu.top_processes', phrase)

    def test_whisper_bottom_cpu_routes_to_top_cpu(self) -> None:
        match = self.router.route("We're using the bottom of my CPU right now")
        self.assertIsNotNone(match)
        self.assertEqual(match.request.name, 'process.top_cpu')

    def test_battery_percentage_routes_to_measured_tool(self) -> None:
        match = self.router.route('What is my computer battery percentage right now?')
        self.assertIsNotNone(match)
        self.assertEqual(match.request.name, 'system.battery')

    def test_battery_shorthand_routes_to_measured_tool(self) -> None:
        for phrase in ("What's my battery?", 'How much battery do I have?', 'Check my battery', 'Battery?'):
            match = self.router.route(phrase)
            self.assertIsNotNone(match, phrase)
            self.assertEqual(match.request.name, 'system.battery', phrase)

    def test_visible_battery_question_is_not_system_battery_route(self) -> None:
        self.assertIsNone(self.router.route('What battery percentage is shown on this page?'))

class PowerShellRiskTests(unittest.TestCase):

    def test_normal_command_is_not_dangerous(self) -> None:
        self.assertIsNone(dangerous_reason({'command': 'Get-Process'}))
        self.assertIsNone(dangerous_reason({'command': "Get-Date -Format 'dddd, MMMM d, yyyy h:mm tt'"}))

    def test_destructive_command_requires_confirmation(self) -> None:
        self.assertIsNotNone(dangerous_reason({'command': 'Remove-Item C:\\Temp -Recurse -Force'}))
        self.assertIsNotNone(dangerous_reason({'command': 'Start-Process powershell -Verb RunAs'}))
        self.assertIsNotNone(dangerous_reason({'command': 'powershell -EncodedCommand AAAA'}))
if __name__ == '__main__':
    unittest.main()

class ToolAwareSessionTests(unittest.TestCase):

    class Fallback:

        def __init__(self) -> None:
            self.prompts = []

        def stream_response(self, prompt: str, **kwargs):
            self.prompts.append(prompt)
            yield 'fallback'

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        ctx = ToolContext(permissions(), EmergencyStop(MemoryStopStateStore()), ToolAuditLog(self.tmp))
        self.registry = ToolRegistry(ctx)
        for d in (*system_definitions(), *windows_definitions()):
            self.registry.register(d)

    def test_known_voice_intent_uses_tool_not_model(self) -> None:
        from hanni.tools.session import ToolAwareSession
        fallback = self.Fallback()
        session = ToolAwareSession(fallback, self.registry)
        text = ''.join(session.stream_response("What's my CPU usage?"))
        self.assertIn('CPU', text)
        self.assertEqual(fallback.prompts, [])

    def test_unknown_intent_falls_back_to_supervisor(self) -> None:
        from hanni.tools.session import ToolAwareSession
        fallback = self.Fallback()
        session = ToolAwareSession(fallback, self.registry)
        self.assertEqual(''.join(session.stream_response('Tell me a joke')), 'fallback')
        self.assertEqual(fallback.prompts, ['Tell me a joke'])

    def test_unrouted_local_action_never_falls_back_and_claims_execution(self) -> None:
        from hanni.tools.session import ToolAwareSession
        fallback = self.Fallback()
        session = ToolAwareSession(fallback, self.registry)
        reply = ''.join(session.stream_response('Create a folder in some unsupported cloud app'))
        self.assertIn("didn't run", reply.lower())
        self.assertEqual(fallback.prompts, [])

    def test_pending_confirmation_can_be_approved_on_next_turn(self) -> None:
        from hanni.tools.base import ToolDefinition, ToolResult
        from hanni.tools.session import ToolAwareSession
        calls = []

        def handler(args, context, request):
            calls.append(request.confirmed)
            return ToolResult('test.risky', True, 'done')
        self.registry.register(ToolDefinition('test.risky', 'test', 3, 3, {}, {}, handler))

        class Router:

            def route(self, text):
                from hanni.tools.router import VoiceToolMatch
                return VoiceToolMatch(ToolRequest('test.risky', {}, source='voice'), 'risky') if text == 'do risky thing' else None
        fallback = self.Fallback()
        session = ToolAwareSession(fallback, self.registry, Router())
        first = ''.join(session.stream_response('do risky thing'))
        self.assertIn('explicit confirmation', first)
        second = ''.join(session.stream_response('You can do that.'))
        self.assertEqual(second, 'done')
        self.assertEqual(calls, [True])

    def test_unrelated_turn_clears_pending_confirmation(self) -> None:
        from hanni.tools.base import ToolDefinition, ToolResult
        from hanni.tools.session import ToolAwareSession
        self.registry.register(ToolDefinition('test.risky2', 'test', 3, 3, {}, {}, lambda a, c, r: ToolResult('test.risky2', True, 'done')))

        class Router:

            def route(self, text):
                from hanni.tools.router import VoiceToolMatch
                return VoiceToolMatch(ToolRequest('test.risky2', {}, source='voice'), 'risky') if text == 'do risky thing' else None
        fallback = self.Fallback()
        session = ToolAwareSession(fallback, self.registry, Router())
        _ = ''.join(session.stream_response('do risky thing'))
        self.assertEqual(''.join(session.stream_response('what time is it')), 'fallback')
        self.assertEqual(''.join(session.stream_response('yes')), 'fallback')

class ToolPermissionConversationTests(unittest.TestCase):

    def test_plain_delete_request_is_not_misclassified_as_permission_talk(self) -> None:
        from hanni.tools.session import ToolAwareSession
        tmp = Path(tempfile.mkdtemp())
        ctx = ToolContext(permissions(), EmergencyStop(MemoryStopStateStore()), ToolAuditLog(tmp))
        registry = ToolRegistry(ctx)

        class Fallback:

            def stream_response(self, prompt, **kwargs):
                yield 'fallback'
        reply = ''.join(ToolAwareSession(Fallback(), registry).stream_response('Permanently delete hanni-m8-lab folder'))
        self.assertNotIn("permissions haven't changed", reply.lower())

    def test_permission_talk_cannot_change_tool_policy_via_llm(self) -> None:
        from hanni.tools.session import ToolAwareSession
        tmp = Path(tempfile.mkdtemp())
        ctx = ToolContext(permissions(), EmergencyStop(MemoryStopStateStore()), ToolAuditLog(tmp))
        registry = ToolRegistry(ctx)

        class Fallback:

            def __init__(self):
                self.prompts = []

            def stream_response(self, prompt, **kwargs):
                self.prompts.append(prompt)
                yield 'I changed your permissions.'
        fallback = Fallback()
        session = ToolAwareSession(fallback, registry)
        reply = ''.join(session.stream_response("You shouldn't have deletion privileges right now."))
        self.assertIn("haven't changed", reply)
        self.assertEqual(fallback.prompts, [])

class M804RouterRegressionTests(unittest.TestCase):

    def test_normal_battery_question_still_routes_to_system_battery(self) -> None:
        match = VoiceToolRouter().route("What's my battery percentage?")
        self.assertIsNotNone(match)
        self.assertEqual(match.request.name, 'system.battery')

class M804ToolConversationRegressionTests(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        ctx = ToolContext(permissions(), EmergencyStop(MemoryStopStateStore()), ToolAuditLog(self.tmp))
        self.registry = ToolRegistry(ctx)

    def test_how_would_you_open_reports_capability_without_execution(self) -> None:
        from hanni.tools.session import ToolAwareSession

        class Fallback:

            def __init__(self):
                self.calls = []

            def stream_response(self, prompt, **kwargs):
                self.calls.append(prompt)
                yield 'fallback'
        fallback = Fallback()
        session = ToolAwareSession(fallback, self.registry)
        reply = ''.join(session.stream_response('How would you open Riot Client?'))
        self.assertIn('app-launch tool', reply)
        self.assertIn("won't launch", reply)
        self.assertEqual(fallback.calls, [])

    def test_unsupported_wallpaper_change_does_not_fall_through_to_fake_action(self) -> None:
        from hanni.tools.session import ToolAwareSession

        class Fallback:

            def __init__(self):
                self.calls = []

            def stream_response(self, prompt, **kwargs):
                self.calls.append(prompt)
                yield 'I changed it'
        fallback = Fallback()
        session = ToolAwareSession(fallback, self.registry)
        reply = ''.join(session.stream_response('Change my Windows wallpaper to a picture of Mars.'))
        self.assertIn("didn't run", reply.lower())
        self.assertEqual(fallback.calls, [])

    def test_resource_tool_can_feed_grounded_explanation(self) -> None:
        from hanni.tools.router import VoiceToolMatch
        from hanni.tools.session import ToolAwareSession
        from hanni.tools.base import ToolDefinition, ToolResult
        self.registry.register(ToolDefinition('process.top_memory', 'memory', 0, 0, {'limit': int}, {}, lambda a, c, r: ToolResult('process.top_memory', True, 'llama.exe is using 13 GB.', {'rows': []})))

        class Router:

            def route(self, text):
                return VoiceToolMatch(ToolRequest('process.top_memory', {'limit': 5}), 'memory')

        class Fallback:

            def __init__(self):
                self.prompts = []

            def stream_response(self, prompt, **kwargs):
                self.prompts.append(prompt)
                yield 'That is high for one process but can be normal for a loaded local model.'
        fallback = Fallback()
        session = ToolAwareSession(fallback, self.registry, Router())
        reply = ''.join(session.stream_response("Tell me what's using the most RAM and explain whether that's unusual."))
        self.assertIn('llama.exe is using 13 GB', reply)
        self.assertIn('can be normal', reply)
        self.assertIn('AUTHORITATIVE LOCAL TOOL RESULT', fallback.prompts[0])
