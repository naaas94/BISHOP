# Bishop (M0)

Minimal Docker Compose skeleton for the nine Bishop services. M0 validates structure and reachability only — no pipeline logic.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/macOS) or Docker Engine with Compose on Linux
- Bash (Git Bash on Windows, or WSL)
- Python 3.11+ for unit tests (`pip install -e ".[dev]"`)

## Quick start

1. Copy environment defaults and adjust paths if needed (Windows requires an explicit `BISHOP_DATA_ROOT` — see `.env.example`):

   ```bash
   cp .env.example .env
   ```

2. Create host volume directories:

   ```bash
   bash scripts/init-volumes.sh
   ```

3. Start the stack:

   ```bash
   docker compose up --build -d
   ```

4. Run the G1 verification gate (compose health, host ports, volume writability):

   ```bash
   bash scripts/verify-g1.sh
   ```

   Requires Docker running locally. This script is the manual/local acceptance check for M0; CI without Docker should rely on pytest only.

## Unit tests

```bash
pytest
```
