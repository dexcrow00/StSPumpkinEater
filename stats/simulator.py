"""Monte-Carlo simulation engine for Slay the Spire scenarios."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable

from models.game_state import GameState


@dataclass
class SimulationResult:
    """Aggregated outcome of a batch of simulations."""
    runs: int = 0
    outcomes: dict[str, list[float]] = field(default_factory=dict)

    def record(self, metrics: dict[str, float]) -> None:
        self.runs += 1
        for key, value in metrics.items():
            self.outcomes.setdefault(key, []).append(value)

    def mean(self, key: str) -> float:
        values = self.outcomes.get(key, [])
        return sum(values) / len(values) if values else 0.0

    def percentile(self, key: str, pct: float) -> float:
        values = sorted(self.outcomes.get(key, []))
        if not values:
            return 0.0
        idx = int(len(values) * pct / 100)
        return values[min(idx, len(values) - 1)]

    def summary(self) -> dict[str, dict[str, float]]:
        result = {}
        for k in self.outcomes:
            result[k] = {
                "mean": self.mean(k),
                "min": self.percentile(k, 0),
                "p25": self.percentile(k, 25),
                "median": self.percentile(k, 50),
                "p75": self.percentile(k, 75),
                "max": self.percentile(k, 100),
            }
        return result


# A scenario function receives a GameState, plays it out, and returns metrics.
ScenarioFn = Callable[[GameState], dict[str, float]]


class Simulator:
    """Run many iterations of a scenario and collect statistics."""

    def __init__(self, base_state: GameState) -> None:
        self.base_state = base_state

    def run(self, scenario: ScenarioFn, iterations: int = 10_000) -> SimulationResult:
        result = SimulationResult()
        for _ in range(iterations):
            state = copy.deepcopy(self.base_state)
            state.deck.shuffle()
            metrics = scenario(state)
            result.record(metrics)
        return result
