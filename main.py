"""Slay the Spire Statistical Modeller — demo entry point."""

from models import Card, CardType, Character, Rarity, Deck, GameState
from models.game_state import STARTING_HP
from data import load_all_cards, load_character_cards, load_relics, load_potions, load_enemies
from stats import draw_probability, Simulator
from stats.probability import expected_damage_output


def build_starter_deck(character: Character) -> Deck:
    """Build the starting deck for a character from loaded card data."""
    cards = load_character_cards(character)
    by_name: dict[str, Card] = {c.name: c for c in cards}

    if character == Character.IRONCLAD:
        deck_cards = (
            [by_name["Strike"]] * 5
            + [by_name["Defend"]] * 4
            + [by_name["Bash"]]
        )
    elif character == Character.SILENT:
        deck_cards = (
            [by_name["Strike"]] * 5
            + [by_name["Defend"]] * 5
            + [by_name["Survivor"]]
            + [by_name["Neutralize"]]
        )
    elif character == Character.DEFECT:
        deck_cards = (
            [by_name["Strike"]] * 4
            + [by_name["Defend"]] * 4
            + [by_name["Zap"]]
            + [by_name["Dualcast"]]
        )
    elif character == Character.WATCHER:
        deck_cards = (
            [by_name["Strike"]] * 4
            + [by_name["Defend"]] * 4
            + [by_name["Eruption"]]
            + [by_name["Vigilance"]]
        )
    else:
        deck_cards = []

    return Deck(deck_cards)


def main() -> None:
    # -- Load all game data -------------------------------------------------
    all_cards = load_all_cards()
    relics = load_relics()
    potions = load_potions()
    enemies = load_enemies()

    print("=== Slay the Spire Data Summary ===")
    for source, cards in all_cards.items():
        print(f"  {source:12s}: {len(cards)} cards")
    print(f"  {'relics':12s}: {len(relics)}")
    print(f"  {'potions':12s}: {len(potions)}")
    print(f"  {'enemies':12s}: {len(enemies)}")
    print()

    # -- Starter deck analysis per character --------------------------------
    for char in [Character.IRONCLAD, Character.SILENT, Character.DEFECT, Character.WATCHER]:
        deck = build_starter_deck(char)
        deck.shuffle()

        cards = load_character_cards(char)
        by_name = {c.name: c for c in cards}
        strike = by_name["Strike"]

        p = draw_probability(deck, strike, draw_count=5)
        ed = expected_damage_output(deck, hand_size=5, energy=3)

        print(f"--- {char.value.upper()} (starter deck: {deck.total_cards} cards, {STARTING_HP[char]} HP) ---")
        print(f"  P(Strike in opener): {p:.1%}")
        print(f"  E[damage] from random hand: {ed:.1f}")
        print()

    # -- Monte-Carlo: Ironclad opening hand ---------------------------------
    print("=== Monte-Carlo: Ironclad opening hand (50k runs) ===")
    ironclad_cards = {c.name: c for c in load_character_cards(Character.IRONCLAD)}
    strike = ironclad_cards["Strike"]
    bash = ironclad_cards["Bash"]
    state = GameState(
        character=Character.IRONCLAD,
        deck=build_starter_deck(Character.IRONCLAD),
        hp=STARTING_HP[Character.IRONCLAD],
        max_hp=STARTING_HP[Character.IRONCLAD],
    )

    def opening_hand_analysis(gs: GameState) -> dict[str, float]:
        gs.next_turn(hand_size=5)
        hand = gs.deck.hand
        strikes = sum(1 for c in hand if c == strike)
        has_bash = 1.0 if bash in hand else 0.0
        total_damage = sum(
            c.effects.get("damage", 0)
            for c in hand
            if c.card_type == CardType.ATTACK
        )
        return {
            "strikes": strikes,
            "has_bash": has_bash,
            "raw_attack_damage": total_damage,
        }

    sim = Simulator(state)
    result = sim.run(opening_hand_analysis, iterations=50_000)
    for key, stats in result.summary().items():
        print(f"  {key}: mean={stats['mean']:.2f}, median={stats['median']:.1f}, "
              f"p25={stats['p25']:.1f}, p75={stats['p75']:.1f}")


if __name__ == "__main__":
    main()
