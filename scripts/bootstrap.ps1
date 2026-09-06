#requires -Version 5.1
<#
.SYNOPSIS
  Installs the pinned resume-builder Python/Typst/font runtime without admin rights.

.PARAMETER Mirror
  Optional download proxy prefix. It may contain {url}; otherwise the original
  HTTPS URL is appended (compatible with common GitHub proxy mirrors). The
  official URL is retried if the mirror fails.
#>

[CmdletBinding()]
param(
    [string]$RuntimeHome = $env:RESUME_BUILDER_HOME,
    [string]$Mirror = $env:RESUME_BUILDER_DOWNLOAD_MIRROR,
    [switch]$Force,
    [switch]$Check
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$V2Root = Split-Path -Parent $ScriptRoot
$ManifestPath = Join-Path $V2Root 'assets\runtime-manifest.json'

if (-not $RuntimeHome) {
    $localBase = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
    $RuntimeHome = Join-Path $localBase 'resume-builder'
}
$RuntimeHome = [IO.Path]::GetFullPath($RuntimeHome)

$archName = [Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
switch ($archName) {
    'X64'   { $PlatformKey = 'windows-x64'; $ArchKey = 'x64' }
    'Arm64' { $PlatformKey = 'windows-arm64'; $ArchKey = 'arm64' }
    default { throw "不支持的 Windows CPU 架构：$archName（仅支持 x64 / arm64）。" }
}

$Manifest = Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
if ($Manifest.schema_version -ne 1) {
    throw 'runtime-manifest.json 的 schema_version 必须为 1。'
}

function Find-CompatiblePython {
    $candidates = @(
        @{ Name = 'python'; Args = @() },
        @{ Name = 'python3'; Args = @() },
        @{ Name = 'py'; Args = @('-3') }
    )
    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate.Name -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $command) { continue }
        $candidateExe = $command.Source
        $candidateArgs = @($candidate.Args)
        $output = & $candidateExe @candidateArgs -c "import sys; print('ok' if sys.version_info >= (3, 10) else 'old')" 2>$null
        if ($LASTEXITCODE -eq 0 -and ($output | Select-Object -Last 1) -eq 'ok') {
            return @{ Exe = $command.Source; Args = @($candidate.Args); Managed = $false }
        }
    }
    return $null
}

function Resolve-DownloadUrls([string]$Url) {
    $urls = @()
    if ($Mirror) {
        if ($Mirror.Contains('{url}')) {
            $urls += $Mirror.Replace('{url}', $Url)
        } else {
            $urls += $Mirror.TrimEnd('/') + '/' + $Url
        }
    }
    $urls += $Url
    return $urls
}

function Get-VerifiedDownload($Artifact) {
    $downloadDir = Join-Path $RuntimeHome 'downloads'
    [IO.Directory]::CreateDirectory($downloadDir) | Out-Null
    $target = Join-Path $downloadDir $Artifact.filename
    if (-not $Force -and (Test-Path -LiteralPath $target -PathType Leaf)) {
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
        if ($actual -eq $Artifact.sha256) {
            Write-Host "[bootstrap] 使用已校验缓存：$($Artifact.filename)"
            return $target
        }
    }
    $errors = @()
    foreach ($url in (Resolve-DownloadUrls $Artifact.url)) {
        $part = Join-Path $downloadDir ('.' + $Artifact.filename + '.' + [Guid]::NewGuid().ToString('N') + '.part')
        try {
            Write-Host "[bootstrap] 下载 Python：$url"
            Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $part -TimeoutSec 180
            $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $part).Hash.ToLowerInvariant()
            if ($actual -ne $Artifact.sha256) {
                throw "SHA-256 不匹配；期望 $($Artifact.sha256)，实际 $actual"
            }
            [IO.File]::Copy($part, $target, $true)
            [IO.File]::Delete($part)
            return $target
        } catch {
            $errors += "${url}: $($_.Exception.Message)"
            if (Test-Path -LiteralPath $part) { [IO.File]::Delete($part) }
        }
    }
    throw "Python 下载失败（镜像与官方源均不可用）：`n- $($errors -join "`n- ")"
}

function Install-ManagedPython {
    if ($Check) {
        throw '未找到 Python 3.10+；--Check 不会下载运行时。请先不带 -Check 运行 bootstrap.ps1。'
    }
    $property = $Manifest.python.platforms.PSObject.Properties[$PlatformKey]
    if (-not $property) { throw "运行时清单缺少 Python 平台：$PlatformKey" }
    $artifact = $property.Value
    $archive = Get-VerifiedDownload $artifact
    $tar = Get-Command tar.exe -ErrorAction SilentlyContinue
    if (-not $tar) { $tar = Get-Command tar -ErrorAction SilentlyContinue }
    if (-not $tar) { throw '安装便携 Python 需要 Windows 自带的 tar.exe（Windows 10/11 默认提供）。' }

    $pythonRoot = Join-Path $RuntimeHome ("python-$($Manifest.python.version)-$ArchKey")
    $expectedExe = Join-Path $pythonRoot 'python.exe'
    if (-not $Force -and (Test-Path -LiteralPath $expectedExe -PathType Leaf)) {
        $ok = & $expectedExe -c "import sys; print('ok' if sys.version_info >= (3, 10) else 'old')" 2>$null
        if ($LASTEXITCODE -eq 0 -and ($ok | Select-Object -Last 1) -eq 'ok') {
            return @{ Exe = $expectedExe; Args = @(); Managed = $true }
        }
    }

    [IO.Directory]::CreateDirectory($RuntimeHome) | Out-Null
    $staging = Join-Path $RuntimeHome ('.python-staging-' + [Guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($staging) | Out-Null
    try {
        & $tar.Source -xzf $archive -C $staging
        if ($LASTEXITCODE -ne 0) { throw "Python 归档解压失败，退出码 $LASTEXITCODE。" }
        $sourceRoot = Join-Path $staging 'python'
        $sourceExe = Join-Path $sourceRoot 'python.exe'
        if (-not (Test-Path -LiteralPath $sourceExe -PathType Leaf)) {
            throw "Python 归档结构异常：未找到 $sourceExe"
        }
        if (Test-Path -LiteralPath $pythonRoot) {
            # 只删除当前脚本管理的精确版本目录，不碰用户的系统 Python。
            [IO.Directory]::Delete($pythonRoot, $true)
        }
        [IO.Directory]::Move($sourceRoot, $pythonRoot)
        Unblock-File -LiteralPath $expectedExe -ErrorAction SilentlyContinue
    } finally {
        if (Test-Path -LiteralPath $staging) { [IO.Directory]::Delete($staging, $true) }
    }
    $versionCheck = & $expectedExe -c "import sys; print(sys.version.split()[0])" 2>$null
    if ($LASTEXITCODE -ne 0) { throw '便携 Python 安装后无法启动。' }
    Write-Host "[bootstrap] Python 安装完成：$versionCheck"
    return @{ Exe = $expectedExe; Args = @(); Managed = $true }
}

$Python = Find-CompatiblePython
if (-not $Python) { $Python = Install-ManagedPython }
Write-Host "[bootstrap] Python：$($Python.Exe)"

$helperArgs = @(
    (Join-Path $ScriptRoot 'bootstrap_runtime.py'),
    '--manifest', $ManifestPath,
    '--runtime-home', $RuntimeHome,
    '--platform', $PlatformKey
)
if ($Mirror) { $helperArgs += @('--mirror', $Mirror) }
if ($Force) { $helperArgs += '--force' }
if ($Check) { $helperArgs += '--check' }

$PythonExe = $Python.Exe
$PythonPrefixArgs = @($Python.Args)
& $PythonExe @PythonPrefixArgs @helperArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$env:RESUME_BUILDER_HOME = $RuntimeHome
$typstExe = Join-Path $RuntimeHome 'bin\typst.exe'
$env:RESUME_BUILDER_TYPST = $typstExe
Write-Host "[bootstrap] RESUME_BUILDER_HOME=$RuntimeHome"
$pythonDisplay = ((@($PythonExe) + $PythonPrefixArgs) | ForEach-Object { '"' + $_ + '"' }) -join ' '
Write-Host "[bootstrap] 启动示例：& $pythonDisplay `"$ScriptRoot\serve.py`" `"<项目目录>`""
