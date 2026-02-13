"""Analytical probability helpers for Slay the Spire calculations."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import comb

from models.card import Card, CardType
from models.deck import Deck
from models.relic import Relic


@dataclass
class RelicCombatModifiers:
    """Aggregated combat-relevant modifiers from a set of relics."""
    energy: int = 0
    strength: int = 0
    dexterity: int = 0
    draw: int = 0
    energy_turn1: int = 0
    strength_turn1: int = 0
    vulnerable: bool = False
    weak: bool = False
    vuln_multiplier: float | None = None
    weak_multiplier: float | None = None
    block_start: int = 0


def get_relic_combat_modifiers(relics: list[Relic]) -> RelicCombatModifiers:
    """Aggregate combat-relevant effects from a list of relics."""
    mods = RelicCombatModifiers()
    for relic in relics:
        e = relic.effects
        if not e:
            continue
        mods.energy += e.get("energy", 0)
        mods.strength += e.get("strength", 0)
        mods.dexterity += e.get("dexterity", 0)
        mods.draw += e.get("draw", 0)
        mods.energy_turn1 += e.get("energy_turn1", 0)
        mods.strength_turn1 += e.get("strength_turn1", 0)
        mods.block_start += e.get("block_start", 0)
        if e.get("vulnerable"):
            mods.vulnerable = True
        if e.get("weak"):
            mods.weak = True
        if "vuln_multiplier" in e:
            mods.vuln_multiplier = e["vuln_multiplier"]
        if "weak_multiplier" in e:
            mods.weak_multiplier = e["weak_multiplier"]
    return mods


def draw_probability(
    deck: Deck,
    target: Card,
    draw_count: int,
) -> float:
    """Probability of drawing at least one copy of *target* in *draw_count* cards.

    Uses the hypergeometric distribution:
        P(X >= 1) = 1 - C(N-K, n) / C(N, n)
    """
    total = deck.total_cards
    copies = deck.card_counts().get(target, 0)

    if copies == 0 or draw_count == 0:
        return 0.0
    if draw_count >= total:
        return 1.0

    p_miss = comb(total - copies, draw_count) / comb(total, draw_count)
    return 1.0 - p_miss


def _expected_bonus_energy(deck: Deck, hand_size: int) -> float:
    """Expected extra energy from energy-generating cards in the hand.

    For each card with a top-level ``energy`` effect, computes the expected
    copies drawn (hypergeometric mean = K * n / N) multiplied by the energy
    granted.  Conditional energy (e.g. ``if_vulnerable``) is ignored.
    """
    total_cards = deck.total_cards
    if total_cards == 0:
        return 0.0

    bonus = 0.0
    for card, copies in deck.card_counts().items():
        if card.card_type in (CardType.CURSE, CardType.STATUS):
            continue
        energy_gain = card.effects.get("energy", 0)
        if not isinstance(energy_gain, (int, float)) or energy_gain <= 0:
            continue
        e_copies = copies * hand_size / total_cards
        bonus += e_copies * energy_gain

    return bonus


def _energy_scale(deck: Deck, hand_size: int, energy: float) -> float:
    """Ratio to scale expected output when drawn cards exceed the energy budget.

    Computes the expected energy cost of all playable cards in the hand
    (hypergeometric mean) and returns ``min(1, energy / expected_cost)``.
    """
    total_cards = deck.total_cards
    if total_cards == 0:
        return 1.0

    demand = 0.0
    for card, copies in deck.card_counts().items():
        if card.card_type in (CardType.CURSE, CardType.STATUS):
            continue
        cost = card.cost if card.cost >= 0 else 0
        if cost > energy:
            continue
        demand += (copies * hand_size / total_cards) * cost

    return min(1.0, energy / demand) if demand > 0 else 1.0


def expected_damage_output(
    deck: Deck,
    hand_size: int = 5,
    energy: int = 3,
    strength: int = 0,
    vulnerable: bool = False,
    weak: bool = False,
    vuln_multiplier: float = 1.5,
    weak_multiplier: float = 0.75,
) -> float:
    """Rough expected damage from a random hand.

    For each unique attack, computes the expected number of copies drawn
    (hypergeometric mean = K * n / N) and multiplies by per-copy damage
    after Strength, Vulnerable, and Weak modifiers.  Scales the total down
    proportionally when the expected energy cost of all playable cards in the
    hand exceeds the energy budget.  Does *not* account for conditional
    effects or play-order optimisation — use the Simulator for complex
    scenarios.
    """
    vuln_mult = vuln_multiplier if vulnerable else 1.0
    weak_mult = weak_multiplier if weak else 1.0
    total_cards = deck.total_cards
    if total_cards == 0:
        return 0.0

    effective_energy = energy + _expected_bonus_energy(deck, hand_size)
    scale = _energy_scale(deck, hand_size, effective_energy)

    expected = 0.0
    for card, copies in deck.card_counts().items():
        if card.card_type != CardType.ATTACK:
            continue
        base_dmg = card.effects.get("damage", 0)
        if not isinstance(base_dmg, (int, float)):
            continue
        cost = card.cost if card.cost >= 0 else 0
        if cost > energy:
            continue

        e_copies = copies * hand_size / total_cards

        hits = card.effects.get("hits", 1)
        if not isinstance(hits, int):
            hits = 1
        dmg = (base_dmg + strength) * hits * vuln_mult * weak_mult
        expected += e_copies * dmg

    return expected * scale


def expected_block_output(
    deck: Deck,
    hand_size: int = 5,
    energy: int = 3,
    dexterity: int = 0,
) -> float:
    """Rough expected block from a random hand.

    For each unique card with a block effect, computes the expected number
    of copies drawn (hypergeometric mean = K * n / N) and multiplies by
    per-copy block after the Dexterity modifier.  Scales the total down
    proportionally when the expected energy cost of all playable cards in the
    hand exceeds the energy budget.  Does *not* account for conditional or
    scaling block effects — use the Simulator for complex scenarios.
    """
    total_cards = deck.total_cards
    if total_cards == 0:
        return 0.0

    effective_energy = energy + _expected_bonus_energy(deck, hand_size)
    scale = _energy_scale(deck, hand_size, effective_energy)

    expected = 0.0
    for card, copies in deck.card_counts().items():
        base_block = card.effects.get("block", 0)
        if not isinstance(base_block, (int, float)) or base_block <= 0:
            continue
        cost = card.cost if card.cost >= 0 else 0
        if cost > energy:
            continue

        e_copies = copies * hand_size / total_cards

        block = base_block + dexterity
        expected += e_copies * max(block, 0)

    return expected * scale
