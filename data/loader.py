"""Loaders for all Slay the Spire data files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from models.card import Card, CardType, Character, Rarity
from models.enemy import Enemy, EnemyType
from models.potion import Potion, PotionRarity
from models.relic import Relic, RelicRarity

DATA_DIR = Path(__file__).resolve().parent
CARDS_DIR = DATA_DIR / "cards"

_CARD_TYPE_MAP = {v.name: v for v in CardType}
_RARITY_MAP = {v.name: v for v in Rarity}
_CHARACTER_MAP = {v.name: v for v in Character}
_CHARACTER_MAP["ANY"] = Character.NEUTRAL  # alias used in JSON files
_ENEMY_TYPE_MAP = {v.name: v for v in EnemyType}
_RELIC_RARITY_MAP = {v.name: v for v in RelicRarity}
_POTION_RARITY_MAP = {v.name: v for v in PotionRarity}


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------

def _parse_card(entry: dict[str, Any], character: Character) -> Card:
    rarity_str = entry.get("rarity", "COMMON")
    return Card(
        name=entry["name"],
        card_type=_CARD_TYPE_MAP[entry["type"]],
        character=character,
        rarity=_RARITY_MAP.get(rarity_str, Rarity.SPECIAL),
        cost=entry.get("cost", 0),
        description=entry.get("description", ""),
        effects=entry.get("effects", {}),
        upgraded_cost=entry.get("upgraded_cost"),
        upgraded_description=entry.get("upgraded_description", ""),
        upgraded_effects=entry.get("upgraded_effects", {}),
        keywords=entry.get("keywords", []),
    )


def load_character_cards(character: Character) -> list[Card]:
    """Load all cards for a specific character from its JSON file."""
    filename = {
        Character.IRONCLAD: "ironclad.json",
        Character.SILENT: "silent.json",
        Character.DEFECT: "defect.json",
        Character.WATCHER: "watcher.json",
        Character.COLORLESS: "colorless.json",
    }.get(character)
    if filename is None:
        return []
    path = CARDS_DIR / filename
    if not path.exists():
        return []
    with open(path) as f:
        raw = json.load(f)
    return [_parse_card(entry, character) for entry in raw]


def load_curses() -> list[Card]:
    path = CARDS_DIR / "curses.json"
    if not path.exists():
        return []
    with open(path) as f:
        raw = json.load(f)
    return [_parse_card(entry, Character.NEUTRAL) for entry in raw]


def load_statuses() -> list[Card]:
    path = CARDS_DIR / "status.json"
    if not path.exists():
        return []
    with open(path) as f:
        raw = json.load(f)
    return [_parse_card(entry, Character.NEUTRAL) for entry in raw]


def load_all_cards() -> dict[str, list[Card]]:
    """Load every card in the game, keyed by source."""
    return {
        "ironclad": load_character_cards(Character.IRONCLAD),
        "silent": load_character_cards(Character.SILENT),
        "defect": load_character_cards(Character.DEFECT),
        "watcher": load_character_cards(Character.WATCHER),
        "colorless": load_character_cards(Character.COLORLESS),
        "curses": load_curses(),
        "statuses": load_statuses(),
    }


# ---------------------------------------------------------------------------
# Relics
# ---------------------------------------------------------------------------

def load_relics() -> list[Relic]:
    path = DATA_DIR / "relics.json"
    with open(path) as f:
        raw = json.load(f)
    relics: list[Relic] = []
    for entry in raw:
        char_str = entry.get("character", "ANY")
        character = _CHARACTER_MAP.get(char_str, Character.NEUTRAL)
        rarity = _RELIC_RARITY_MAP.get(entry.get("rarity", "COMMON"), RelicRarity.COMMON)
        relics.append(Relic(
            name=entry["name"],
            rarity=rarity,
            description=entry.get("description", ""),
            character=character,
        ))
    return relics


# ---------------------------------------------------------------------------
# Potions
# ---------------------------------------------------------------------------

def load_potions() -> list[Potion]:
    path = DATA_DIR / "potions.json"
    with open(path) as f:
        raw = json.load(f)
    potions: list[Potion] = []
    for entry in raw:
        char_str = entry.get("character", "ANY")
        character = _CHARACTER_MAP.get(char_str, Character.NEUTRAL)
        rarity = _POTION_RARITY_MAP.get(entry.get("rarity", "COMMON"), PotionRarity.COMMON)
        potions.append(Potion(
            name=entry["name"],
            rarity=rarity,
            description=entry.get("description", ""),
            character=character,
        ))
    return potions


# ---------------------------------------------------------------------------
# Enemies
# ---------------------------------------------------------------------------

def load_enemies() -> list[Enemy]:
    path = DATA_DIR / "enemies.json"
    with open(path) as f:
        raw = json.load(f)
    enemies: list[Enemy] = []
    for entry in raw:
        enemies.append(Enemy(
            name=entry["name"],
            enemy_type=_ENEMY_TYPE_MAP[entry["type"]],
            act=entry["act"],
            hp_min=entry.get("hp_min", 0),
            hp_max=entry.get("hp_max", 0),
            moves=entry.get("moves", []),
        ))
    return enemies
