"""Independent WAV integrity/content audit, without playback or recognition."""
from __future__ import annotations
import collections
import hashlib
import json
import math
from pathlib import Path
import wave
import numpy as np

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def longest_zero_run(values):
    zero = values == 0
    if not np.any(zero):
        return 0
    edges = np.diff(np.r_[False, zero, False].astype(np.int8))
    return int(np.max(np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1)))

def audit(corpus, destination):
    corpus, destination = (Path(corpus).resolve(), Path(destination).resolve())
    destination.mkdir(parents=True, exist_ok=False)
    manifest_path, reference_path = (corpus / 'manifest.json', corpus / 'references.json')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    refs = {row['id']: row for row in json.loads(reference_path.read_text(encoding='utf-8'))['samples']}
    rows, previews = ([], [])
    for row in manifest['samples']:
        path = (corpus / row['wav_path']).resolve()
        if not path.is_relative_to(corpus):
            raise ValueError('Corpus path escaped its owned directory')
        with wave.open(str(path), 'rb') as handle:
            actual = dict(channels=handle.getnchannels(), sample_rate=handle.getframerate(), sample_width=handle.getsampwidth(), frames=handle.getnframes(), compression=handle.getcomptype())
            values = np.frombuffer(handle.readframes(handle.getnframes()), dtype='<i2')
        actual['sha256'] = sha(path)
        actual['seconds'] = actual['frames'] / actual['sample_rate']
        actual['pcm_peak'] = int(np.max(np.abs(values.astype(np.int32)))) if values.size else 0
        actual['pcm_rms'] = float(np.sqrt(np.mean(values.astype(np.float64) ** 2))) if values.size else 0
        actual['clipped_samples'] = int(np.sum((values == -32768) | (values == 32767)))
        actual['leading_pad_silent'] = bool(np.all(values[:8000] == 0))
        actual['trailing_pad_silent'] = bool(np.all(values[-8000:] == 0))
        core = values[8000:-8000]
        actual['nonzero_core_samples'] = int(np.count_nonzero(core))
        actual['longest_interior_zero_seconds'] = longest_zero_run(core) / actual['sample_rate']
        checks = {key: actual[key] == row[key] for key in ('channels', 'sample_rate', 'sample_width', 'frames', 'sha256', 'pcm_peak')}
        checks.update(seconds=math.isclose(actual['seconds'], row['seconds'], abs_tol=1e-10), rms=math.isclose(actual['pcm_rms'], row['pcm_rms'], rel_tol=1e-12), mono_pcm16_16k=actual['channels'] == 1 and actual['sample_width'] == 2 and (actual['sample_rate'] == 16000) and (actual['compression'] == 'NONE'), nonempty_speech=actual['nonzero_core_samples'] > 0, actual_padding=actual['leading_pad_silent'] and actual['trailing_pad_silent'], reference_identity=row['id'] in refs, metadata_condition=row['condition'] == refs[row['id']]['condition'], metadata_seed=row['seed'] == refs[row['id']]['seed'])
        if row['condition'] == 'low_amplitude':
            checks['attenuated_peak_bound'] = actual['pcm_peak'] <= 2622
        rows.append(dict(id=row['id'], condition=row['condition'], actual=actual, checks=checks, passed=all(checks.values())))
        if row['category'] == 'direct_wake' and len(previews) < 5:
            previews.append((row['id'], row['condition'], values.copy()))
    from html import escape
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="880" viewBox="0 0 1200 880">', '<rect width="1200" height="880" fill="white"/>', '<text x="65" y="28" font-size="17">Synthetic PCM waveforms; no acoustic listening or recognition</text>']
    for index, (cid, condition, values) in enumerate(previews):
        top = 70 + index * 155
        svg.append(f'<text x="65" y="{top - 13}" font-size="13">{escape(cid)}: {escape(condition)}</text>')
        for offset in (0, 52, 104):
            svg.append(f'<path d="M65 {top + offset} H1160" stroke="#ddd"/>')
        stride = max(1, len(values) // 5000)
        points = ' '.join((f'{65 + 1095 * i / max(1, len(values) - 1):.2f},{top + 52 - 52 * int(values[i]) / 32768:.2f}' for i in range(0, len(values), stride)))
        svg.append(f'<polyline points="{points}" stroke="#234c68" fill="none" stroke-width="0.6"/>')
        svg.append(f'<text x="65" y="{top + 125}" font-size="12">0 s</text><text x="1090" y="{top + 125}" font-size="12">{len(values) / 16000:.3f} s</text>')
    svg.append('</svg>')
    svg_text = '\n'.join(svg)
    (destination / 'SYNTHETIC_WAVEFORMS.svg').write_text(svg_text, encoding='utf-8')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless=True, args=['--disable-gpu', '--disable-background-networking', '--no-first-run'])
        try:
            page = browser.new_page(viewport={'width': 1220, 'height': 900})
            page.route('**/*', lambda route: route.abort())
            page.set_content('<html><body style="margin:0">' + svg_text + '</body></html>')
            page.screenshot(path=str(destination / 'SYNTHETIC_WAVEFORMS.png'))
        finally:
            browser.close()
    summary = dict(scope='actual developer-generated synthetic WAV bytes; no playback, STT, VAD or acoustic listening', manifest_sha256=sha(manifest_path), references_sha256=sha(reference_path), sample_count=len(rows), passed=sum((x['passed'] for x in rows)), unique_ids=len({r['id'] for r in rows}), total_seconds=sum((r['actual']['seconds'] for r in rows)), conditions=dict(collections.Counter((r['condition'] for r in rows))), categories=dict(collections.Counter((r['category'] for r in manifest['samples']))), clipped_sample_count=sum((r['actual']['clipped_samples'] for r in rows)), internal_pause_samples_with_at_least_600ms_exact_zero=sum((r['condition'] == 'internal_pause' and r['actual']['longest_interior_zero_seconds'] >= 0.6 for r in rows)), observations=rows, limitations=['Independent waveform inspection cannot establish intelligibility, WER or recognition quality.', 'Declared noise SNR is not independently recoverable without preserved precondition PCM.', 'Exact zero runs measure file pauses, not VAD endpointing latency.', 'Synthetic controlled voices are not owner microphone, room noise, acoustic echo or actual speech listening.'])
    (destination / 'RESULTS.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.corpus, args.out)
    print(json.dumps({key: result[key] for key in ('sample_count', 'passed', 'total_seconds', 'clipped_sample_count', 'internal_pause_samples_with_at_least_600ms_exact_zero')}))
