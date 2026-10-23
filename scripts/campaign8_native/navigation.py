"""Original visible navigation controls discovered from the current source metadata."""
from __future__ import annotations
from pathlib import Path
import re

def source_routes():
    source = (Path(__file__).resolve().parents[2] / 'frontend/src/workspace.tsx').read_text(encoding='utf8')
    section = source.split('> = {', 1)[1].split('\n};', 1)[0]
    return {match[0].strip('"'): {'label': match[1], 'group': match[2]} for match in re.findall('([\\w-]+|"[\\w-]+"):\\s*\\{\\s*label:\\s*"([^"]+)",\\s*group:\\s*"([^"]+)"', section)}

def navigate(session, route):
    if route not in session.report['declared_routes']:
        raise ValueError('Unknown original route.')
    metadata = source_routes()[route]
    steps = []
    opener = session.page.get_by_role('button', name='Open navigation', exact=True)
    if opener.is_visible():
        steps.append(session.execute({'id': route + '-open-navigation', 'action': 'click', 'role': 'button', 'name': 'Open navigation'}))
    sidebar = session.page.locator('aside[aria-label="Workspace navigation"]')
    target = route
    if route == 'mcp':
        target = 'settings'
    if target not in {'settings', 'notifications'}:
        group = sidebar.get_by_role('button', name=metadata['group'], exact=True)
        if group.get_attribute('aria-expanded') != 'true':
            group.click(timeout=5000)
            session.page.wait_for_timeout(120)
            steps.append({'input': {'action': 'click', 'scope': 'Original Primary navigation', 'name': metadata['group']}, 'dom': session.dom()})
    button = sidebar.get_by_role('button', name=source_routes()[target]['label'], exact=True)
    button.click(timeout=5000)
    session.page.wait_for_timeout(300)
    steps.append({'input': {'action': 'click', 'scope': 'Original Workspace navigation', 'name': source_routes()[target]['label']}, 'dom': session.dom()})
    if route == 'mcp':
        steps.append(session.execute({'id': 'settings-open-mcp', 'action': 'click', 'role': 'button', 'name': 'MCP Hub'}))
    observed = session.page.evaluate("() => ({hash:location.hash,scrolls:[...document.querySelectorAll('main,.workspace-main,.workspace-content,.screen-content')].map(e=>({tag:e.tagName,class:e.className,top:e.scrollTop,height:e.scrollHeight,clientHeight:e.clientHeight}))})")
    return {'route': route, 'source_metadata': metadata, 'input_layer': 'Original visible DOM navigation controls', 'steps': steps, 'observed_before_capture_scroll_setup': observed}

def reset_capture_scroll(session):
    return session.page.evaluate("() => {const es=[...document.querySelectorAll('main,.workspace-main,.workspace-content,.screen-content')]; const before=es.map(e=>({class:e.className,top:e.scrollTop}));es.forEach(e=>e.scrollTop=0);return {method:'Explicit primary-content screenshot setup',before,after:es.map(e=>({class:e.className,top:e.scrollTop}))};}")
