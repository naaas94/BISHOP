"""Harvest dollar metering — pinned units, derived N_cap.

Operator sets dollars. Env ``BISHOP_HARVEST_DAILY_BUDGET_USD`` overrides
``daily_budget_usd`` (``0`` kills the GitHub tap). Live Anthropic usage is
PB-002; this module is the v0 formula.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_RELATIVE = Path("config/harvest/economics.yaml")
_CONTAINER_PATH = Path("/app/config/harvest/economics.yaml")


@dataclass(frozen=True)
class HarvestEconomics:
    daily_budget_usd: float
    unit_gate1_usd: float
    unit_enrich_usd: float
    github_paid_path_rate: float
    paper_daily_g1_reserve: int
    paper_paid_path_rate: float

    @property
    def blended_github_usd(self) -> float:
        return self.unit_gate1_usd + self.github_paid_path_rate * self.unit_enrich_usd

    @property
    def paper_reserve_usd(self) -> float:
        g1 = self.paper_daily_g1_reserve * self.unit_gate1_usd
        enrich = (
            self.paper_daily_g1_reserve
            * self.paper_paid_path_rate
            * self.unit_enrich_usd
        )
        return g1 + enrich

    @property
    def github_budget_usd(self) -> float:
        return self.daily_budget_usd - self.paper_reserve_usd

    @property
    def n_cap(self) -> int:
        blended = self.blended_github_usd
        budget = self.github_budget_usd
        if blended <= 0 or budget <= 0:
            return 0
        return math.floor(budget / blended)


def remaining_slots(*, n_cap: int, released_today: int, github_in_queue: int) -> int:
    """Tap inserts this many more GitHub rows today (never negative)."""
    from_budget = n_cap - released_today
    from_queue = n_cap - github_in_queue
    return max(0, min(from_budget, from_queue))


def economics_yaml_path() -> Path:
    raw = os.environ.get("BISHOP_HARVEST_ECONOMICS_PATH")
    if raw:
        return Path(raw)
    for candidate in (_CONTAINER_PATH, _DEFAULT_RELATIVE):
        if candidate.is_file():
            return candidate
    return _DEFAULT_RELATIVE


def _parse_flat_yaml(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def load_harvest_economics(path: Path | None = None) -> HarvestEconomics:
    """Load committed yaml, then apply the daily-budget env override."""
    yaml_path = path or economics_yaml_path()
    if not yaml_path.is_file():
        raise FileNotFoundError(f"harvest economics missing: {yaml_path}")
    raw = _parse_flat_yaml(yaml_path.read_text(encoding="utf-8"))
    budget = float(raw["daily_budget_usd"])
    env_budget = os.environ.get("BISHOP_HARVEST_DAILY_BUDGET_USD")
    if env_budget is not None and env_budget != "":
        budget = float(env_budget)
    return HarvestEconomics(
        daily_budget_usd=budget,
        unit_gate1_usd=float(raw["unit_gate1_usd"]),
        unit_enrich_usd=float(raw["unit_enrich_usd"]),
        github_paid_path_rate=float(raw["github_paid_path_rate"]),
        paper_daily_g1_reserve=int(float(raw["paper_daily_g1_reserve"])),
        paper_paid_path_rate=float(raw["paper_paid_path_rate"]),
    )
