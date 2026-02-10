from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .card import Character


class PotionRarity(Enum):
    COMMON = auto()
    UNCOMMON = auto()
    RARE = auto()


@dataclass(frozen=True)
class Potion:
    name: str
    rarity: PotionRarity
    description: str
    character: Character = Character.NEUTRAL

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Potion):
            return NotImplemented
        return self.name == other.name

    def __str__(self) -> str:
        return f"{self.name} ({self.rarity.name})"
