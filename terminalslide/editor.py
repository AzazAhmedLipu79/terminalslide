from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Label, TextArea, Static
from textual.containers import Vertical
from textual.message import Message


class EditorScreen(Screen):
    """Inline markdown editor for a single slide's raw content."""

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", show=True),
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    DEFAULT_CSS = """
    EditorScreen {
        layout: vertical;
        background: $surface;
    }
    #editor-header {
        height: 1;
        background: $primary-darken-3;
        padding: 0 2;
        color: $text;
    }
    #editor-hint {
        height: 1;
        background: $primary-darken-2;
        padding: 0 2;
        color: $text-muted;
    }
    TextArea {
        height: 1fr;
    }
    """

    class Saved(Message):
        """Posted when the user saves. Contains updated raw slide text."""
        def __init__(self, raw: str) -> None:
            super().__init__()
            self.raw = raw

    class Cancelled(Message):
        """Posted when the user cancels."""

    def __init__(self, slide_index: int, raw: str) -> None:
        super().__init__()
        self._slide_index = slide_index
        self._original_raw = raw

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold]Edit slide {self._slide_index + 1}[/bold]",
            id="editor-header",
        )
        yield Static(
            "Ctrl+S to save  •  Esc to cancel",
            id="editor-hint",
        )
        yield TextArea(self._original_raw, language="markdown", id="editor-area")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(TextArea).focus()

    def action_save(self) -> None:
        raw = self.query_one(TextArea).text
        self.dismiss(raw)

    def action_cancel(self) -> None:
        self.dismiss(None)
