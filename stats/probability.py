"""Analytical probability helpers for Slay the Spire calculations."""

from __future__ import annotations

from math import comb

from models.card import Card, CardType
from models.deck import Deck


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


def expected_damage_output(
    deck: Deck,
    hand_size: int = 5,
    energy: int = 3,
    strength: int = 0,
    vulnerable: bool = False,
) -> float:
    """Rough expected damage from a random hand.

    Estimates average damage by considering the probability of drawing each
    attack, its energy cost, and its base damage.  Applies Strength bonus
    and Vulnerable multiplier.  Does *not* account for multi-hit or
    conditional effects — use the Simulator for complex scenarios.
    """
    vuln_mult = 1.5 if vulnerable else 1.0
    total_cards = deck.total_cards
    if total_cards == 0:
        return 0.0

    expected = 0.0
    for card in deck:
        if card.card_type != CardType.ATTACK:
            continue
        base_dmg = card.effects.get("damage", 0)
        if not isinstance(base_dmg, (int, float)):
            continue
        cost = card.cost if card.cost >= 0 else 0
        if cost > energy:
            continue

        copies = deck.card_counts().get(card, 0)
        p_in_hand = 1.0 - (
            comb(total_cards - copies, hand_size) / comb(total_cards, hand_size)
            if copies < total_cards and hand_size <= total_cards
            else 0.0
        )

        hits = card.effects.get("hits", 1)
        if not isinstance(hits, int):
            hits = 1
        dmg = (base_dmg + strength) * hits * vuln_mult
        expected += p_in_hand * dmg

    return expected
