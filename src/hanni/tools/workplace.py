"""Owner-requested public web search and ephemeral Windows screen OCR."""
import base64
import json
from urllib.parse import urlsplit, quote

from .base import ToolDefinition, ToolResult
from .winshell import run_powershell_json

# Capture and OCR run in one short-lived process. Frames never touch disk.
# See https://learn.microsoft.com/uwp/api/windows.media.ocr.ocrengine.recognizeasync
SCREEN_OCR = r'''
Add-Type -AssemblyName System.Drawing,System.Windows.Forms,UIAutomationClient,UIAutomationTypes,System.Runtime.WindowsRuntime
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class HanniScreen {
  public delegate bool Visit(IntPtr handle, IntPtr data);
  [DllImport("user32.dll")] public static extern bool EnumWindows(Visit callback, IntPtr data);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr handle);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr handle);
  [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr handle, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr handle, out uint pid);
}
'@
$policy = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__POLICY__')) | ConvertFrom-Json
$blocked = [Collections.Generic.List[string]]::new()
$visit = [HanniScreen+Visit] {
  param($handle, $data)
  if (-not [HanniScreen]::IsWindowVisible($handle) -or [HanniScreen]::IsIconic($handle)) { return $true }
  $caption = [Text.StringBuilder]::new(4096)
  [void][HanniScreen]::GetWindowText($handle, $caption, 4096)
  if (-not $caption.Length) { return $true }
  [uint32]$windowPid = 0
  [void][HanniScreen]::GetWindowThreadProcessId($handle, [ref]$windowPid)
  try { $name = (Get-Process -Id $windowPid -ErrorAction Stop).ProcessName + '.exe' }
  catch { $blocked.Add('A visible application could not be checked.'); return $true }
  if ($policy.process_names -contains $name) { $blocked.Add('A protected application is visible.'); return $true }
  foreach ($pattern in $policy.window_title_patterns) {
    if ([regex]::IsMatch($caption.ToString(), $pattern)) { $blocked.Add('A protected window is visible.'); return $true }
  }
  if ($name -match '^(msedge|chrome|firefox|brave|opera|vivaldi)\.exe$' -and $policy.url_patterns.Count) {
    try {
      $root = [System.Windows.Automation.AutomationElement]::FromHandle($handle)
      $condition = [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Edit)
      $edits = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
      $url = $null
      foreach ($edit in $edits) {
        if (-not $edit.Current.IsPassword -and $edit.Current.Name -match '(?i)address|location|search or enter') {
          $value = $edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value
          if ($value -match '^(https?://|localhost[:/])') { $url = $value; break }
        }
      }
      if (-not $url) { $blocked.Add('A browser address could not be checked against screen exclusions.') }
      else { foreach ($pattern in $policy.url_patterns) { if ([regex]::IsMatch($url, $pattern)) { $blocked.Add('A protected browser page is visible.') } } }
    } catch { $blocked.Add('Browser privacy checks were unavailable.') }
  }
  return $true
}
[void][HanniScreen]::EnumWindows($visit, [IntPtr]::Zero)
if ($blocked.Count) { throw $blocked[0] }
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime]
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1 } | Select-Object -First 1
function Await($operation, $type) { $asTask.MakeGenericMethod($type).Invoke($null, @($operation)).GetAwaiter().GetResult() }
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if (-not $engine) { throw 'Install a Windows OCR language to enable screen text recognition.' }
$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
if ($bounds.Width -le 0 -or $bounds.Height -le 0 -or [long]$bounds.Width * $bounds.Height -gt 40000000) { throw 'No capturable desktop or display area is too large.' }
$bitmap = $graphics = $scaled = $memory = $random = $software = $null
try {
  $bitmap = [Drawing.Bitmap]::new($bounds.Width, $bounds.Height)
  $graphics = [Drawing.Graphics]::FromImage($bitmap)
  $graphics.CopyFromScreen($bounds.Left, $bounds.Top, 0, 0, $bitmap.Size)
  # Recheck exclusions after capture. A newly opened private surface is discarded.
  [void][HanniScreen]::EnumWindows($visit, [IntPtr]::Zero)
  if ($blocked.Count) { throw $blocked[0] }
  $limit = [Windows.Media.Ocr.OcrEngine]::MaxImageDimension
  $ratio = [Math]::Min(1.0, $limit / [double][Math]::Max($bitmap.Width, $bitmap.Height))
  $scaled = [Drawing.Bitmap]::new($bitmap, [Drawing.Size]::new([int]($bitmap.Width * $ratio), [int]($bitmap.Height * $ratio)))
  $memory = [IO.MemoryStream]::new()
  $scaled.Save($memory, [Drawing.Imaging.ImageFormat]::Png)
  $memory.Position = 0
  $random = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($memory)
  $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($random)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $software = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $result = Await ($engine.RecognizeAsync($software)) ([Windows.Media.Ocr.OcrResult])
  @{ text = (($result.Lines | ForEach-Object { $_.Text }) -join "`n"); width = $bounds.Width; height = $bounds.Height; method = 'windows-ocr' } | ConvertTo-Json -Compress
} finally {
  foreach ($resource in @($software, $random, $memory, $scaled, $graphics, $bitmap)) { if ($null -ne $resource) { $resource.Dispose() } }
}
'''


def definitions(config):
    def search(args, context, request):
        from hanni.native.local_tools import _web_search
        from hanni.memory.privacy import validate_memory_text
        query = validate_memory_text(args['query'], max_chars=300)
        result = _web_search(query)
        if not result.get('ok'):
            return ToolResult('web.search', False, result.get('error') or 'Web search unavailable.')
        sources = []
        for source in result.get('data', {}).get('results', []):
            parts = urlsplit(source['url'])
            if parts.scheme not in {'https', 'http'} or not parts.hostname or parts.username or parts.password:
                continue
            sources.append({**source, 'url': quote(source['url'], safe='/:?=&%#@,+-._~')})
        return ToolResult('web.search', bool(sources), 'Search excerpts returned.' if sources else 'No usable search links returned.', {'results': sources})

    def screen(args, context, request):
        exclusions = config.privacy.screen_exclusions
        policy = {name: list(getattr(exclusions, name)) for name in ('process_names', 'window_title_patterns', 'url_patterns')}
        encoded = base64.b64encode(json.dumps(policy).encode()).decode('ascii')
        result = run_powershell_json(SCREEN_OCR.replace('__POLICY__', encoded), timeout=40, capability='screen.read_text')
        if not isinstance(result, dict) or not isinstance(result.get('text'), str):
            raise RuntimeError('Windows OCR returned invalid screen data.')
        result['text'] = result['text'][:20000]
        return ToolResult('screen.read_text', True, 'On-demand screen text recognized; frame discarded.', result)
    return (
        ToolDefinition('web.search', 'Search the public web and return bounded source excerpts and URLs.', 0, 0,
            {'query': str}, {'results': 'array'}, search, side_effect='read', timeout_seconds=60, background_allowed=False),
        ToolDefinition('screen.read_text', 'Capture the visible desktop once, honor screen exclusions, recognize text locally, and discard the frame.', 2, 2,
            {}, {'text': 'string', 'method': 'string'}, screen, side_effect='read', timeout_seconds=50, background_allowed=False,
            requires_confirmation_if=lambda args: 'Screen capture requires an explicit owner request.'),
    )
