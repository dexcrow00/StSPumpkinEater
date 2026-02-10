from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class EnemyType(Enum):
    NORMAL = auto()
    ELITE = auto()
    BOSS = auto()


@dataclass
class Enemy:
    name: str
    enemy_type: EnemyType
    act: int  # 1, 2, or 3
    hp_min: int = 0
    hp_max: int = 0
    moves: list[dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.name} ({self.enemy_type.name}, Act {self.act}, HP {self.hp_min}-{self.hp_max})"
