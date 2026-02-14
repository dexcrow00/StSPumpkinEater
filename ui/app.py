"""Slay the Spire Statistical Modeller — tkinter GUI application."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Any, Callable

# Ensure project root is on sys.path so imports work when run directly.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from data import (
    load_all_cards,
    load_character_cards,
    load_enemies,
    load_potions,
    load_relics,
)
from models import Card, CardType, Character, Deck, Rarity
from models.enemy import Enemy, EnemyType
from models.potion import Potion, PotionRarity
from models.relic import Relic, RelicRarity
from stats.probability import (
    RelicCombatModifiers,
    draw_probability,
    expected_block_output,
    expected_damage_output,
    get_relic_combat_modifiers,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COST_DISPLAY = {-1: "X", -2: "U"}


def _cost_str(cost: int) -> str:
    return _COST_DISPLAY.get(cost, str(cost))


# ---------------------------------------------------------------------------
# Theme — dark palette inspired by Slay the Spire
# ---------------------------------------------------------------------------

THEME = {
    "bg":          "#1a1a2e",   # main background
    "bg_mid":      "#16213e",   # panels / frames
    "bg_light":    "#0f3460",   # inputs / lighter surfaces
    "accent":      "#e94560",   # primary accent (crimson)
    "gold":        "#f5c518",   # secondary accent
    "text":        "#ecf0f1",   # primary text
    "text_dim":    "#8899aa",   # secondary text
    "row_even":    "#1e2a3a",   # treeview even row
    "row_odd":     "#162033",   # treeview odd row
    "select_bg":   "#e94560",   # selection background
    "select_fg":   "#ffffff",   # selection foreground
    "border":      "#2a3a5c",   # subtle borders
    "detail_bg":   "#111827",   # detail pane background
}


# ---------------------------------------------------------------------------
# AppData — single load of all game data
# ---------------------------------------------------------------------------

class AppData:
    """Loads and holds all game data for the GUI."""

    def __init__(self) -> None:
        all_cards = load_all_cards()
        self.cards: list[Card] = []
        for card_list in all_cards.values():
            self.cards.extend(card_list)

        self.relics: list[Relic] = load_relics()
        self.potions: list[Potion] = load_potions()
        self.enemies: list[Enemy] = load_enemies()

        # Pre-compute filter value sets
        self.card_characters = sorted({c.character.value for c in self.cards})
        self.card_types = sorted({c.card_type.name for c in self.cards})
        self.card_rarities = sorted({c.rarity.name for c in self.cards})
        self.card_costs = sorted({_cost_str(c.cost) for c in self.cards},
                                 key=lambda x: (x not in ("X", "U"), x))

        self.relic_rarities = sorted({r.rarity.name for r in self.relics})
        self.relic_characters = sorted({r.character.value for r in self.relics})

        self.potion_rarities = sorted({p.rarity.name for p in self.potions})
        self.potion_characters = sorted({p.character.value for p in self.potions})

        self.enemy_types = sorted({e.enemy_type.name for e in self.enemies})
        self.enemy_acts = sorted({str(e.act) for e in self.enemies})

    def get_starter_deck_cards(self, character: Character) -> list[Card]:
        cards = load_character_cards(character)
        by_name: dict[str, Card] = {c.name: c for c in cards}

        if character == Character.IRONCLAD:
            return ([by_name["Strike"]] * 5
                    + [by_name["Defend"]] * 4
                    + [by_name["Bash"]])
        elif character == Character.SILENT:
            return ([by_name["Strike"]] * 5
                    + [by_name["Defend"]] * 5
                    + [by_name["Survivor"]]
                    + [by_name["Neutralize"]])
        elif character == Character.DEFECT:
            return ([by_name["Strike"]] * 4
                    + [by_name["Defend"]] * 4
                    + [by_name["Zap"]]
                    + [by_name["Dualcast"]])
        elif character == Character.WATCHER:
            return ([by_name["Strike"]] * 4
                    + [by_name["Defend"]] * 4
                    + [by_name["Eruption"]]
                    + [by_name["Vigilance"]])
        return []

    def get_starter_relic(self, character: Character) -> Relic | None:
        """Return the starter relic for a character."""
        starter_names = {
            Character.IRONCLAD: "Burning Blood",
            Character.SILENT: "Ring of the Snake",
            Character.DEFECT: "Cracked Core",
            Character.WATCHER: "Pure Water",
        }
        name = starter_names.get(character)
        if name is None:
            return None
        for r in self.relics:
            if r.name == name:
                return r
        return None

    def cards_for_character(self, character: Character) -> list[Card]:
        """Return cards available to a character (their own + colorless + curses)."""
        return [c for c in self.cards
                if c.character == character
                or c.character == Character.COLORLESS
                or c.card_type == CardType.CURSE]


# ---------------------------------------------------------------------------
# FilterableTreeview — reusable composite widget
# ---------------------------------------------------------------------------

class FilterableTreeview(ttk.Frame):
    """Search + filters + sortable Treeview + detail pane."""

    def __init__(
        self,
        parent: tk.Widget,
        columns: list[tuple[str, str, int]],  # (col_id, heading, width)
        items: list[Any],
        item_to_row: Callable[[Any], tuple],
        item_matches_filters: Callable[[Any, str, dict[str, str]], bool],
        detail_formatter: Callable[[Any], str],
        filters: list[tuple[str, str, list[str]]] | None = None,  # (key, label, values)
    ) -> None:
        super().__init__(parent)
        self._items = items
        self._item_to_row = item_to_row
        self._item_matches_filters = item_matches_filters
        self._detail_formatter = detail_formatter
        self._filter_vars: dict[str, tk.StringVar] = {}
        self._debounce_id: str | None = None
        self._sort_col: str | None = None
        self._sort_reverse = False

        # --- Top bar: search + filters ---
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, padx=4, pady=(4, 2))

        ttk.Label(bar, text="Search:").pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_filter_changed)
        search_entry = ttk.Entry(bar, textvariable=self._search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=(4, 8))

        if filters:
            for key, label, values in filters:
                ttk.Label(bar, text=f"{label}:").pack(side=tk.LEFT, padx=(4, 0))
                var = tk.StringVar(value="All")
                self._filter_vars[key] = var
                cb = ttk.Combobox(bar, textvariable=var, values=["All"] + values,
                                  state="readonly", width=12)
                cb.pack(side=tk.LEFT, padx=(2, 4))
                cb.bind("<<ComboboxSelected>>", self._on_filter_changed)

        # --- Paned: tree + detail ---
        paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        # Treeview
        tree_frame = ttk.Frame(paned)
        col_ids = [c[0] for c in columns]
        self._tree = ttk.Treeview(tree_frame, columns=col_ids, show="headings",
                                  selectmode="browse")
        for col_id, heading, width in columns:
            self._tree.heading(col_id, text=heading,
                               command=lambda c=col_id: self._sort_by(c))
            self._tree.column(col_id, width=width, minwidth=40)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        paned.add(tree_frame, weight=3)

        # Detail pane
        detail_frame = ttk.Frame(paned)
        self._detail = tk.Text(detail_frame, wrap=tk.WORD, height=6,
                               state=tk.DISABLED, font=("TkDefaultFont", 12),
                               background=THEME["detail_bg"],
                               foreground=THEME["text"],
                               insertbackground=THEME["text"],
                               selectbackground=THEME["select_bg"],
                               selectforeground=THEME["select_fg"],
                               relief=tk.FLAT, borderwidth=0)
        detail_sb = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL,
                                  command=self._detail.yview)
        self._detail.configure(yscrollcommand=detail_sb.set)
        self._detail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_sb.pack(side=tk.RIGHT, fill=tk.Y)

        paned.add(detail_frame, weight=1)

        # Map iid → item for selection lookup
        self._iid_to_item: dict[str, Any] = {}

        self._populate()

    # --- Public API ---

    def set_items(self, items: list[Any]) -> None:
        self._items = items
        self._populate()

    # --- Internals ---

    def _populate(self) -> None:
        self._tree.delete(*self._tree.get_children())
        self._iid_to_item.clear()
        search = self._search_var.get().strip().lower()
        filter_vals = {k: v.get() for k, v in self._filter_vars.items()}

        rows: list[tuple[str, tuple]] = []
        for idx, item in enumerate(self._items):
            if not self._item_matches_filters(item, search, filter_vals):
                continue
            row = self._item_to_row(item)
            iid = str(idx)
            rows.append((iid, row, item))

        # Apply sort if active
        if self._sort_col is not None:
            col_ids = [c for c in self._tree["columns"]]
            try:
                col_idx = col_ids.index(self._sort_col)
            except ValueError:
                col_idx = 0
            rows.sort(key=lambda r: r[1][col_idx], reverse=self._sort_reverse)

        tag_even = False
        for iid, row, item in rows:
            tag = "even" if tag_even else "odd"
            self._tree.insert("", tk.END, iid=iid, values=row, tags=(tag,))
            self._iid_to_item[iid] = item
            tag_even = not tag_even

        self._tree.tag_configure("even", background=THEME["row_even"],
                                 foreground=THEME["text"])
        self._tree.tag_configure("odd", background=THEME["row_odd"],
                                foreground=THEME["text"])

        # Clear detail
        self._detail.configure(state=tk.NORMAL)
        self._detail.delete("1.0", tk.END)
        self._detail.configure(state=tk.DISABLED)

    def _on_filter_changed(self, *_args: Any) -> None:
        if self._debounce_id is not None:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(150, self._populate)

    def _on_select(self, _event: tk.Event) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        item = self._iid_to_item.get(sel[0])
        if item is None:
            return
        text = self._detail_formatter(item)
        self._detail.configure(state=tk.NORMAL)
        self._detail.delete("1.0", tk.END)
        self._detail.insert("1.0", text)
        self._detail.configure(state=tk.DISABLED)

    def _sort_by(self, col: str) -> None:
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False
        self._populate()


# ---------------------------------------------------------------------------
# Data Browser Tab (inner notebook with Cards / Relics / Potions / Enemies)
# ---------------------------------------------------------------------------

class DataBrowserTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, data: AppData) -> None:
        super().__init__(parent)
        self._data = data
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True)

        nb.add(self._build_cards_tab(nb), text="Cards")
        nb.add(self._build_relics_tab(nb), text="Relics")
        nb.add(self._build_potions_tab(nb), text="Potions")
        nb.add(self._build_enemies_tab(nb), text="Enemies")

    # --- Cards ---
    def _build_cards_tab(self, parent: tk.Widget) -> FilterableTreeview:
        columns = [
            ("name", "Name", 160),
            ("character", "Character", 90),
            ("type", "Type", 80),
            ("rarity", "Rarity", 80),
            ("cost", "Cost", 50),
        ]
        filters = [
            ("character", "Character", self._data.card_characters),
            ("type", "Type", self._data.card_types),
            ("rarity", "Rarity", self._data.card_rarities),
        ]
        return FilterableTreeview(
            parent,
            columns=columns,
            items=self._data.cards,
            item_to_row=self._card_row,
            item_matches_filters=self._card_filter,
            detail_formatter=self._card_detail,
            filters=filters,
        )

    @staticmethod
    def _card_row(card: Card) -> tuple:
        return (card.name, card.character.value, card.card_type.name,
                card.rarity.name, _cost_str(card.cost))

    @staticmethod
    def _card_filter(card: Card, search: str, filters: dict[str, str]) -> bool:
        if search and search not in card.name.lower():
            return False
        if filters.get("character", "All") != "All" and card.character.value != filters["character"]:
            return False
        if filters.get("type", "All") != "All" and card.card_type.name != filters["type"]:
            return False
        if filters.get("rarity", "All") != "All" and card.rarity.name != filters["rarity"]:
            return False
        return True

    @staticmethod
    def _card_detail(card: Card) -> str:
        lines = [
            f"{card.name}",
            f"Type: {card.card_type.name}  |  Rarity: {card.rarity.name}  |  "
            f"Cost: {_cost_str(card.cost)}  |  Character: {card.character.value}",
            "",
        ]
        if card.description:
            lines.append(card.description)
            lines.append("")
        if card.effects:
            lines.append("Effects: " + ", ".join(f"{k}={v}" for k, v in card.effects.items()))
        if card.keywords:
            lines.append("Keywords: " + ", ".join(card.keywords))
        if card.upgraded_description or card.upgraded_effects:
            lines.append("")
            lines.append("--- Upgraded ---")
            if card.upgraded_cost is not None:
                lines.append(f"Cost: {_cost_str(card.effective_upgraded_cost)}")
            if card.upgraded_description:
                lines.append(card.upgraded_description)
            if card.upgraded_effects:
                lines.append("Effects: " + ", ".join(
                    f"{k}={v}" for k, v in card.upgraded_effects.items()))
        return "\n".join(lines)

    # --- Relics ---
    def _build_relics_tab(self, parent: tk.Widget) -> FilterableTreeview:
        columns = [
            ("name", "Name", 180),
            ("rarity", "Rarity", 100),
            ("character", "Character", 100),
        ]
        filters = [
            ("rarity", "Rarity", self._data.relic_rarities),
            ("character", "Character", self._data.relic_characters),
        ]
        return FilterableTreeview(
            parent,
            columns=columns,
            items=self._data.relics,
            item_to_row=lambda r: (r.name, r.rarity.name, r.character.value),
            item_matches_filters=self._relic_filter,
            detail_formatter=lambda r: f"{r.name}\nRarity: {r.rarity.name}  |  "
                                       f"Character: {r.character.value}\n\n{r.description}",
            filters=filters,
        )

    @staticmethod
    def _relic_filter(relic: Relic, search: str, filters: dict[str, str]) -> bool:
        if search and search not in relic.name.lower():
            return False
        if filters.get("rarity", "All") != "All" and relic.rarity.name != filters["rarity"]:
            return False
        if filters.get("character", "All") != "All" and relic.character.value != filters["character"]:
            return False
        return True

    # --- Potions ---
    def _build_potions_tab(self, parent: tk.Widget) -> FilterableTreeview:
        columns = [
            ("name", "Name", 180),
            ("rarity", "Rarity", 100),
            ("character", "Character", 100),
        ]
        filters = [
            ("rarity", "Rarity", self._data.potion_rarities),
            ("character", "Character", self._data.potion_characters),
        ]
        return FilterableTreeview(
            parent,
            columns=columns,
            items=self._data.potions,
            item_to_row=lambda p: (p.name, p.rarity.name, p.character.value),
            item_matches_filters=self._potion_filter,
            detail_formatter=lambda p: f"{p.name}\nRarity: {p.rarity.name}  |  "
                                       f"Character: {p.character.value}\n\n{p.description}",
            filters=filters,
        )

    @staticmethod
    def _potion_filter(potion: Potion, search: str, filters: dict[str, str]) -> bool:
        if search and search not in potion.name.lower():
            return False
        if filters.get("rarity", "All") != "All" and potion.rarity.name != filters["rarity"]:
            return False
        if filters.get("character", "All") != "All" and potion.character.value != filters["character"]:
            return False
        return True

    # --- Enemies ---
    def _build_enemies_tab(self, parent: tk.Widget) -> FilterableTreeview:
        columns = [
            ("name", "Name", 180),
            ("type", "Type", 80),
            ("act", "Act", 50),
            ("hp", "HP", 100),
        ]
        filters = [
            ("type", "Type", self._data.enemy_types),
            ("act", "Act", self._data.enemy_acts),
        ]
        return FilterableTreeview(
            parent,
            columns=columns,
            items=self._data.enemies,
            item_to_row=lambda e: (e.name, e.enemy_type.name, str(e.act),
                                   f"{e.hp_min}-{e.hp_max}"),
            item_matches_filters=self._enemy_filter,
            detail_formatter=self._enemy_detail,
            filters=filters,
        )

    @staticmethod
    def _enemy_filter(enemy: Enemy, search: str, filters: dict[str, str]) -> bool:
        if search and search not in enemy.name.lower():
            return False
        if filters.get("type", "All") != "All" and enemy.enemy_type.name != filters["type"]:
            return False
        if filters.get("act", "All") != "All" and str(enemy.act) != filters["act"]:
            return False
        return True

    @staticmethod
    def _enemy_detail(enemy: Enemy) -> str:
        lines = [
            enemy.name,
            f"Type: {enemy.enemy_type.name}  |  Act: {enemy.act}  |  "
            f"HP: {enemy.hp_min}-{enemy.hp_max}",
            "",
            "Moves:",
        ]
        for move in enemy.moves:
            name = move.get("name", "?")
            parts = [f"  {name}"]
            if "damage" in move:
                dmg = move["damage"]
                hits = move.get("hits", 1)
                if hits > 1:
                    parts.append(f"  {dmg}x{hits} damage")
                else:
                    parts.append(f"  {dmg} damage")
            if "block" in move:
                parts.append(f"  {move['block']} block")
            extras = {k: v for k, v in move.items()
                      if k not in ("name", "damage", "block", "hits")}
            if extras:
                parts.append("  " + ", ".join(f"{k}={v}" for k, v in extras.items()))
            lines.append(" | ".join(parts))
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deck Builder Tab
# ---------------------------------------------------------------------------

class DeckBuilderTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, data: AppData) -> None:
        super().__init__(parent)
        self._data = data
        self._deck_cards: list[Card] = []
        self._selected_relics: list[Relic] = []

        # --- Top bar ---
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=6, pady=4)

        ttk.Label(top, text="Character:").pack(side=tk.LEFT)
        self._char_var = tk.StringVar(value=Character.IRONCLAD.value)
        char_values = [c.value for c in Character
                       if c not in (Character.COLORLESS, Character.NEUTRAL)]
        char_cb = ttk.Combobox(top, textvariable=self._char_var, values=char_values,
                               state="readonly", width=12)
        char_cb.pack(side=tk.LEFT, padx=(4, 12))
        char_cb.bind("<<ComboboxSelected>>", self._on_character_changed)

        ttk.Button(top, text="Load Starter Deck",
                   command=self._load_starter).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Clear Deck",
                   command=self._clear_deck).pack(side=tk.LEFT, padx=4)

        # --- Vertical paned: cards section | relic section ---
        vpaned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        vpaned.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        # === Cards section ===
        cards_frame = ttk.Frame(vpaned)

        card_paned = ttk.PanedWindow(cards_frame, orient=tk.HORIZONTAL)
        card_paned.pack(fill=tk.BOTH, expand=True)

        # Left: card catalog
        left = ttk.Frame(card_paned)
        ttk.Label(left, text="Card Catalog", font=("TkDefaultFont", 12, "bold")).pack(
            anchor=tk.W, padx=4, pady=(2, 0))
        self._catalog = FilterableTreeview(
            left,
            columns=[
                ("name", "Name", 140),
                ("type", "Type", 70),
                ("rarity", "Rarity", 70),
                ("cost", "Cost", 45),
            ],
            items=self._data.cards_for_character(Character.IRONCLAD),
            item_to_row=lambda c: (c.name, c.card_type.name, c.rarity.name,
                                   _cost_str(c.cost)),
            item_matches_filters=self._catalog_filter,
            detail_formatter=DataBrowserTab._card_detail,
            filters=[
                ("source", "Source", ["Character", "Colorless", "Curse"]),
                ("type", "Type", self._data.card_types),
                ("rarity", "Rarity", self._data.card_rarities),
            ],
        )
        self._catalog.pack(fill=tk.BOTH, expand=True)

        add_btn = ttk.Button(left, text="Add to Deck >>", command=self._add_selected)
        add_btn.pack(pady=4)
        self._catalog._tree.bind("<Double-1>", lambda e: self._add_selected())

        card_paned.add(left, weight=1)

        # Right: deck contents
        right = ttk.Frame(card_paned)
        ttk.Label(right, text="Deck Contents", font=("TkDefaultFont", 12, "bold")).pack(
            anchor=tk.W, padx=4, pady=(2, 0))

        deck_tree_frame = ttk.Frame(right)
        deck_tree_frame.pack(fill=tk.BOTH, expand=True, padx=4)

        deck_cols = [("name", "Name", 140), ("qty", "Qty", 40),
                     ("type", "Type", 70), ("cost", "Cost", 45)]
        self._deck_tree = ttk.Treeview(
            deck_tree_frame, columns=[c[0] for c in deck_cols],
            show="headings", selectmode="browse")
        for col_id, heading, width in deck_cols:
            self._deck_tree.heading(col_id, text=heading)
            self._deck_tree.column(col_id, width=width, minwidth=30)
        deck_vsb = ttk.Scrollbar(deck_tree_frame, orient=tk.VERTICAL,
                                 command=self._deck_tree.yview)
        self._deck_tree.configure(yscrollcommand=deck_vsb.set)
        self._deck_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        deck_vsb.pack(side=tk.RIGHT, fill=tk.Y)

        remove_btn = ttk.Button(right, text="<< Remove from Deck",
                                command=self._remove_selected)
        remove_btn.pack(pady=4)
        self._deck_tree.bind("<Double-1>", lambda e: self._remove_selected())

        # Summary
        self._summary_var = tk.StringVar(value="Deck: 0 cards")
        ttk.Label(right, textvariable=self._summary_var,
                  font=("TkDefaultFont", 11)).pack(anchor=tk.W, padx=6, pady=(0, 4))

        card_paned.add(right, weight=1)

        vpaned.add(cards_frame, weight=3)

        # === Relic section ===
        relic_frame = ttk.Frame(vpaned)

        relic_paned = ttk.PanedWindow(relic_frame, orient=tk.HORIZONTAL)
        relic_paned.pack(fill=tk.BOTH, expand=True)

        # Left: relic catalog
        relic_left = ttk.Frame(relic_paned)
        ttk.Label(relic_left, text="Relic Catalog",
                  font=("TkDefaultFont", 12, "bold")).pack(
            anchor=tk.W, padx=4, pady=(2, 0))
        self._relic_catalog = FilterableTreeview(
            relic_left,
            columns=[
                ("name", "Name", 160),
                ("rarity", "Rarity", 80),
                ("character", "Character", 80),
            ],
            items=self._data.relics,
            item_to_row=lambda r: (r.name, r.rarity.name, r.character.value),
            item_matches_filters=self._relic_catalog_filter,
            detail_formatter=self._relic_detail,
            filters=[
                ("rarity", "Rarity", self._data.relic_rarities),
                ("character", "Character", self._data.relic_characters),
            ],
        )
        self._relic_catalog.pack(fill=tk.BOTH, expand=True)

        relic_add_btn = ttk.Button(relic_left, text="Add Relic >>",
                                   command=self._add_relic)
        relic_add_btn.pack(pady=4)
        self._relic_catalog._tree.bind("<Double-1>", lambda e: self._add_relic())

        relic_paned.add(relic_left, weight=1)

        # Right: selected relics
        relic_right = ttk.Frame(relic_paned)
        ttk.Label(relic_right, text="Selected Relics",
                  font=("TkDefaultFont", 12, "bold")).pack(
            anchor=tk.W, padx=4, pady=(2, 0))

        relic_sel_frame = ttk.Frame(relic_right)
        relic_sel_frame.pack(fill=tk.BOTH, expand=True, padx=4)

        relic_sel_cols = [("name", "Name", 160), ("rarity", "Rarity", 80)]
        self._relic_sel_tree = ttk.Treeview(
            relic_sel_frame, columns=[c[0] for c in relic_sel_cols],
            show="headings", selectmode="browse")
        for col_id, heading, width in relic_sel_cols:
            self._relic_sel_tree.heading(col_id, text=heading)
            self._relic_sel_tree.column(col_id, width=width, minwidth=30)
        relic_sel_vsb = ttk.Scrollbar(relic_sel_frame, orient=tk.VERTICAL,
                                      command=self._relic_sel_tree.yview)
        self._relic_sel_tree.configure(yscrollcommand=relic_sel_vsb.set)
        self._relic_sel_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        relic_sel_vsb.pack(side=tk.RIGHT, fill=tk.Y)

        relic_remove_btn = ttk.Button(relic_right, text="<< Remove Relic",
                                      command=self._remove_relic)
        relic_remove_btn.pack(pady=4)
        self._relic_sel_tree.bind("<Double-1>", lambda e: self._remove_relic())

        self._relic_summary_var = tk.StringVar(value="Relics: 0")
        ttk.Label(relic_right, textvariable=self._relic_summary_var,
                  font=("TkDefaultFont", 11)).pack(anchor=tk.W, padx=6, pady=(0, 4))

        relic_paned.add(relic_right, weight=1)

        vpaned.add(relic_frame, weight=1)

    # --- Public API ---

    def get_deck(self) -> Deck:
        return Deck(list(self._deck_cards))

    def get_deck_cards(self) -> list[Card]:
        return list(self._deck_cards)

    def get_selected_relics(self) -> list[Relic]:
        return list(self._selected_relics)

    # --- Internals ---

    def _selected_character(self) -> Character:
        val = self._char_var.get()
        for c in Character:
            if c.value == val:
                return c
        return Character.IRONCLAD

    def _on_character_changed(self, *_args: Any) -> None:
        char = self._selected_character()
        self._catalog.set_items(self._data.cards_for_character(char))

    def _load_starter(self) -> None:
        char = self._selected_character()
        self._deck_cards = self._data.get_starter_deck_cards(char)
        self._refresh_deck_tree()
        # Also load starter relic
        self._selected_relics.clear()
        starter = self._data.get_starter_relic(char)
        if starter is not None:
            self._selected_relics.append(starter)
        self._refresh_relic_sel_tree()

    def _clear_deck(self) -> None:
        self._deck_cards.clear()
        self._refresh_deck_tree()
        self._selected_relics.clear()
        self._refresh_relic_sel_tree()

    def _add_selected(self) -> None:
        sel = self._catalog._tree.selection()
        if not sel:
            return
        item = self._catalog._iid_to_item.get(sel[0])
        if item is not None:
            self._deck_cards.append(item)
            self._refresh_deck_tree()

    def _remove_selected(self) -> None:
        sel = self._deck_tree.selection()
        if not sel:
            return
        iid = sel[0]
        card = self._deck_iid_to_card.get(iid)
        if card is not None and card in self._deck_cards:
            self._deck_cards.remove(card)
            self._refresh_deck_tree()

    def _add_relic(self) -> None:
        sel = self._relic_catalog._tree.selection()
        if not sel:
            return
        relic = self._relic_catalog._iid_to_item.get(sel[0])
        if relic is not None and relic not in self._selected_relics:
            self._selected_relics.append(relic)
            self._refresh_relic_sel_tree()

    def _remove_relic(self) -> None:
        sel = self._relic_sel_tree.selection()
        if not sel:
            return
        iid = sel[0]
        relic = self._relic_iid_to_relic.get(iid)
        if relic is not None and relic in self._selected_relics:
            self._selected_relics.remove(relic)
            self._refresh_relic_sel_tree()

    def _refresh_deck_tree(self) -> None:
        self._deck_tree.delete(*self._deck_tree.get_children())
        self._deck_iid_to_card: dict[str, Card] = {}

        # Group by card identity
        from collections import Counter
        counts: Counter[Card] = Counter(self._deck_cards)
        tag_even = False
        for idx, (card, qty) in enumerate(sorted(counts.items(), key=lambda x: x[0].name)):
            iid = str(idx)
            tag = "even" if tag_even else "odd"
            self._deck_tree.insert("", tk.END, iid=iid,
                                   values=(card.name, qty, card.card_type.name,
                                           _cost_str(card.cost)),
                                   tags=(tag,))
            self._deck_iid_to_card[iid] = card
            tag_even = not tag_even

        self._deck_tree.tag_configure("even", background=THEME["row_even"],
                                      foreground=THEME["text"])
        self._deck_tree.tag_configure("odd", background=THEME["row_odd"],
                                     foreground=THEME["text"])

        # Summary
        total = len(self._deck_cards)
        attacks = sum(1 for c in self._deck_cards if c.card_type == CardType.ATTACK)
        skills = sum(1 for c in self._deck_cards if c.card_type == CardType.SKILL)
        powers = sum(1 for c in self._deck_cards if c.card_type == CardType.POWER)
        curses = sum(1 for c in self._deck_cards if c.card_type == CardType.CURSE)
        costs = [c.cost for c in self._deck_cards if c.cost >= 0]
        avg_cost = sum(costs) / len(costs) if costs else 0.0

        summary = (f"Deck: {total} cards  |  "
                   f"Attacks: {attacks}  Skills: {skills}  Powers: {powers}")
        if curses:
            summary += f"  Curses: {curses}"
        summary += f"  |  Avg cost: {avg_cost:.1f}"
        self._summary_var.set(summary)

    def _refresh_relic_sel_tree(self) -> None:
        self._relic_sel_tree.delete(*self._relic_sel_tree.get_children())
        self._relic_iid_to_relic: dict[str, Relic] = {}

        tag_even = False
        for idx, relic in enumerate(sorted(self._selected_relics, key=lambda r: r.name)):
            iid = str(idx)
            tag = "even" if tag_even else "odd"
            self._relic_sel_tree.insert("", tk.END, iid=iid,
                                        values=(relic.name, relic.rarity.name),
                                        tags=(tag,))
            self._relic_iid_to_relic[iid] = relic
            tag_even = not tag_even

        self._relic_sel_tree.tag_configure("even", background=THEME["row_even"],
                                           foreground=THEME["text"])
        self._relic_sel_tree.tag_configure("odd", background=THEME["row_odd"],
                                          foreground=THEME["text"])

        self._relic_summary_var.set(f"Relics: {len(self._selected_relics)}")

    def _catalog_filter(self, card: Card, search: str, filters: dict[str, str]) -> bool:
        if search and search not in card.name.lower():
            return False
        source = filters.get("source", "All")
        if source == "Character":
            if card.character not in (self._selected_character(),):
                return False
        elif source == "Colorless":
            if card.character != Character.COLORLESS:
                return False
        elif source == "Curse":
            if card.card_type != CardType.CURSE:
                return False
        if filters.get("type", "All") != "All" and card.card_type.name != filters["type"]:
            return False
        if filters.get("rarity", "All") != "All" and card.rarity.name != filters["rarity"]:
            return False
        return True

    @staticmethod
    def _relic_catalog_filter(relic: Relic, search: str, filters: dict[str, str]) -> bool:
        if search and search not in relic.name.lower():
            return False
        if filters.get("rarity", "All") != "All" and relic.rarity.name != filters["rarity"]:
            return False
        if filters.get("character", "All") != "All" and relic.character.value != filters["character"]:
            return False
        return True

    @staticmethod
    def _relic_detail(relic: Relic) -> str:
        lines = [
            relic.name,
            f"Rarity: {relic.rarity.name}  |  Character: {relic.character.value}",
            "",
            relic.description,
        ]
        if relic.effects:
            lines.append("")
            lines.append("Effects: " + ", ".join(
                f"{k}={v}" for k, v in relic.effects.items()))
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Probability Analysis Tab
# ---------------------------------------------------------------------------

class ProbabilityTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, deck_builder: DeckBuilderTab) -> None:
        super().__init__(parent)
        self._deck_builder = deck_builder

        # --- Parameters ---
        params = ttk.LabelFrame(self, text="Parameters")
        params.pack(fill=tk.X, padx=8, pady=6)

        row1 = ttk.Frame(params)
        row1.pack(fill=tk.X, padx=6, pady=(4, 2))

        ttk.Label(row1, text="Hand size:").pack(side=tk.LEFT)
        self._hand_size = tk.IntVar(value=5)
        ttk.Spinbox(row1, from_=1, to=10, textvariable=self._hand_size,
                     width=4).pack(side=tk.LEFT, padx=(2, 12))

        ttk.Label(row1, text="Energy:").pack(side=tk.LEFT)
        self._energy = tk.IntVar(value=3)
        ttk.Spinbox(row1, from_=0, to=10, textvariable=self._energy,
                     width=4).pack(side=tk.LEFT, padx=(2, 12))

        ttk.Label(row1, text="Strength:").pack(side=tk.LEFT)
        self._strength = tk.IntVar(value=0)
        ttk.Spinbox(row1, from_=-10, to=99, textvariable=self._strength,
                     width=4).pack(side=tk.LEFT, padx=(2, 12))

        ttk.Label(row1, text="Dexterity:").pack(side=tk.LEFT)
        self._dexterity = tk.IntVar(value=0)
        ttk.Spinbox(row1, from_=-10, to=99, textvariable=self._dexterity,
                     width=4).pack(side=tk.LEFT, padx=(2, 12))

        row2 = ttk.Frame(params)
        row2.pack(fill=tk.X, padx=6, pady=(2, 4))

        self._vulnerable = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text="Vulnerable", variable=self._vulnerable).pack(
            side=tk.LEFT, padx=(0, 12))

        self._weak = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text="Weak", variable=self._weak).pack(
            side=tk.LEFT, padx=(0, 12))

        self._turn1 = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="Turn 1 mode", variable=self._turn1).pack(
            side=tk.LEFT, padx=(0, 12))

        ttk.Button(row2, text="Recalculate", command=self._recalculate).pack(
            side=tk.RIGHT, padx=4)

        # --- Draw probability table ---
        prob_frame = ttk.LabelFrame(self, text="Draw Probabilities")
        prob_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        prob_cols = [("name", "Card", 160), ("copies", "Copies", 60),
                     ("prob", "P(draw >= 1)", 110)]
        self._prob_tree = ttk.Treeview(
            prob_frame, columns=[c[0] for c in prob_cols],
            show="headings", selectmode="browse")
        for col_id, heading, width in prob_cols:
            self._prob_tree.heading(col_id, text=heading)
            self._prob_tree.column(col_id, width=width, minwidth=40)
        prob_vsb = ttk.Scrollbar(prob_frame, orient=tk.VERTICAL,
                                 command=self._prob_tree.yview)
        self._prob_tree.configure(yscrollcommand=prob_vsb.set)
        self._prob_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        prob_vsb.pack(side=tk.RIGHT, fill=tk.Y, pady=4)

        # --- Expected output ---
        out_frame = ttk.LabelFrame(self, text="Expected Output Per Turn")
        out_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        self._damage_var = tk.StringVar(value="Load a deck to see expected output.")
        ttk.Label(out_frame, textvariable=self._damage_var,
                  font=("TkDefaultFont", 13)).pack(anchor=tk.W, padx=8, pady=(8, 0))

        self._block_var = tk.StringVar(value="")
        ttk.Label(out_frame, textvariable=self._block_var,
                  font=("TkDefaultFont", 13)).pack(anchor=tk.W, padx=8, pady=(0, 4))

        self._relic_info_var = tk.StringVar(value="")
        ttk.Label(out_frame, textvariable=self._relic_info_var,
                  font=("TkDefaultFont", 11),
                  foreground=THEME["text_dim"]).pack(anchor=tk.W, padx=8, pady=(0, 8))

    def on_tab_selected(self) -> None:
        self._recalculate()

    def _recalculate(self) -> None:
        deck_cards = self._deck_builder.get_deck_cards()
        if not deck_cards:
            self._prob_tree.delete(*self._prob_tree.get_children())
            self._damage_var.set("No deck loaded. Use the Deck Builder tab first.")
            self._block_var.set("")
            self._relic_info_var.set("")
            return

        deck = Deck(list(deck_cards))
        hand_size = self._hand_size.get()
        energy = self._energy.get()
        strength = self._strength.get()
        dexterity = self._dexterity.get()
        vulnerable = self._vulnerable.get()
        weak = self._weak.get()
        turn1 = self._turn1.get()

        # Aggregate relic modifiers
        relics = self._deck_builder.get_selected_relics()
        mods = get_relic_combat_modifiers(relics)

        # Apply relic modifiers
        eff_energy = energy + mods.energy + (mods.energy_turn1 if turn1 else 0)
        eff_strength = strength + mods.strength + (mods.strength_turn1 if turn1 else 0)
        eff_dexterity = dexterity + mods.dexterity
        eff_hand_size = hand_size + mods.draw + (mods.draw_turn1 if turn1 else 0)
        eff_vulnerable = (vulnerable or mods.vulnerable
                          or (mods.vulnerable_turn1 if turn1 else False))
        eff_weak = (weak or mods.weak
                    or (mods.weak_turn1 if turn1 else False))

        vuln_mult = mods.vuln_multiplier if mods.vuln_multiplier is not None else 1.5
        weak_mult = mods.weak_multiplier if mods.weak_multiplier is not None else 0.75

        # Draw probability table
        self._prob_tree.delete(*self._prob_tree.get_children())
        counts = deck.card_counts()
        tag_even = False
        for card in sorted(counts.keys(), key=lambda c: c.name):
            copies = counts[card]
            p = draw_probability(deck, card, draw_count=eff_hand_size)
            tag = "even" if tag_even else "odd"
            self._prob_tree.insert("", tk.END,
                                   values=(card.name, copies, f"{p:.1%}"),
                                   tags=(tag,))
            tag_even = not tag_even

        self._prob_tree.tag_configure("even", background=THEME["row_even"],
                                      foreground=THEME["text"])
        self._prob_tree.tag_configure("odd", background=THEME["row_odd"],
                                     foreground=THEME["text"])

        # Expected damage & block
        ed = expected_damage_output(
            deck, hand_size=eff_hand_size, energy=eff_energy,
            strength=eff_strength, vulnerable=eff_vulnerable, weak=eff_weak,
            vuln_multiplier=vuln_mult, weak_multiplier=weak_mult,
        )
        # Akabeko-style flat damage: applies to first attack on turn 1,
        # so add it if there's at least one attack in the deck
        flat_dmg = 0
        if turn1 and mods.damage_turn1:
            has_attack = any(c.card_type == CardType.ATTACK for c in deck_cards)
            if has_attack:
                flat_dmg = mods.damage_turn1
        ed += flat_dmg

        eb = expected_block_output(
            deck, hand_size=eff_hand_size, energy=eff_energy,
            dexterity=eff_dexterity,
        )

        params = f"hand={eff_hand_size}, energy={eff_energy}"
        self._damage_var.set(
            f"E[damage] = {ed:.1f}   "
            f"({params}, str={eff_strength}"
            f"{', vulnerable' if eff_vulnerable else ''}"
            f"{f', +{flat_dmg} flat' if flat_dmg else ''})"
        )
        self._block_var.set(
            f"E[block]    = {eb:.1f}   "
            f"({params}, dex={eff_dexterity})"
        )

        # Relic modifier info
        relic_parts: list[str] = []
        if mods.energy:
            relic_parts.append(f"energy +{mods.energy}")
        if mods.energy_turn1 and turn1:
            relic_parts.append(f"energy T1 +{mods.energy_turn1}")
        if mods.strength:
            relic_parts.append(f"str +{mods.strength}")
        if mods.strength_turn1 and turn1:
            relic_parts.append(f"str T1 +{mods.strength_turn1}")
        if mods.dexterity:
            relic_parts.append(f"dex +{mods.dexterity}")
        if mods.draw:
            relic_parts.append(f"draw +{mods.draw}")
        if mods.draw_turn1 and turn1:
            relic_parts.append(f"draw T1 +{mods.draw_turn1}")
        if mods.vulnerable:
            relic_parts.append("vulnerable")
        if mods.vulnerable_turn1 and turn1:
            relic_parts.append("vulnerable T1")
        if mods.weak:
            relic_parts.append("weak")
        if mods.weak_turn1 and turn1:
            relic_parts.append("weak T1")
        if mods.damage_turn1 and turn1:
            relic_parts.append(f"dmg T1 +{mods.damage_turn1}")
        if mods.block_start and turn1:
            relic_parts.append(f"start block +{mods.block_start}")
        if mods.vuln_multiplier is not None:
            relic_parts.append(f"vuln x{mods.vuln_multiplier}")
        if mods.weak_multiplier is not None:
            relic_parts.append(f"weak x{mods.weak_multiplier}")

        if relic_parts:
            self._relic_info_var.set(
                f"Relic modifiers: {', '.join(relic_parts)}"
                f"   {'[Turn 1]' if turn1 else '[Ongoing]'}"
            )
        else:
            self._relic_info_var.set("")


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

class App:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Slay the Spire Statistical Modeller")
        self.root.geometry("1100x750")
        self.root.minsize(900, 600)

        # Theme — dark Slay the Spire palette
        T = THEME
        self.root.configure(bg=T["bg"])
        self.root.option_add("*TCombobox*Listbox.background", T["bg_light"])
        self.root.option_add("*TCombobox*Listbox.foreground", T["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", T["select_bg"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", T["select_fg"])

        style = ttk.Style()
        style.theme_use("clam")

        # Base defaults
        style.configure(".",
                        background=T["bg"], foreground=T["text"],
                        fieldbackground=T["bg_light"], bordercolor=T["border"],
                        darkcolor=T["bg"], lightcolor=T["bg_mid"],
                        troughcolor=T["bg_mid"],
                        selectbackground=T["select_bg"],
                        selectforeground=T["select_fg"],
                        font=("TkDefaultFont", 11))

        # Frames & labels
        style.configure("TFrame", background=T["bg"])
        style.configure("TLabel", background=T["bg"], foreground=T["text"])
        style.configure("TLabelframe", background=T["bg"],
                        foreground=T["gold"])
        style.configure("TLabelframe.Label", background=T["bg"],
                        foreground=T["gold"])

        # Notebook tabs
        style.configure("TNotebook", background=T["bg"],
                        bordercolor=T["border"], tabmargins=[4, 4, 2, 0])
        style.configure("TNotebook.Tab", background=T["bg_mid"],
                        foreground=T["text_dim"], padding=[14, 5])
        style.map("TNotebook.Tab",
                  background=[("selected", T["accent"])],
                  foreground=[("selected", T["select_fg"])])

        # Buttons
        style.configure("TButton", background=T["bg_light"],
                        foreground=T["text"], padding=[10, 4],
                        bordercolor=T["border"])
        style.map("TButton",
                  background=[("active", T["accent"]),
                              ("pressed", T["accent"])],
                  foreground=[("active", T["select_fg"])])

        # Entry
        style.configure("TEntry", fieldbackground=T["bg_light"],
                        foreground=T["text"], insertcolor=T["text"],
                        bordercolor=T["border"])

        # Combobox
        style.configure("TCombobox", fieldbackground=T["bg_light"],
                        foreground=T["text"], arrowcolor=T["text_dim"],
                        bordercolor=T["border"])
        style.map("TCombobox",
                  fieldbackground=[("readonly", T["bg_light"])],
                  foreground=[("readonly", T["text"])],
                  bordercolor=[("focus", T["accent"])])

        # Treeview
        style.configure("Treeview", background=T["row_odd"],
                        foreground=T["text"], fieldbackground=T["row_odd"],
                        rowheight=26, bordercolor=T["border"])
        style.configure("Treeview.Heading", background=T["bg_light"],
                        foreground=T["gold"],
                        font=("TkDefaultFont", 11, "bold"),
                        bordercolor=T["border"])
        style.map("Treeview.Heading",
                  background=[("active", T["accent"])])
        style.map("Treeview",
                  background=[("selected", T["select_bg"])],
                  foreground=[("selected", T["select_fg"])])

        # Scrollbar
        style.configure("Vertical.TScrollbar",
                        background=T["bg_mid"], troughcolor=T["bg"],
                        bordercolor=T["border"], arrowcolor=T["text_dim"])
        style.map("Vertical.TScrollbar",
                  background=[("active", T["bg_light"])])

        # Spinbox
        style.configure("TSpinbox", fieldbackground=T["bg_light"],
                        foreground=T["text"], arrowcolor=T["text_dim"],
                        insertcolor=T["text"], bordercolor=T["border"])

        # Checkbutton
        style.configure("TCheckbutton", background=T["bg"],
                        foreground=T["text"])
        style.map("TCheckbutton",
                  background=[("active", T["bg"])])

        # PanedWindow
        style.configure("TPanedwindow", background=T["bg"])

        # Load data
        self._data = AppData()

        # Notebook
        self._notebook = ttk.Notebook(self.root)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Tabs
        browser_tab = DataBrowserTab(self._notebook, self._data)
        self._notebook.add(browser_tab, text="Data Browser")

        self._deck_builder = DeckBuilderTab(self._notebook, self._data)
        self._notebook.add(self._deck_builder, text="Deck Builder")

        self._prob_tab = ProbabilityTab(self._notebook, self._deck_builder)
        self._notebook.add(self._prob_tab, text="Probability Analysis")

        # Auto-recalculate when switching to probability tab
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, _event: tk.Event) -> None:
        current = self._notebook.index(self._notebook.select())
        # Probability tab is index 2
        if current == 2:
            self._prob_tab.on_tab_selected()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
