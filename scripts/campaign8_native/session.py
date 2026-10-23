"""One bounded actual HANNI Windows/WebView2 session with disposable state."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time
from uuid import uuid4
from scripts.campaign8_native.owned_window import OwnedProcess, capture_owned_window, wait_owned_window
ROOT = Path(__file__).resolve().parents[2]
DOM_INVENTORY = "() => ({url:location.href,title:document.title,\n  viewport:{width:innerWidth,height:innerHeight,devicePixelRatio},\n  visibleText:(()=>{if(!document.createTreeWalker)return '';let parts=[],length=0,count=0;\n    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);\n    for(let node;(node=walker.nextNode())&&count++<2000;){const text=node.textContent.trim(),parent=node.parentElement;\n      if(!text||!parent||['SCRIPT','STYLE','NOSCRIPT'].includes(parent.tagName))continue;\n      const style=getComputedStyle(parent);if(style.visibility==='hidden'||style.display==='none')continue;\n      const range=document.createRange();range.selectNodeContents(node);const rects=[...range.getClientRects()];\n      const visible=rects.length&&rects.every(r=>{if(r.width<=0||r.height<=0||r.left<0||r.top<0||r.right>innerWidth||r.bottom>innerHeight)return false;\n        for(let p=parent;p;p=p.parentElement){const s=getComputedStyle(p),b=p.getBoundingClientRect();\n          if(s.visibility==='hidden'||s.display==='none'||s.opacity==='0')return false;\n          if(/(auto|scroll|hidden|clip)/.test(s.overflowX)&&(r.left<b.left||r.right>b.right))return false;\n          if(/(auto|scroll|hidden|clip)/.test(s.overflowY)&&(r.top<b.top||r.bottom>b.bottom))return false;}\n        const hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return hit===parent||parent.contains(hit);});\n      range.detach();if(visible){parts.push(text);length+=text.length+1;if(length>=12000)break;}}\n    return parts.join('\\n').slice(0,12000);})(),\n  fonts:[...new Set([...document.querySelectorAll('h1,h2,h3,button,input,nav')]\n    .map(e=>getComputedStyle(e).fontFamily))],\n  controls:[...document.querySelectorAll('button,a,input,select,textarea,[role=button],[role=tab],[role=checkbox]')]\n    .map((e,index)=>{let r=e.getBoundingClientRect(),style=getComputedStyle(e);\n      let tag=e.tagName.toLowerCase(),hasValue=['input','textarea','select'].includes(tag);\n      let fieldIdentity=[e.id,e.name,e.getAttribute('aria-label'),e.getAttribute('autocomplete'),\n        ...[...(e.labels||[])].map(label=>label.textContent)].filter(Boolean).join(' ');\n      let sensitive=hasValue&&(e.type==='password'||\n        /password|passwd|secret|credential|authorization|api[-_\\s]*(key|token)|access[-_\\s]*token|refresh[-_\\s]*token|bearer|\\btoken\\b/i.test(fieldIdentity));\n      return {\n      index,tag:e.tagName.toLowerCase(),role:e.getAttribute('role'),\n      name:e.getAttribute('aria-label')||e.getAttribute('title')||(e.innerText||'').trim().slice(0,160),\n      inputType:e.getAttribute('type'),visible:r.width>0&&r.height>0&&style.visibility!=='hidden',\n      enabled:!e.disabled,ariaDisabled:e.getAttribute('aria-disabled'),\n      checked:e.checked??null,ariaCurrent:e.getAttribute('aria-current'),\n      ariaSelected:e.getAttribute('aria-selected'),tabIndex:e.tabIndex,\n      readOnly:hasValue?e.readOnly??null:null,\n      value:hasValue&&!sensitive?e.value:null,valueRedacted:sensitive,\n      selectedOptionText:tag==='select'&&!sensitive?[...e.selectedOptions].map(option=>option.textContent):null,\n      selectionStart:hasValue&&!sensitive&&typeof e.selectionStart==='number'?e.selectionStart:null,\n      selectionEnd:hasValue&&!sensitive&&typeof e.selectionEnd==='number'?e.selectionEnd:null,\n      href:e.tagName==='A'?e.getAttribute('href'):null,\n      rect:{x:r.x,y:r.y,width:r.width,height:r.height}}}),\n  dialogs:[...document.querySelectorAll('dialog')].map(e=>({open:e.open,\n    label:e.getAttribute('aria-label')||e.querySelector('h1,h2,h3')?.textContent||''})),\n  focused:{tag:document.activeElement?.tagName,role:document.activeElement?.getAttribute('role'),\n    name:document.activeElement?.getAttribute('aria-label')||document.activeElement?.textContent?.slice(0,120)},\n  horizontalOverflow:document.documentElement.scrollWidth>innerWidth,\n  bodyWidth:document.body.scrollWidth})"

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def connect_native_cdp(chromium, endpoint):
    """Attach without changing the native browser's download/context defaults."""
    return chromium.connect_over_cdp(endpoint, timeout=1000, no_defaults=True)

def validated_upload(item):
    allowed = {'id', 'action', 'selector', 'fixture_id', 'view', 'settle_ms'}
    if set(item) - allowed or item.get('selector') != 'dialog input[type="file"]' or item.get('fixture_id') != 'mcp-disabled-config' or (item.get('view') not in {None, 'main'}):
        raise ValueError('Only the fixed synthetic MCP fixture may enter its original main-dialog file input.')
    from scripts.campaign8_ui.upload import upload_fixture
    fixture = upload_fixture(item['fixture_id'])
    if fixture.get('name') != 'campaign8-controlled-disabled-mcp.json' or fixture.get('mimeType') != 'application/json' or type(fixture.get('buffer')) is not bytes or (len(fixture['buffer']) > 256 * 1024):
        raise ValueError('The frozen synthetic upload metadata is invalid.')
    document = json.loads(fixture['buffer'])
    configs = document.get('mcpServers', {})
    if set(configs) != {'Controlled native file integration'} or configs['Controlled native file integration'].get('auto_connect') is not False:
        raise ValueError('The fixed import must explicitly prevent automatic connection.')
    return fixture

class NativeSession:

    def __init__(self, *, url, output, executable=None, maximum_seconds=600, minimum_free_ram_bytes=400 * 1024 ** 2, evidence_class='CONTROLLED', state_directory=None):
        from desktop.main import validate_url
        self.url = validate_url(url)
        self.output = Path(output).resolve()
        if not self.output.is_relative_to((ROOT / 'data/campaign8-native').resolve()):
            raise ValueError('Native outputs must be in the campaign-owned output directory.')
        if self.output.exists():
            raise FileExistsError('Preserve previous native session evidence.')
        self.state_directory = Path(state_directory).resolve() if state_directory is not None else None
        if self.state_directory is not None and (not self.state_directory.is_relative_to((ROOT / 'data/campaign8-native').resolve()) or not self.state_directory.is_dir() or (not (self.state_directory / 'window.json').is_file())):
            raise ValueError('Reused native state must be an existing campaign-owned disposable directory.')
        self.executable = Path(executable or ROOT / 'dist/HANNI OS/HANNI OS.exe').resolve()
        self.maximum_seconds = maximum_seconds
        self.minimum_free_ram_bytes = minimum_free_ram_bytes
        self.title = 'HANNI OS Campaign 8 ' + uuid4().hex[:12]
        self.evidence_class = evidence_class
        self.process = self.main = self.mini = self.playwright = self.browser = self.log = None
        self.page = self.mini_page = None
        self.started = None
        self.records = []
        self.report = {'scope': 'Actual packaged Windows WebView2; disposable original backend with explicitly controlled dependencies', 'evidence_class': evidence_class, 'headless': False, 'native_browser_preview': False, 'actions': self.records, 'screenshots': [], 'javascript_errors': [], 'network': [], 'resources': [], 'complete': False, 'owned_native_cleanup': False}

    def save(self):
        (self.output / 'RESULTS.json').write_text(json.dumps(self.report, indent=2, allow_nan=False) + '\n', encoding='utf8', newline='\n')

    def check_budget(self):
        import psutil
        memory = psutil.virtual_memory()
        sample = {'at': time.time(), 'available_ram_bytes': memory.available, 'used_percent': memory.percent}
        if self.process is not None:
            try:
                sample['owned_process_rss_bytes'] = psutil.Process(self.process.pid).memory_info().rss
                sample['owned_tree_rss_bytes'] = sample['owned_process_rss_bytes'] + sum((p.memory_info().rss for p in psutil.Process(self.process.pid).children(recursive=True) if p.is_running()))
            except psutil.Error:
                pass
        self.report['resources'].append(sample)
        if memory.available < self.minimum_free_ram_bytes:
            raise RuntimeError('Owned native QA stopped at the minimum free RAM boundary.')
        if self.started is not None and time.monotonic() - self.started > self.maximum_seconds:
            raise TimeoutError('Owned native QA session reached its bounded time limit.')
        return sample

    def __enter__(self):
        import ctypes
        import psutil
        from playwright.sync_api import sync_playwright
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        self.check_budget()
        self.output.mkdir(parents=True, exist_ok=False)
        state = self.state_directory or self.output / 'native-state'
        if self.state_directory is None:
            state.mkdir()
            (state / 'window.json').write_text(json.dumps({'width': 1100, 'height': 700, 'x': 0, 'y': 0, 'maximized': False, 'close_to_tray': False, 'minimize_to_tray': False, 'notifications': False, 'mini_pinned': False, 'mini_shortcut': 'Ctrl+Shift+H'}) + '\n', encoding='utf8', newline='\n')
        self.report['native_state_directory'] = str(state)
        self.report['existing_disposable_state_reused'] = self.state_directory is not None
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        command = [str(self.executable), '--url', self.url, '--attach-only', '--state-dir', str(state), '--debug-port', str(port), '--title', self.title]
        self.started = time.monotonic()
        self.log = (self.output / 'native-launch.log').open('w', encoding='utf8')
        self.process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT)
        created = psutil.Process(self.process.pid).create_time()
        self.identity = OwnedProcess(self.process.pid, created, str(self.executable))
        self.report.update(started_at=datetime.now(timezone.utc).isoformat(), argv=command, pid=self.process.pid, create_time=created, executable_sha256=digest(self.executable), debug_port=port, title=self.title, source_sha256=digest(ROOT / 'desktop/main.py'), assets={str(p.relative_to(ROOT)): digest(p) for p in [ROOT / 'src/hanni/dashboard/static/app.js', ROOT / 'src/hanni/dashboard/static/style.css']}, physical_windows_system_dpi=ctypes.windll.user32.GetDpiForSystem())
        self.save()
        try:
            self.main = wait_owned_window(self.identity, self.title)
            self.mini = wait_owned_window(self.identity, 'HANNI Mini')
            self.playwright = sync_playwright().start()
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                self.check_budget()
                try:
                    self.browser = connect_native_cdp(self.playwright.chromium, f'http://127.0.0.1:{port}')
                    break
                except Exception:
                    time.sleep(0.2)
            if self.browser is None:
                raise RuntimeError('Owned native WebView2 CDP did not become available.')
            self.report['cdp_attachment'] = {'no_defaults': True, 'scope': 'Preserve original native browser context/download defaults; no policy override.'}
            for context in self.browser.contexts:
                context.on('page', self.observe_page)
                for page in context.pages:
                    self.observe_page(page)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                pages = [p for c in self.browser.contexts for p in c.pages]
                self.page = next((p for p in pages if p.url.startswith(self.url + '/') and '?view=mini' not in p.url), None)
                self.mini_page = next((p for p in pages if p.url == self.url + '/?view=mini'), None)
                if self.page is not None and self.mini_page is not None:
                    break
                self.browser.new_browser_cdp_session().send('Target.getTargets')
                time.sleep(0.1)
            if self.page is None or self.mini_page is None:
                raise RuntimeError('Original main and Mini documents did not connect.')
            self.page.wait_for_load_state('domcontentloaded')
            contract = self.page.request.get(self.url + '/api/workspace').json()
            declared = contract.get('screens')
            if not isinstance(declared, list) or not declared or any((not isinstance(s, str) for s in declared)):
                raise RuntimeError('Original backend did not supply its declared route inventory.')
            self.report['declared_routes'] = declared
            self.check_budget()
            self.save()
            return self
        except BaseException:
            self.__exit__(*__import__('sys').exc_info())
            raise

    def observe_page(self, page):
        page.on('pageerror', lambda error: self.report['javascript_errors'].append(str(error)[:300]))
        page.on('response', lambda response: self.report['network'].append({'method': response.request.method, 'path': response.url.removeprefix(self.url), 'same_origin': response.url.startswith(self.url + '/'), 'status': response.status}))

    def window_state(self, window):
        import ctypes
        import win32gui
        window.verify()
        return {'hwnd': window.hwnd, 'pid': self.identity.pid, 'create_time': self.identity.create_time, 'title': window.title, 'class': window.window_class, 'visible': bool(win32gui.IsWindowVisible(window.hwnd)), 'minimized': bool(win32gui.IsIconic(window.hwnd)), 'maximized': bool(ctypes.windll.user32.IsZoomed(window.hwnd)), 'window_rect': list(win32gui.GetWindowRect(window.hwnd)), 'client_rect': list(win32gui.GetClientRect(window.hwnd)), 'dpi': ctypes.windll.user32.GetDpiForWindow(window.hwnd), 'topmost': bool(win32gui.GetWindowLong(window.hwnd, -20) & 8)}

    def capture(self, name, *, mini=False):
        self.check_budget()
        result = capture_owned_window(self.mini if mini else self.main, self.output / 'screenshots' / (name + '.png'))
        result['evidence_class'] = self.evidence_class
        self.report['screenshots'].append(result)
        self.save()
        return result

    def dom(self, *, mini=False):
        self.check_budget()
        return (self.mini_page if mini else self.page).evaluate(DOM_INVENTORY)

    def platform_fonts(self, *, mini=False):
        """Actual native WebView renderer font identities, not CSS assumptions."""
        page = self.mini_page if mini else self.page
        cdp = page.context.new_cdp_session(page)
        try:
            cdp.send('DOM.enable')
            cdp.send('CSS.enable')
            root = cdp.send('DOM.getDocument')['root']['nodeId']
            result = {}
            for selector in ['body', 'h1', 'button', 'input']:
                node = cdp.send('DOM.querySelector', {'nodeId': root, 'selector': selector})['nodeId']
                if node:
                    result[selector] = cdp.send('CSS.getPlatformFontsForNode', {'nodeId': node})['fonts']
            return result
        finally:
            cdp.detach()

    def native(self, action, *, mini=False, size=None):
        import win32con
        import win32gui
        window = self.mini if mini else self.main
        window.verify()
        if action == 'resize':
            if not isinstance(size, list) or len(size) != 2 or any((type(n) is not int or not 420 <= n <= 4096 for n in size)):
                raise ValueError('Provide a bounded actual Windows outer-window size.')
            win32gui.ShowWindow(window.hwnd, win32con.SW_RESTORE)
            win32gui.SetWindowPos(window.hwnd, win32con.HWND_TOP, 0, 0, size[0], size[1], 0)
        elif action in {'minimize', 'maximize', 'restore', 'show', 'hide'}:
            modes = {'minimize': win32con.SW_MINIMIZE, 'maximize': win32con.SW_MAXIMIZE, 'restore': win32con.SW_RESTORE, 'show': win32con.SW_SHOW, 'hide': win32con.SW_HIDE}
            win32gui.ShowWindow(window.hwnd, modes[action])
        elif action == 'focus':
            win32gui.SetForegroundWindow(window.hwnd)
        else:
            raise ValueError('Unsupported native-window action.')
        time.sleep(0.15)
        return self.window_state(window)

    def execute(self, item):
        """Input-only action execution: no expected answers or scoring logic."""
        self.check_budget()
        page = self.mini_page if item.get('view') == 'mini' else self.page
        window = self.mini if item.get('view') == 'mini' else self.main
        before = self.window_state(window)
        action = item['action']
        result = None
        if action == 'route':
            route = item['route']
            if not isinstance(route, str) or route not in self.report['declared_routes']:
                raise ValueError('Route must be in the original backend declared inventory.')
            page.evaluate('(route)=>location.hash=route', route)
            page.wait_for_timeout(item.get('settle_ms', 500))
            result = self.dom(mini=item.get('view') == 'mini')
        elif action == 'capture':
            result = self.capture(item['id'], mini=item.get('view') == 'mini')
        elif action in {'resize', 'minimize', 'maximize', 'restore', 'show', 'hide', 'focus'}:
            result = self.native(action, mini=item.get('view') == 'mini', size=item.get('size'))
        elif action == 'mini_bridge':
            method = item['method']
            if method not in {'get_state', 'dismiss', 'pin', 'expand', 'configure_hotkey'}:
                raise ValueError('Only original Mini window methods are exposed.')
            result = page.evaluate('async ({method,args})=>await window.pywebview.api[method](...args)', {'method': method, 'args': item.get('arguments', [])})
        elif action == 'application_menu':
            from scripts.campaign8_native.menus import application_menu
            if item['name'].startswith('Start Assistant'):
                raise ValueError('Starting an assistant is excluded from the generic QA executor.')
            result = application_menu(self.main, item['name'])
        elif action == 'tray_menu':
            from scripts.campaign8_native.menus import tray_menu
            if item.get('name', '').startswith('Start Assistant'):
                raise ValueError('Starting an assistant is excluded from the generic QA executor.')
            result = tray_menu(self.identity, item.get('name'))
        elif action == 'tray_restore':
            from scripts.campaign8_native.menus import tray_restore
            result = tray_restore(self.identity)
        elif action == 'upload_fixture':
            fixture = validated_upload(item)
            page.locator(item['selector']).set_input_files(fixture, timeout=5000)
            page.wait_for_timeout(item.get('settle_ms', 250))
            result = {'input_layer': 'Original DOM file input change; no physical OS picker or disk file access', 'fixture_id': item['fixture_id'], 'filename': fixture['name'], 'bytes': len(fixture['buffer']), 'sha256': hashlib.sha256(fixture['buffer']).hexdigest(), 'dom': self.dom()}
        elif action in {'click', 'fill', 'check', 'select', 'press'}:
            if 'role' in item:
                locator = page.get_by_role(item['role'], name=item.get('name'), exact=True)
            else:
                locator = page.locator(item['selector'])
            locator = locator.nth(item.get('index', 0))
            if action == 'click':
                locator.click(timeout=item.get('timeout_ms', 5000))
            elif action == 'fill':
                locator.fill(item['value'], timeout=5000)
            elif action == 'check':
                deadline = time.monotonic() + 5
                if locator.is_checked(timeout=5000) != item['checked']:
                    locator.click(timeout=5000)
                    while locator.is_checked(timeout=1000) != item['checked']:
                        if time.monotonic() >= deadline:
                            raise TimeoutError('Original asynchronous checkbox did not reach its requested state within five seconds.')
                        page.wait_for_timeout(50)
            elif action == 'select':
                locator.select_option(item['value'], timeout=5000)
            elif action == 'press':
                locator.press(item['key'], timeout=5000)
            page.wait_for_timeout(item.get('settle_ms', 250))
            result = self.dom(mini=item.get('view') == 'mini')
        elif action == 'inventory':
            result = self.dom(mini=item.get('view') == 'mini')
        elif action == 'font_identity':
            result = self.platform_fonts(mini=item.get('view') == 'mini')
        else:
            raise ValueError('Unsupported native executor action.')
        receipt = {'id': item['id'], 'input': item, 'evidence_class': self.evidence_class, 'before': before, 'after': self.window_state(window), 'result': result}
        self.records.append(receipt)
        self.check_budget()
        self.save()
        return receipt

    def __exit__(self, kind, error, traceback):
        if error is not None:
            self.report['error'] = {'type': type(error).__name__, 'message': str(error)[:500]}
        if self.process is not None:
            import win32con
            import win32gui
            if self.process.poll() is None:
                self.identity.verify()
                if self.main is not None:
                    if win32gui.IsWindow(self.main.hwnd):
                        self.main.verify()
                        win32gui.PostMessage(self.main.hwnd, win32con.WM_CLOSE, 0, 0)
                try:
                    self.process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self.identity.verify()
                    self.process.terminate()
                    self.process.wait(timeout=10)
            self.report['owned_native_cleanup'] = self.process.poll() is not None
            self.report['native_exit_code'] = self.process.returncode
        if self.browser is not None:
            try:
                self.browser.close()
            except Exception:
                pass
        if self.playwright is not None:
            self.playwright.stop()
        if self.log is not None:
            self.log.close()
        if self.output.exists():
            self.report['finished_at'] = datetime.now(timezone.utc).isoformat()
            self.save()
