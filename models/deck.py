from __future__ import annotations

import random
from collections import Counter
from typing import Iterator

from .card import Card


class Deck:
    """A mutable collection of cards with draw/discard/shuffle support."""

    def __init__(self, cards: list[Card] | None = None) -> None:
        self._draw_pile: list[Card] = list(cards) if cards else []
        self._discard_pile: list[Card] = []
        self._hand: list[Card] = []

    # -- Deck manipulation ---------------------------------------------------

    def shuffle(self) -> None:
        random.shuffle(self._draw_pile)

    def draw(self, n: int = 1) -> list[Card]:
        """Draw *n* cards. Reshuffles discard into draw pile when needed."""
        drawn: list[Card] = []
        for _ in range(n):
            if not self._draw_pile:
                if not self._discard_pile:
                    break
                self._draw_pile = self._discard_pile
                self._discard_pile = []
                self.shuffle()
            drawn.append(self._draw_pile.pop())
        self._hand.extend(drawn)
        return drawn

    def discard_hand(self) -> None:
        self._discard_pile.extend(self._hand)
        self._hand.clear()

    def add(self, card: Card) -> None:
        """Add a card to the draw pile (e.g. when purchasing/gaining)."""
        self._draw_pile.append(card)

    def remove(self, card: Card) -> bool:
        """Remove a card from wherever it currently lives. Returns success."""
        for pile in (self._hand, self._draw_pile, self._discard_pile):
            if card in pile:
                pile.remove(card)
                return True
        return False

    # -- Queries -------------------------------------------------------------

    @property
    def hand(self) -> list[Card]:
        return list(self._hand)

    @property
    def draw_pile_size(self) -> int:
        return len(self._draw_pile)

    @property
    def discard_pile_size(self) -> int:
        return len(self._discard_pile)

    @property
    def total_cards(self) -> int:
        return len(self._draw_pile) + len(self._discard_pile) + len(self._hand)

    def card_counts(self) -> Counter[Card]:
        """Frequency of each card across all piles."""
        return Counter(self._draw_pile + self._discard_pile + self._hand)

    def __iter__(self) -> Iterator[Card]:
        yield from self._draw_pile
        yield from self._discard_pile
        yield from self._hand

    def __len__(self) -> int:
        return self.total_cards
