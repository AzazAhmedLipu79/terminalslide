from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static, Footer


KEYBINDS = [
    ("→ / l / Space", "Next slide"),
    ("← / h", "Previous slide"),
    ("g / Home", "First slide"),
    ("G / End", "Last slide"),
    ("Tab", "Slide overview grid"),
    ("e", "Edit current slide"),
    ("n", "New slide after current"),
    ("d", "Delete current slide"),
    ("t", "Toggle talk timer"),
    ("T", "Cycle theme"),
    ("b", "Blank screen"),
    ("p", "Export to PDF"),
    ("?", "Show this help"),
    ("q / Esc / Ctrl+C", "Quit"),
]


class KeybindOverlay(Screen):
    """Full-screen keybind help overlay."""

    BINDINGS = [
        Binding("escape,q,?", "close", "Close", show=True),
    ]

    DEFAULT_CSS = """
    KeybindOverlay {
        layout: vertical;
        align: center middle;
        background: rgba(0,0,0,0.85);
    }
    #keybind-box {
        width: 60;
        background: $surface;
        border: double $accent;
        padding: 1 3;
    }
    """

    def compose(self) -> ComposeResult:
        lines = ["[bold]TermSlide — Keybindings[/bold]\n"]
        for key, action in KEYBINDS:
            lines.append(f"[bold cyan]{key:<20}[/bold cyan]  {action}")
        yield Static("\n".join(lines), id="keybind-box")
        yield Footer()

    def action_close(self) -> None:
        self.dismiss()
