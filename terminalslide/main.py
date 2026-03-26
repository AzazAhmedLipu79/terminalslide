from __future__ import annotations

import os
import sys
import tempfile
import threading
from pathlib import Path
from typing import Optional

import click
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Footer, Header, Label, ProgressBar, Static
from textual import work, on
from rich.console import Console
from rich.text import Text

from .parser import Deck, Slide, parse_file, parse_text, reassemble
from .themes import Theme, get_theme, next_theme
from .renderer import build_slide_renderable
from .timer import TalkTimer
from .watcher import FileWatcher
from .overview import OverviewScreen
from .editor import EditorScreen
from .keybinds import KeybindOverlay


STARTER_CONTENT = """\
---
title: My Presentation
author: Your Name
theme: dark
date: 2026-03-27
---

# Welcome to TermSlide

Write markdown. Run one command. Present anywhere.

---

# What This Deck Can Do

- Slides separated by `---`
- Live reload when you save this file
- Syntax-highlighted code blocks
- Export to PDF with `p`

---

# Code Example

This is how a code slide looks:

```python
def greet(name: str) -> str:
    return f"Hello, {name}!"

print(greet("world"))
```

---

# Presenter Notes

This slide has a presenter note below.
Notes are hidden during presentation.

> note: Remember to pause here and ask the audience a question.

---

# That's It

- Press `?` for all keybinds
- Press `T` to cycle themes
- Press `p` to export this deck to PDF
"""


class SlideView(Static):
    """Renders the current slide using Rich."""

    DEFAULT_CSS = """
    SlideView {
        height: 1fr;
        padding: 1 2;
        overflow-y: auto;
    }
    """

    def update_slide(self, slide: Slide, theme: Theme) -> None:
        panel = build_slide_renderable(slide, theme)
        self.update(panel)


class BlankScreen(Static):
    """Full-screen blank overlay."""

    DEFAULT_CSS = """
    BlankScreen {
        background: $background;
        height: 100%;
        width: 100%;
        content-align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("[dim]Press any key to continue[/dim]")

    def on_key(self, event) -> None:
        self.remove()


class TermSlideApp(App):
    """Main TermSlide application."""

    CSS = """
    TermSlideApp {
        background: $background;
    }
    #header-bar {
        height: 1;
        background: $primary-darken-3;
        layout: horizontal;
        padding: 0 2;
    }
    #header-title {
        width: 1fr;
        color: $text;
    }
    #header-timer {
        width: auto;
        color: white;
        text-align: right;
    }
    #slide-view {
        height: 1fr;
    }
    #footer-bar {
        height: 1;
        background: $primary-darken-3;
        layout: horizontal;
        padding: 0 2;
    }
    #footer-hints {
        width: 1fr;
        color: $text-muted;
    }
    #footer-slide-counter {
        width: auto;
        color: $text;
        text-align: right;
    }
    #progress {
        height: 1;
        background: $primary-darken-2;
    }
    #status-bar {
        height: 1;
        background: $warning-darken-2;
        color: $text;
        padding: 0 2;
        display: none;
    }
    """

    BINDINGS = [
        Binding("right,l,space", "next_slide", "Next", show=False),
        Binding("left,h", "prev_slide", "Prev", show=False),
        Binding("g,home", "first_slide", "First", show=False),
        Binding("G,end", "last_slide", "Last", show=False),
        Binding("tab", "overview", "Overview", show=True, priority=True),
        Binding("e", "edit_slide", "Edit", show=True),
        Binding("n", "new_slide", "New slide", show=True),
        Binding("d", "delete_slide", "Delete slide", show=False),
        Binding("t", "toggle_timer", "Timer", show=True),
        Binding("T", "cycle_theme", "Theme", show=True),
        Binding("b", "blank_screen", "Blank", show=False),
        Binding("p", "export_pdf", "Export PDF", show=True),
        Binding("question_mark", "show_help", "Help", show=True),
        Binding("q,escape,ctrl+c", "quit_app", "Quit", show=True),
    ]

    current_index: reactive[int] = reactive(0)
    timer_visible: reactive[bool] = reactive(False)

    class FileChanged(Message):
        """Posted from the watchdog thread when the source file changes."""

    def __init__(self, deck: Deck, source_path: str) -> None:
        super().__init__()
        self._deck = deck
        self._source_path = source_path
        self._theme: Theme = get_theme(deck.front_matter.theme or "dark")
        self._timer = TalkTimer()
        self._timer_interval = None
        self._watcher: Optional[FileWatcher] = None
        self._autosave_timer: Optional[threading.Timer] = None
        self._dirty = False  # tracks unsaved in-session edits

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Horizontal(id="header-bar"):
            filename = Path(self._source_path).name if self._source_path else ""
            yield Static(
                f"[bold]terminalslide[/bold] — {filename}",
                id="header-title",
            )
            yield Static("", id="header-timer")

        yield SlideView(id="slide-view")
        yield Static("", id="status-bar")

        with Horizontal(id="footer-bar"):
            yield Static(
                "← → (navigate)   e (edit)   Tab (overview)   ? (help)",
                id="footer-hints",
            )
            yield Static(id="footer-slide-counter")

        yield Static("", id="progress")

    def on_mount(self) -> None:
        self._apply_theme()
        self._render_current_slide()
        self._update_footer()
        self._start_watcher()
        self._schedule_autosave()
        self.set_interval(1.0, self._tick_timer)

    def on_unmount(self) -> None:
        if self._watcher:
            self._watcher.stop()
        if self._autosave_timer:
            self._autosave_timer.cancel()

    # ── Theme ──────────────────────────────────────────────────────────────

    def _apply_theme(self) -> None:
        t = self._theme
        self.app.dark = (t.name == "dark" or t.name == "minimal")

    # ── Rendering ──────────────────────────────────────────────────────────

    def _render_current_slide(self) -> None:
        slides = self._deck.slides
        if not slides:
            return
        idx = max(0, min(self.current_index, len(slides) - 1))
        slide = slides[idx]
        self.query_one(SlideView).update_slide(slide, self._theme)
        self._update_footer()
        self._update_progress()

    def _update_footer(self) -> None:
        total = len(self._deck.slides)
        idx = self.current_index + 1
        self.query_one("#footer-slide-counter", Static).update(
            f"Slide {idx} / {total}"
        )

    def _update_progress(self) -> None:
        total = len(self._deck.slides)
        if total <= 1:
            ratio = 1.0
        else:
            ratio = self.current_index / (total - 1)
        filled = int(ratio * (self.size.width or 80))
        bar = "█" * filled + "░" * ((self.size.width or 80) - filled)
        self.query_one("#progress", Static).update(
            f"[{self._theme.accent}]{bar}[/]"
        )

    def _tick_timer(self) -> None:
        if self._timer.is_running:
            color = self._timer.color()
            self.query_one("#header-timer", Static).update(
                f"[{color}]{self._timer.formatted()}[/]"
            )

    # ── Navigation ─────────────────────────────────────────────────────────

    def action_next_slide(self) -> None:
        if self.current_index < len(self._deck.slides) - 1:
            self.current_index += 1
            self._render_current_slide()

    def action_prev_slide(self) -> None:
        if self.current_index > 0:
            self.current_index -= 1
            self._render_current_slide()

    def action_first_slide(self) -> None:
        self.current_index = 0
        self._render_current_slide()

    def action_last_slide(self) -> None:
        self.current_index = len(self._deck.slides) - 1
        self._render_current_slide()

    # ── Overview notification ──────────────────────────────────────────────

    def _notify_overview(self) -> None:
        """If OverviewScreen is on the screen stack, refresh its cards."""
        from .overview import OverviewScreen
        for screen in self.screen_stack:
            if isinstance(screen, OverviewScreen):
                screen.refresh_deck(self._deck, self.current_index)
                break

    # ── Overview ───────────────────────────────────────────────────────────

    def action_overview(self) -> None:
        def on_dismiss(result: int | None) -> None:
            if result is not None:
                self.current_index = result
                self._render_current_slide()

        self.push_screen(
            OverviewScreen(self._deck, self.current_index, self._theme),
            callback=on_dismiss,
        )

    # ── Edit ───────────────────────────────────────────────────────────────

    def action_edit_slide(self) -> None:
        slide = self._deck.slides[self.current_index]

        def on_dismiss(result: str | None) -> None:
            if result is not None:
                from .parser import _parse_slide
                new_slide = _parse_slide(result)
                self._deck.slides[self.current_index] = new_slide
                self._dirty = True
                self._save_to_disk()
                self._render_current_slide()
                self._notify_overview()

        self.push_screen(
            EditorScreen(self.current_index, slide.raw),
            callback=on_dismiss,
        )

    # ── New / Delete slide ─────────────────────────────────────────────────

    def action_new_slide(self) -> None:
        from .parser import _parse_slide
        new_slide = _parse_slide("# New Slide\n\nContent here.\n")
        self._deck.slides.insert(self.current_index + 1, new_slide)
        self.current_index += 1
        self._dirty = True
        self._save_to_disk()
        self._render_current_slide()
        self._notify_overview()

    def action_delete_slide(self) -> None:
        total = len(self._deck.slides)
        if total <= 1:
            self._flash_status("Cannot delete the only slide.")
            return

        idx = self.current_index

        async def confirm() -> None:
            result = await self.app.push_screen_wait(
                _ConfirmScreen(f"Delete slide {idx + 1}? [y/N]")
            )
            if result:
                self._deck.slides.pop(idx)
                self.current_index = min(idx, len(self._deck.slides) - 1)
                self._dirty = True
                self._save_to_disk()
                self._render_current_slide()
                self._notify_overview()

        self.run_worker(confirm())

    # ── Timer ──────────────────────────────────────────────────────────────

    def action_toggle_timer(self) -> None:
        self._timer.toggle()
        if self._timer.is_running:
            self.query_one("#header-timer", Static).update(
                self._timer.formatted()
            )
        else:
            self.query_one("#header-timer", Static).update(
                f"[dim]{self._timer.formatted()}[/dim]"
            )

    # ── Theme ──────────────────────────────────────────────────────────────

    def action_cycle_theme(self) -> None:
        self._theme = next_theme(self._theme.name)
        self._apply_theme()
        self._render_current_slide()
        self._flash_status(f"Theme: {self._theme.name}")

    # ── Blank screen ───────────────────────────────────────────────────────

    def action_blank_screen(self) -> None:
        self.mount(BlankScreen())

    # ── PDF export ─────────────────────────────────────────────────────────

    def action_export_pdf(self) -> None:
        from .pdf_export import export_pdf, get_output_path
        output = get_output_path(self._source_path)
        self._flash_status("Generating PDF...")
        try:
            export_pdf(self._deck, self._theme, output)
            self._flash_status(f"PDF saved: {Path(output).name}")
        except Exception as e:
            self._flash_status(f"PDF export failed: {e}")

    # ── Help overlay ───────────────────────────────────────────────────────

    def action_show_help(self) -> None:
        self.push_screen(KeybindOverlay())

    # ── Quit ───────────────────────────────────────────────────────────────

    def action_quit_app(self) -> None:
        if self._dirty:
            self._save_to_disk()
        if self._watcher:
            self._watcher.stop()
        self.exit()

    # ── File watcher ───────────────────────────────────────────────────────

    def _start_watcher(self) -> None:
        def on_change():
            self.post_message(TermSlideApp.FileChanged())

        self._watcher = FileWatcher(self._source_path, on_change)
        self._watcher.start()

    @on(FileChanged)
    def handle_file_changed(self) -> None:
        try:
            new_deck = parse_file(self._source_path)
            self._deck = new_deck
            # Clamp index
            self.current_index = min(
                self.current_index, max(0, len(self._deck.slides) - 1)
            )
            self._render_current_slide()
            self._notify_overview()
            self._flash_status(f"Reloaded — {len(self._deck.slides)} slides")
        except Exception as e:
            self._flash_status(f"Reload error: {e}")

    # ── Autosave ───────────────────────────────────────────────────────────

    def _schedule_autosave(self) -> None:
        def autosave():
            if self._dirty:
                self._save_to_disk()
            self._autosave_timer = threading.Timer(30, autosave)
            self._autosave_timer.daemon = True
            self._autosave_timer.start()

        self._autosave_timer = threading.Timer(30, autosave)
        self._autosave_timer.daemon = True
        self._autosave_timer.start()

    def _save_to_disk(self) -> None:
        """Atomically write the current deck back to the source file."""
        if not self._source_path:
            return
        try:
            content = reassemble(self._deck)
            dir_ = os.path.dirname(self._source_path) or "."
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=dir_, delete=False, suffix=".tmp"
            ) as f:
                f.write(content)
                tmp_path = f.name
            os.replace(tmp_path, self._source_path)
            self._dirty = False
        except Exception as e:
            self._flash_status(f"Save failed: {e}")

    # ── Status flash ───────────────────────────────────────────────────────

    def _flash_status(self, message: str, duration: float = 2.0) -> None:
        bar = self.query_one("#status-bar", Static)
        bar.update(message)
        bar.styles.display = "block"
        self.set_timer(duration, lambda: bar.styles.__setattr__("display", "none"))


class _ConfirmScreen(Screen):
    """Simple yes/no confirm prompt."""

    BINDINGS = [
        Binding("y", "yes", "Yes"),
        Binding("n,escape", "no", "No"),
    ]

    DEFAULT_CSS = """
    _ConfirmScreen {
        align: center middle;
        background: rgba(0,0,0,0.7);
    }
    #confirm-box {
        width: 50;
        height: 5;
        background: $surface;
        border: solid $warning;
        padding: 1 2;
        content-align: center middle;
    }
    """

    def __init__(self, prompt: str) -> None:
        super().__init__()
        self._prompt = prompt

    def compose(self) -> ComposeResult:
        yield Static(self._prompt, id="confirm-box")

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


# ── CLI ────────────────────────────────────────────────────────────────────


@click.group(invoke_without_command=True, context_settings={"help_option_names": ["--help"]})
@click.version_option(version="0.1.0", prog_name="terminalslide")
@click.option("--list", "list_all", is_flag=True, default=False, help="List all .md files in the current directory tree.")
@click.pass_context
def cli(ctx: click.Context, list_all: bool) -> None:
    """TermSlide — Write markdown. Run one command. Present anywhere.

    \b
    COMMANDS
      terminalslide <file.md>        Open a markdown file as a presentation
      terminalslide init             Generate a starter.md template here

    \b
    FILE OPTIONS  (pass alongside a file)
      terminalslide -r/--read <file.md>  List all slide titles in a file and exit

    \b
    GLOBAL OPTIONS
      terminalslide --list           List all .md files found under current directory
      terminalslide --version        Show version and exit
      terminalslide --help           Show this message and exit

    \b
    INSIDE THE PRESENTATION
      →  l  Space    Next slide
      ←  h           Previous slide
      g  Home        First slide
      G  End         Last slide
      Tab            Slide overview grid (jump anywhere)
      e              Edit current slide inline
      n              New slide after current
      d              Delete current slide
      t              Toggle talk timer (counts up, turns red at limit)
      T              Cycle theme  dark → light → minimal
      b              Blank screen (press any key to return)
      p              Export deck to PDF
      ?              Show keybind help overlay
      q  Esc  Ctrl+C Quit (autosaves first)

    \b
    MARKDOWN FORMAT
      Slides are separated by --- on its own line.
      First # heading becomes the slide title.
      Fenced code blocks (```python) are syntax-highlighted.
      Lines starting with "> note:" are presenter notes (hidden on screen).
      Optional YAML front matter: title, author, theme, date.

    \b
    EXAMPLES
      terminalslide talk.md
      terminalslide talk.md -r / terminalslide --read talk.md
      terminalslide --list
      terminalslide init && terminalslide starter.md
    """
    if list_all:
        _cmd_list_all()
        return
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _cmd_list_all() -> None:
    """Scan current directory tree for .md files and print a summary."""
    cwd = Path(".")
    md_files = sorted(cwd.rglob("*.md"))
    # Exclude hidden dirs and .venv
    md_files = [
        f for f in md_files
        if not any(part.startswith(".") or part in ("venv", ".venv", "node_modules")
                   for part in f.parts)
    ]
    if not md_files:
        click.echo("No .md files found in current directory.")
        return
    click.echo(f"Found {len(md_files)} markdown file{'s' if len(md_files) != 1 else ''} under {cwd.resolve().name}/\n")
    for f in md_files:
        try:
            deck = parse_file(str(f))
            n = len(deck.slides)
            fm = deck.front_matter
            meta = fm.title or ""
            if fm.author:
                meta += f" — {fm.author}" if meta else fm.author
            slide_label = f"{n} slide{'s' if n != 1 else ''}"
            meta_part = f"  [{meta}]" if meta else ""
            click.echo(f"  {str(f):<40} {slide_label:<12}{meta_part}")
        except Exception:
            click.echo(f"  {str(f):<40} (could not parse)")
    click.echo()


@cli.command(name="present", hidden=True)
@click.argument("file", type=click.Path())
@click.option("-r", "--read", "list_slides", is_flag=True, default=False, help="List all slide titles in this file and exit.")
def _present_hidden(file: str, list_slides: bool) -> None:
    """Hidden alias used internally."""
    _run_presentation(file, list_slides=list_slides)


def _run_presentation(file: str, list_slides: bool = False) -> None:
    path = Path(file)

    if not path.exists():
        create = click.confirm(
            f"'{path.name}' doesn't exist. Create it?", default=True
        )
        if not create:
            sys.exit(0)

        import datetime
        today = datetime.date.today().isoformat()
        default_title = path.stem.replace("-", " ").replace("_", " ").title()

        click.echo("\nFill in your deck details (press Enter to keep the default):\n")
        title  = click.prompt("  Title",  default=default_title)
        author = click.prompt("  Author", default="Your Name")
        theme  = click.prompt("  Theme  [dark/light/minimal]", default="dark")
        date   = click.prompt("  Date",   default=today)

        if theme not in ("dark", "light", "minimal"):
            click.echo(f"  Unknown theme '{theme}', falling back to 'dark'.")
            theme = "dark"

        content = (
            f"---\n"
            f"title: {title}\n"
            f"author: {author}\n"
            f"theme: {theme}\n"
            f"date: {date}\n"
            f"---\n\n"
            f"# {title}\n\n"
            f"Start writing your slides here.\n\n"
            f"---\n\n"
            f"# Slide 2\n\n"
            f"Add your content.\n"
        )
        path.write_text(content, encoding="utf-8")
        click.echo(f"\nCreated '{path.name}'.")

    if path.stat().st_size == 0:
        click.echo(f"Error: '{file}' is empty.", err=True)
        sys.exit(1)

    if path.suffix.lower() != ".md":
        click.echo(f"Warning: file does not have a .md extension.", err=True)

    deck = parse_file(str(path))
    n = len(deck.slides)

    if list_slides:
        fm = deck.front_matter
        if fm.title:
            click.echo(f"  {path.name} — {fm.title}" + (f" by {fm.author}" if fm.author else ""))
            click.echo()
        for i, slide in enumerate(deck.slides, start=1):
            title = slide.title or "(untitled)"
            preview = slide.body.splitlines()[0][:60] if slide.body.strip() else ""
            click.echo(f"  {i:>3}.  {title}" + (f"  [dim]— {preview}[/dim]" if preview else ""))
        click.echo(f"\n  {n} slide{'s' if n != 1 else ''} total.")
        return

    click.echo(f"Loaded {n} slide{'s' if n != 1 else ''} from {path.name}")

    app = TermSlideApp(deck=deck, source_path=str(path.resolve()))
    app.run()


@cli.command()
def init() -> None:
    """Generate a starter.md template in the current directory."""
    target = Path("starter.md")
    if target.exists():
        overwrite = click.confirm("starter.md already exists. Overwrite?", default=False)
        if not overwrite:
            return
    target.write_text(STARTER_CONTENT, encoding="utf-8")
    click.echo("Created starter.md — run: terminalslide starter.md")


def main() -> None:
    """
    Smart entry point: if the first non-flag argument looks like a file
    (not a known subcommand), inject 'present' so `terminalslide file.md`
    routes correctly without requiring a subcommand verb.
    """
    _SUBCOMMANDS = {"init", "present", "--help", "--version", "-h", "--list"}
    args = sys.argv[1:]
    # Inject 'present' when any arg is a file path (not a subcommand, not a flag).
    # This lets all orderings work: file.md -r, --read file.md, file.md, etc.
    has_file_arg = any(
        a not in _SUBCOMMANDS and not a.startswith("-")
        for a in args
    )
    if args and has_file_arg and args[0] not in _SUBCOMMANDS:
        sys.argv.insert(1, "present")
    cli()


if __name__ == "__main__":
    main()
