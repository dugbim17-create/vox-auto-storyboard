# Start the OmniVoice TTS worker (P3-T01).
#
# The worker must run under the OmniVoice venv (torch + CUDA) with the tool
# root on sys.path so `import synth` resolves, but the FastAPI app package lives
# in this project. We launch uvicorn with:
#   - python = OmniVoice venv (has fastapi/uvicorn/omnivoice/torch)
#   - cwd    = tool root (so `import synth` works)
#   - PYTHONPATH = <project root> (so `import workers.omnivoice_worker` works)
#   - PYTHONIOENCODING = utf-8

param(
    [int]$Port = 8791,
    [string]$ListenHost = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
throw "OmniVoice retired. Worker launch is disabled; use VieNeu CPU/GPU or Piper."

# Discover the OmniVoice venv python from the project settings/discovery.
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = $projectRoot

# Resolve venv python from config/discovered/omnivoice.json (fallback: known path).
$omniConfig = Join-Path $projectRoot "config\discovered\omnivoice.json"
if (Test-Path $omniConfig) {
    $cfg = Get-Content $omniConfig -Raw | ConvertFrom-Json
    $venvPython = $cfg.venv_python
    $toolRoot = $cfg.tool_root
} else {
    $venvPython = "D:\ALL AI\VScode\voice-clone-tool\.venv\Scripts\python.exe"
    $toolRoot = "D:\ALL AI\VScode\voice-clone-tool"
}
$env:OMNIVOICE_TOOL_ROOT = $toolRoot

if (-not (Test-Path $venvPython)) {
    Write-Error "OmniVoice venv python not found: $venvPython"
    exit 1
}

Write-Host "Starting OmniVoice worker on $ListenHost`:$Port"
Write-Host "  python : $venvPython"
Write-Host "  tool   : $toolRoot"
Write-Host "  cwd    : $toolRoot"

Push-Location $toolRoot
try {
    & $venvPython -m uvicorn workers.omnivoice_worker.main:app --host $ListenHost --port $Port
} finally {
    Pop-Location
}
