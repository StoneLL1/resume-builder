#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet('serve','render','session','wait_for_event','validate_project','bootstrap_runtime')]
    [string]$Script,
    [Parameter(Position=1, ValueFromRemainingArguments=$true)]
    [string[]]$ScriptArgs,
    [string]$RuntimeHome = $env:RESUME_BUILDER_HOME
)
$ErrorActionPreference = 'Stop'
if (-not $RuntimeHome) { $RuntimeHome = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'resume-builder' }
$env:RESUME_BUILDER_HOME = [IO.Path]::GetFullPath($RuntimeHome)
$statePath = Join-Path $RuntimeHome 'runtime-state.json'
$interpreter = $null
if (Test-Path -LiteralPath $statePath) {
    $state = Get-Content -Raw -Encoding UTF8 -LiteralPath $statePath | ConvertFrom-Json
    if (Test-Path -LiteralPath $state.python.executable -PathType Leaf) { $interpreter = $state.python.executable }
}
if (-not $interpreter) {
    $manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot '../assets/runtime-manifest.json') | ConvertFrom-Json
    $runtimeArch = [Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
    $managed = Join-Path $RuntimeHome ("python-$($manifest.python.version)-$runtimeArch\python.exe")
    if (Test-Path -LiteralPath $managed -PathType Leaf) { $interpreter = $managed }
}
if (-not $interpreter) {
    foreach ($candidate in @('python','python3')) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command -and $command.Source -notlike '*\WindowsApps\*') { $interpreter = $command.Source; break }
    }
}
if (-not $interpreter) { throw 'Python unavailable. Run scripts/bootstrap.ps1 first.' }
$env:PYTHONUTF8 = '1'
& $interpreter (Join-Path $PSScriptRoot ($Script + '.py')) @ScriptArgs
exit $LASTEXITCODE
