# Create host volume directories under BISHOP_DATA_ROOT (spec §8.5).
param()

$root = if ($env:BISHOP_DATA_ROOT) { $env:BISHOP_DATA_ROOT } else { Join-Path $HOME "bishop_data" }

$dirs = @("sqlite", "lancedb", "duckdb", "bm25", "profiles", "logs")
foreach ($name in $dirs) {
    $path = Join-Path $root $name
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

Write-Host "Bishop volume directories ready under: $root"
