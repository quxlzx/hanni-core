"""Actual native font comparisons using temporary CSS variable overrides only."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import winreg
from scripts.campaign8_native.session import NativeSession, digest
FAMILIES = ['Geist Sans', 'Segoe UI', 'Segoe UI Variable', 'Arial', 'Calibri', 'Tahoma', 'Verdana']
VIEWS = [('home', [1366, 860]), ('cluster', [900, 650]), ('memory', [900, 650])]

def installed_fonts():
    result = []
    for hive, label in [(winreg.HKEY_LOCAL_MACHINE, 'machine'), (winreg.HKEY_CURRENT_USER, 'user')]:
        try:
            with winreg.OpenKey(hive, 'SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Fonts') as key:
                for index in range(winreg.QueryInfoKey(key)[1]):
                    name, value, kind = winreg.EnumValue(key, index)
                    if any((name.lower().startswith(f.lower()) for f in FAMILIES[1:])):
                        result.append({'scope': label, 'name': name, 'file': value, 'type': kind})
        except FileNotFoundError:
            pass
    return result
METRICS = "() => ({\n  text: document.body.innerText,\n  rootVariable:getComputedStyle(document.documentElement).getPropertyValue('--sans'),\n  elements:[...document.querySelectorAll('h1,h2,h3,p,button,input,th,td')].slice(0,180).map(e=>{\n    const s=getComputedStyle(e);return {tag:e.tagName,text:(e.innerText||e.placeholder||'').trim(),\n      fontFamily:s.fontFamily,fontSize:s.fontSize,fontWeight:s.fontWeight,lineHeight:s.lineHeight,\n      letterSpacing:s.letterSpacing};})})"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import psutil
    ready = json.loads(args.ready.read_text(encoding='utf8'))
    assert ready['evidence_class'] == 'CONTROLLED'
    assert psutil.Process(ready['pid']).create_time() == ready['create_time']
    with NativeSession(url=ready['url'], output=args.output) as session:
        session.report['backend_receipt'] = {k: ready[k] for k in ['url', 'pid', 'create_time', 'scope', 'evidence_class']}
        session.report['font_comparison'] = {'families': FAMILIES, 'installed_font_registry': installed_fonts(), 'method': 'Temporary --sans on original native WebView; sizes/weights/line height/mono unchanged', 'views': [], 'original_variable_restored': False}
        original = session.page.evaluate("() => ({value:document.documentElement.style.getPropertyValue('--sans'),priority:document.documentElement.style.getPropertyPriority('--sans')})")
        before_assets = session.report['assets'].copy()
        try:
            for route, size in VIEWS:
                session.execute({'id': route + '-route', 'action': 'route', 'route': route})
                session.execute({'id': route + '-size', 'action': 'resize', 'size': size})
                baseline = None
                for family in FAMILIES:
                    session.check_budget()
                    session.page.evaluate("family => document.documentElement.style.setProperty('--sans', JSON.stringify(family)+', Arial, sans-serif')", family)
                    session.page.evaluate('() => document.fonts.ready')
                    session.page.wait_for_timeout(180)
                    metrics = session.page.evaluate(METRICS)
                    text = metrics.pop('text')
                    text_hash = hashlib.sha256(text.encode('utf8')).hexdigest()
                    invariant = [{k: v for k, v in row.items() if k not in {'fontFamily', 'text'}} for row in metrics['elements']]
                    if baseline is None:
                        baseline = {'text': text, 'invariant': invariant}
                    slug = family.lower().replace(' ', '-')
                    label = route + '-' + 'x'.join(map(str, size)) + '-' + slug
                    comparison = {'route': route, 'family': family, 'requested_physical_size': size, 'actual_window': session.window_state(session.main), 'metrics': metrics, 'actual_platform_fonts': session.platform_fonts(), 'body_text_sha256': text_hash, 'same_exact_text_as_current_font': text == baseline['text'], 'same_style_metrics_as_current_font': invariant == baseline['invariant'], 'text_differences': [] if text == baseline['text'] else {'scope': 'Original live host telemetry changes were retained; no measurements frozen', 'baseline': baseline['text'], 'current': text}, 'screenshot': session.capture(label)}
                    session.report['font_comparison']['views'].append(comparison)
                    session.save()
        finally:
            session.page.evaluate("original => {const s=document.documentElement.style; if(original.value)s.setProperty('--sans',original.value,original.priority);else s.removeProperty('--sans');}", original)
            session.report['font_comparison']['original_variable_restored'] = session.page.evaluate("original => document.documentElement.style.getPropertyValue('--sans')===original.value", original)
            current_assets = {path: digest(Path(__file__).resolve().parents[2] / path) for path in before_assets}
            session.report['font_comparison']['served_assets_unchanged'] = current_assets == before_assets
            session.report['font_comparison']['assets_after'] = current_assets
            session.save()
        session.report['complete'] = True
if __name__ == '__main__':
    main()
