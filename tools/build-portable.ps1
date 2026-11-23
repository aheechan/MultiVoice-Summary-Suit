# Build a portable, self-contained folder for testing on another Windows machine.
# Layout:
#   MultiVoice-Portable\
#     Start-MultiVoice.bat
#     app\          source + configs (relative paths)
#     runtime\python  base CPython 3.12
#     runtime\venv    project dependencies
#     runtime\ffmpeg  ffmpeg build
#     models\qwen3_asr_0_6b  ASR model (optional)
param(
    [string]$Dist = 'D:\Local Repositories\MultiVoice-Summary-Suit\dist\MultiVoice-Portable',
    [string]$BasePython = 'C:\Users\72157\AppData\Local\Programs\Python\Python312',
    [string]$Venv = 'D:\Local Repositories\_venvs\MultiVoice-Summary-Suit',
    [string]$Ffmpeg = 'C:\Program Files\ffmpeg-n8.0-latest-win64-gpl-shared-8.0',
    [string]$AsrModel = 'D:\ALT-VoiceType\models\qwen3_asr_0_6b',
    [switch]$IncludeModel
)

$ErrorActionPreference = 'Stop'
function Copy-Tree([string]$From, [string]$To, [string[]]$Extra = @()) {
    $rc = @($From, $To, '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/MT:8') + $Extra
    robocopy @rc | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE): $From -> $To" }
    $global:LASTEXITCODE = 0
}
$repo = Split-Path -Parent $PSScriptRoot
if (Test-Path $Dist) { Remove-Item $Dist -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Dist | Out-Null

Write-Host "1/6 copying application sources..."
$exclude = @('.git', 'dist', 'release', 'build', 'output', 'work', 'docs', '__pycache__', '.venv')
$rc = @($repo, (Join-Path $Dist 'app'), '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/NP')
foreach ($dir in $exclude) { $rc += '/XD'; $rc += (Join-Path $repo $dir) }
robocopy @rc | Out-Null

Write-Host "2/6 copying CPython runtime..."
Copy-Tree $BasePython (Join-Path $Dist 'runtime\python')

Write-Host "3/6 copying virtual environment..."
Copy-Tree $Venv (Join-Path $Dist 'runtime\venv')

Write-Host "4/6 copying FFmpeg..."
Copy-Tree $Ffmpeg (Join-Path $Dist 'runtime\ffmpeg')

if ($IncludeModel -and (Test-Path $AsrModel)) {
    Write-Host "5/6 copying ASR model (large)..."
    robocopy $AsrModel (Join-Path $Dist 'models\qwen3_asr_0_6b') /E /NFL /NDL /NJH /NJS /NP | Out-Null
} else {
    Write-Host "5/6 skipping ASR model (pass -IncludeModel to bundle it)"
}

Write-Host "6/6 writing portable config and launcher..."
$utf8 = New-Object System.Text.UTF8Encoding($false)

$configDir = Join-Path $Dist 'app\configs'
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
$paths = @'
[workspace]
work = "../work"
output = "../output"

[models]
root = "../models"

[tools]
ffmpeg = "../runtime/ffmpeg/bin/ffmpeg.exe"
ffprobe = "../runtime/ffmpeg/bin/ffprobe.exe"

[output]
languages = ["zh", "en"]
'@
[System.IO.File]::WriteAllText((Join-Path $configDir 'paths.toml'), $paths, $utf8)

$models = @'
[asr]
engine = "qwen3"
model = "qwen3_asr_0_6b"
device = "cpu"
language = "auto"

[[llm.providers]]
name = "local"
base_url = "http://127.0.0.1:8082/v1"
model = "Qwen3.5-9B"
enabled = true
priority = 1
'@
[System.IO.File]::WriteAllText((Join-Path $configDir 'models.toml'), $models, $utf8)

$bat = @'
@echo off
setlocal
cd /d "%~dp0app"
set "PYTHONPATH=%~dp0app\src;%~dp0runtime\venv\Lib\site-packages"
set "MVS_CONFIG_DIR=%~dp0app\configs"
set "MVS_GLOSSARY=%~dp0glossary\terms.jsonl"
if not exist "%~dp0work" mkdir "%~dp0work"
if not exist "%~dp0output" mkdir "%~dp0output"
if not exist "%~dp0glossary" mkdir "%~dp0glossary"
if "%~1"=="" (
  "%~dp0runtime\python\pythonw.exe" -m multivoice.ui.tray --panel
) else (
  "%~dp0runtime\python\pythonw.exe" -m multivoice.ui.tray --panel --input "%~1"
)
'@
[System.IO.File]::WriteAllText((Join-Path $Dist 'Start-MultiVoice.bat'), $bat,
    (New-Object System.Text.ASCIIEncoding))

New-Item -ItemType Directory -Force -Path (Join-Path $Dist 'work') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Dist 'output') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Dist 'glossary') | Out-Null

$size = (Get-ChildItem $Dist -Recurse -File | Measure-Object Length -Sum).Sum
Write-Host ("done: {0}  ({1:N0} MB)" -f $Dist, ($size / 1MB))
