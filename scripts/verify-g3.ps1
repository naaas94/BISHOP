# G3 verification gate (M3): live Anthropic Messages API probe for pinned pre-filter model.
param()

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Write-Log([string]$Message) {
    Write-Host "[verify-g3] $Message"
}

function Fail([string]$Message) {
    Write-Error "[verify-g3] ERROR: $Message"
    exit 1
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Fail "required command not found: python"
}

python -m pytest --version *> $null
if ($LASTEXITCODE -ne 0) {
    Fail "pytest is not available (install project dev dependencies)"
}

Write-Log "Running G3 unit tests (mocked Anthropic client)"
python -m pytest tests/test_anthropic_config.py tests/test_verify_g3.py -v --tb=short
if ($LASTEXITCODE -ne 0) {
    Fail "G3 unit tests failed"
}

if (-not $env:ANTHROPIC_API_KEY) {
    Write-Log "SKIP: ANTHROPIC_API_KEY not set — live G3 model verification skipped (CI-safe)"
    exit 0
}

Write-Log "Live G3 probe: model claude-haiku-4-5-20251001"
$probe = @'
from bishop_shared.anthropic_config import ANTHROPIC_MODEL_PREFILTER, verify_model_string
import sys

EXPECTED = "claude-haiku-4-5-20251001"
if ANTHROPIC_MODEL_PREFILTER != EXPECTED:
    print(
        f"ANTHROPIC_MODEL_PREFILTER mismatch: {ANTHROPIC_MODEL_PREFILTER!r} != {EXPECTED!r}",
        file=sys.stderr,
    )
    sys.exit(1)

if not verify_model_string():
    print(
        f"Anthropic Messages API returned HTTP 400 for model {ANTHROPIC_MODEL_PREFILTER!r}",
        file=sys.stderr,
    )
    sys.exit(1)
'@

python -c $probe
if ($LASTEXITCODE -ne 0) {
    Fail "G3 model string verification failed — M3 Anthropic work blocked"
}

Write-Log "G3 verification passed"
