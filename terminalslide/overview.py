from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Label, Static
from textual.containers import ScrollableContainer
from textual import on
from textual.message import Message

from .parser import Deck, Slide
from .themes import Theme

_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_MARKUP_RE = re.compile(r"\*{1,2}([^*]+)\*{1,2}")


def _card_preview(slide: Slide, max_lines: int = 3, max_chars: int = 48) -> list[str]:
    """Return up to *max_lines* cleaned preview lines from the slide body."""
    body = _FENCE_RE.sub("[code block]", slide.body or "")
    lines: list[str] = []
    for raw in body.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        # skip ATX headings (already shown as title)
        if stripped.startswith("#"):
            continue
        # bullets → unicode bullet
        stripped = re.sub(r"^[-*+]\s+", "• ", stripped)
        stripped = re.sub(r"^\d+\.\s+", "• ", stripped)
        # remove bold/italic markup
        stripped = _MARKUP_RE.sub(r"\1", stripped)
        if len(stripped) > max_chars:
            stripped = stripped[: max_chars - 1] + "…"
        lines.append(stripped)
        if len(lines) >= max_lines:
            break
    return lines


class SlideCard(Static):
    """A single miniature slide card shown in the overview grid."""

    DEFAULT_CSS = """
    SlideCard {
        border: solid $primary-darken-2;
        padding: 1 2;
        height: 8;
        margin: 1;
    }
    SlideCard.current {
        border: double $accent;
    }
    SlideCard:hover {
        border: solid $accent;
    }
    """

    def __init__(
        self,
        index: int,
        total: int,
        slide: Slide,
        is_current: bool,
        theme: Theme,
    ) -> None:
        super().__init__()
        self._index = index
        self._total = total
        self._slide = slide
        self._is_current = is_current
        self._theme = theme
        if is_current:
            self.add_class("current")

    def compose(self) -> ComposeResult:
        page = f"{self._index + 1:02d} / {self._total:02d}"
        yield Label(f"[dim]{page}[/dim]")
        title = self._slide.title or "(untitled)"
        yield Label(f"[bold]{title}[/bold]" if self._is_current else title)
        for line in _card_preview(self._slide):
            yield Label(f"[dim]{line}[/dim]")

    def on_click(self) -> None:
        self.post_message(OverviewScreen.SlideSelected(self._index))


class OverviewScreen(Screen):
    """Grid overview of all slides. Press Enter/Tab/Esc to exit."""

    BINDINGS = [
        Binding("tab,escape", "exit_overview", "Exit overview", show=True, priority=True),
        Binding("enter", "jump_to_slide", "Jump to slide", show=True),
        Binding("up,k", "move_up", "Up", show=False),
        Binding("down,j", "move_down", "Down", show=False),
        Binding("left,h", "move_left", "Left", show=False),
        Binding("right,l", "move_right", "Right", show=False),
    ]

    DEFAULT_CSS = """
    OverviewScreen {
        layout: vertical;
    }
    #overview-header {
        height: 1;
        background: $primary-darken-3;
        padding: 0 2;
        color: $text;
    }
    #grid-container {
        layout: grid;
        grid-size: 3;
        grid-gutter: 1;
        overflow-y: auto;
        padding: 1 2;
    }
    """

    class SlideSelected(Message):
        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    def __init__(
        self,
        deck: Deck,
        current_index: int,
        theme: Theme,
    ) -> None:
        super().__init__()
        self._deck = deck
        self._current_index = current_index
        self._theme = theme
        self._focused_index = current_index

    def compose(self) -> ComposeResult:
        filename = self._deck.source_path.split("/")[-1] if self._deck.source_path else ""
        yield Static(
            f"[bold]terminalslide — overview — {filename}[/bold]"
            f"   [dim]{len(self._deck.slides)} slides[/dim]",
            id="overview-header",
        )
        with ScrollableContainer(id="grid-container"):
            total = len(self._deck.slides)
            for i, slide in enumerate(self._deck.slides):
                yield SlideCard(
                    index=i,
                    total=total,
                    slide=slide,
                    is_current=(i == self._current_index),
                    theme=self._theme,
                )
        yield Footer()

    def on_mount(self) -> None:
        self._update_grid_columns()

    def on_resize(self) -> None:
        self._update_grid_columns()

    def _cols_for_width(self, width: int) -> int:
        if width >= 140:
            return 5
        if width >= 110:
            return 4
        if width >= 80:
            return 3
        if width >= 52:
            return 2
        return 1

    def _update_grid_columns(self) -> None:
        cols = self._cols_for_width(self.size.width)
        try:
            container = self.query_one("#grid-container")
            container.styles.grid_size_columns = cols
        except Exception:
            pass

    @on(SlideSelected)
    def handle_slide_selected(self, event: SlideSelected) -> None:
        self.dismiss(event.index)

    def action_exit_overview(self) -> None:
        self.dismiss(self._current_index)

    def action_jump_to_slide(self) -> None:
        self.dismiss(self._focused_index)

    def _get_cards(self) -> list[SlideCard]:
        return list(self.query(SlideCard))

    def _cols(self) -> int:
        return self._cols_for_width(self.size.width)

    def action_move_up(self) -> None:
        cols = self._cols()
        new = max(0, self._focused_index - cols)
        self._set_focus(new)

    def action_move_down(self) -> None:
        cols = self._cols()
        new = min(len(self._deck.slides) - 1, self._focused_index + cols)
        self._set_focus(new)

    def action_move_left(self) -> None:
        new = max(0, self._focused_index - 1)
        self._set_focus(new)

    def action_move_right(self) -> None:
        new = min(len(self._deck.slides) - 1, self._focused_index + 1)
        self._set_focus(new)

    def _set_focus(self, index: int) -> None:
        self._focused_index = index
        cards = self._get_cards()
        for i, card in enumerate(cards):
            card.remove_class("current")
            if i == index:
                card.add_class("current")
                card.scroll_visible()

    def refresh_deck(self, deck: Deck, current_index: int) -> None:
        """Rebuild cards to reflect a changed deck (live reload, add, delete)."""
        self._deck = deck
        self._current_index = current_index
        self._focused_index = min(current_index, max(0, len(deck.slides) - 1))

        # Update header slide count
        filename = deck.source_path.split("/")[-1] if deck.source_path else ""
        self.query_one("#overview-header", Static).update(
            f"[bold]terminalslide — overview — {filename}[/bold]"
            f"   [dim]{len(deck.slides)} slides[/dim]"
        )

        # Rebuild cards inside the grid container
        container = self.query_one("#grid-container")
        container.remove_children()
        total = len(deck.slides)
        for i, slide in enumerate(deck.slides):
            card = SlideCard(
                index=i,
                total=total,
                slide=slide,
                is_current=(i == self._focused_index),
                theme=self._theme,
            )
            container.mount(card)
        self._update_grid_columns()
