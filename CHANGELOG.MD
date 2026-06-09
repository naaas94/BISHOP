# Changelog

## m0-workshop — 2026-06-09

- T1 (repo layout, shared constants, volume init): Added `bishop_shared/constants.py` with frozen §9 service names, §8.5 volume mounts, and M0 port constants; `.env.example`, cross-platform `scripts/init-volumes` scripts, pytest coverage, and architectural decision log for layout and volume matrix. Establishes the typed contract surface T2–T5 consume without embedding paths in compose yet.
