from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from .card import Character


class RelicRarity(Enum):
    STARTER = auto()
    COMMON = auto()
    UNCOMMON = auto()
    RARE = auto()
    BOSS = auto()
    SHOP = auto()
    EVENT = auto()


@dataclass(frozen=True)
class Relic:
    name: str
    rarity: RelicRarity
    description: str
    character: Character = Character.NEUTRAL  # NEUTRAL = available to all
    effects: dict[str, Any] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Relic):
            return NotImplemented
        return self.name == other.name

    def __str__(self) -> str:
        return f"{self.name} ({self.rarity.name})"
