# Copy repo NL profiles into BISHOP_DATA_ROOT when host volume is empty (M3 C1).
param()

$root = if ($env:BISHOP_DATA_ROOT) { $env:BISHOP_DATA_ROOT } else { Join-Path $HOME "bishop_data" }
$dest = Join-Path $root "profiles"
$src = Join-Path (Split-Path $PSScriptRoot -Parent) "config\profiles"

New-Item -ItemType Directory -Force -Path $dest | Out-Null

$hasEntries = $false
if (Test-Path $dest) {
    $hasEntries = @(Get-ChildItem -Path $dest -Force).Count -gt 0
}

if (-not $hasEntries) {
    Copy-Item -Path (Join-Path $src "*") -Destination $dest -Recurse -Force
    Write-Host "Seeded profiles into: $dest"
} else {
    Write-Host "Profiles directory not empty, skipping seed: $dest"
}
