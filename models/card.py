from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class CardType(Enum):
    ATTACK = auto()
    SKILL = auto()
    POWER = auto()
    STATUS = auto()
    CURSE = auto()


class Rarity(Enum):
    BASIC = auto()
    COMMON = auto()
    UNCOMMON = auto()
    RARE = auto()
    SPECIAL = auto()  # for statuses, curses, generated cards


class Character(Enum):
    IRONCLAD = "ironclad"
    SILENT = "silent"
    DEFECT = "defect"
    WATCHER = "watcher"
    COLORLESS = "colorless"
    NEUTRAL = "neutral"  # curses, statuses


@dataclass(frozen=True, eq=False)
class Card:
    """A single Slay the Spire card.

    ``effects`` holds structured numerical data for statistical calculations
    (e.g. {"damage": 6, "vulnerable": 2}).  ``upgraded_effects`` mirrors it
    for the upgraded version.  ``description`` / ``upgraded_description`` are
    the human-readable text.
    """
    name: str
    card_type: CardType
    character: Character = Character.NEUTRAL
    rarity: Rarity = Rarity.COMMON
    cost: int = 0
    description: str = ""
    effects: dict[str, Any] = field(default_factory=dict)
    upgraded_cost: int | None = None  # None means same as base cost
    upgraded_description: str = ""
    upgraded_effects: dict[str, Any] = field(default_factory=dict)
    keywords: list[str] = field(default_factory=list)

    @property
    def effective_upgraded_cost(self) -> int:
        return self.upgraded_cost if self.upgraded_cost is not None else self.cost

    def __hash__(self) -> int:
        return hash((self.name, self.character))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Card):
            return NotImplemented
        return (self.name, self.character) == (other.name, other.character)

    def __str__(self) -> str:
        return f"{self.name} ({self.card_type.name}, {self.rarity.name}, cost={self.cost})"
