from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from .card import Character
from .deck import Deck


class Stance(Enum):
    NONE = auto()
    WRATH = auto()
    CALM = auto()
    DIVINITY = auto()


class OrbType(Enum):
    LIGHTNING = auto()
    FROST = auto()
    DARK = auto()
    PLASMA = auto()


# Starting HP per character
STARTING_HP: dict[Character, int] = {
    Character.IRONCLAD: 80,
    Character.SILENT: 70,
    Character.DEFECT: 75,
    Character.WATCHER: 72,
}

# Base energy per turn
BASE_ENERGY = 3

# Default hand size
DEFAULT_HAND_SIZE = 5

# Ascension modifiers (ascension level -> list of effects)
ASCENSION_MODIFIERS: dict[int, str] = {
    1:  "Elites are more likely to spawn",
    2:  "Normal enemies are slightly harder",
    3:  "Elites are slightly harder",
    4:  "Boss is slightly harder",
    5:  "Heal less at rest sites (75%)",
    6:  "Start each run damaged (10% less HP for Ironclad, 2 less for others? Actually: lose starting HP)",
    7:  "Normal enemies are harder",
    8:  "Elites are harder",
    9:  "Boss is harder",
    10: "Start with a curse (Ascender's Bane)",
    11: "Heal less at rest sites (further reduced to ~65%)",
    12: "Upgraded cards in boss reward no longer guaranteed",
    13: "Normal enemies have more challenging patterns",
    14: "Elites have more challenging patterns",
    15: "Boss has more challenging patterns",
    16: "Strike and Defend are worse (Strike deals 5, Defend gives 4)",
    17: "Normal enemies have even more HP",
    18: "Elites have even more HP",
    19: "Boss has even more HP",
    20: "Double boss on Act 1 and Act 2 (two boss options; Act 3 boss + the Heart)",
}


@dataclass
class GameState:
    """Full snapshot of a Slay the Spire run in progress."""

    character: Character = Character.IRONCLAD
    deck: Deck = field(default_factory=Deck)
    turn: int = 0
    act: int = 1
    floor: int = 0
    ascension: int = 0

    # Combat state
    hp: int = 80
    max_hp: int = 80
    energy: int = BASE_ENERGY
    max_energy: int = BASE_ENERGY
    block: int = 0
    gold: int = 99

    # Buffs / debuffs
    strength: int = 0
    dexterity: int = 0
    focus: int = 0  # Defect
    mantra: int = 0  # Watcher
    stance: Stance = Stance.NONE  # Watcher

    # Defect orbs: list of OrbType
    orb_slots: int = 3
    orbs: list[OrbType] = field(default_factory=list)

    # Relics held (by name for simplicity)
    relics: list[str] = field(default_factory=list)
    potions: list[str] = field(default_factory=list)

    def next_turn(self, hand_size: int = DEFAULT_HAND_SIZE) -> None:
        self.block = 0
        self.deck.discard_hand()
        self.deck.draw(hand_size)
        self.energy = self.max_energy
        self.turn += 1
