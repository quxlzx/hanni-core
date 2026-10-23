[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$qaInput = [Console]::In.ReadToEnd() | ConvertFrom-Json
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$qaWindow = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$qaInput.hwnd)
if ($null -eq $qaWindow -or $qaWindow.Current.ProcessId -ne $qaInput.pid) {
    throw 'Native automation window ownership did not match.'
}
if ($qaInput.action -eq 'inspect_tree') {
    $qaDescendants = $qaWindow.FindAll([System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.Condition]::TrueCondition)
    $qaItems = @()
    for ($qaIndex = 0; $qaIndex -lt [Math]::Min(600, $qaDescendants.Count); $qaIndex++) {
        $qaChild = $qaDescendants.Item($qaIndex)
        if ($qaChild.Current.ProcessId -eq $qaInput.pid) {
            $qaItems += @{name=$qaChild.Current.Name;process_id=$qaChild.Current.ProcessId;
                control_type=$qaChild.Current.ControlType.ProgrammaticName;
                enabled=$qaChild.Current.IsEnabled;offscreen=$qaChild.Current.IsOffscreen;
                patterns=@($qaChild.GetSupportedPatterns() | ForEach-Object { $_.ProgrammaticName })}
        }
    }
    @{items=$qaItems;count=$qaDescendants.Count;scope='Descendants of exact owned HWND only'} |
        ConvertTo-Json -Depth 6 -Compress
    exit
}
$qaCondition = [System.Windows.Automation.PropertyCondition]::new(
    [System.Windows.Automation.AutomationElement]::NameProperty, [string]$qaInput.name)
$qaElement = $qaWindow.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $qaCondition)
if ($null -eq $qaElement) { throw 'Named native control is unavailable in the owned window.' }
$qaPatterns = @($qaElement.GetSupportedPatterns() | ForEach-Object { $_.ProgrammaticName })
$qaPattern = $null
if ($qaInput.action -eq 'inspect') {
    # Inspection reads only the named control in an already verified owned tree.
} elseif ($qaInput.action -eq 'invoke') {
    if ($qaElement.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$qaPattern)) {
        $qaPattern.Invoke()
    } elseif ($qaElement.TryGetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern, [ref]$qaPattern)) {
        $qaPattern.Expand()
    } else { throw 'The owned native control has no invoke/expand pattern.' }
} else { throw 'Unsupported native automation action.' }
@{name=$qaInput.name;process_id=$qaElement.Current.ProcessId;control_type=$qaElement.Current.ControlType.ProgrammaticName;
  enabled=$qaElement.Current.IsEnabled;patterns=$qaPatterns;action=$qaInput.action} | ConvertTo-Json -Depth 5 -Compress
