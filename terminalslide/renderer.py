from __future__ import annotations

import re

from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text
from rich import box

from .parser import Slide
from .themes import Theme


# Regex to detect fenced code blocks: ```lang\n...\n```
_FENCE_RE = re.compile(
    r"```(\w*)\n(.*?)```",
    re.DOTALL,
)

# Regex for inline bold (**text**) and italic (*text*)
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"\*(.+?)\*")


def _render_body(body: str, theme: Theme) -> list:
    """
    Parse the body markdown into a list of Rich renderables.
    Handles: fenced code blocks, bullet lists, numbered lists,
    paragraphs with bold/italic.
    """
    renderables = []
    # Split into segments: code blocks and text blocks
    last = 0
    for m in _FENCE_RE.finditer(body):
        # Text before this code block
        text_chunk = body[last:m.start()].strip()
        if text_chunk:
            renderables.extend(_render_text_block(text_chunk, theme))

        lang = m.group(1) or "text"
        code = m.group(2)
        syntax = Syntax(
            code,
            lang,
            theme=theme.pygments_style,
            background_color=theme.code_background,
            word_wrap=True,
            padding=(1, 2),
        )
        renderables.append(syntax)
        last = m.end()

    remainder = body[last:].strip()
    if remainder:
        renderables.extend(_render_text_block(remainder, theme))

    return renderables


def _render_text_block(text: str, theme: Theme) -> list:
    """Render a plain text block (bullets, numbered lists, paragraphs)."""
    renderables = []
    lines = text.splitlines()
    buffer: list[str] = []

    def flush_buffer():
        if buffer:
            rich_text = _inline_markup("\n".join(buffer), theme)
            renderables.append(Padding(rich_text, pad=(0, 0, 0, 0)))
            buffer.clear()

    for line in lines:
        stripped = line.strip()
        # Bullet
        if re.match(r"^[-*+]\s+", stripped):
            flush_buffer()
            content = re.sub(r"^[-*+]\s+", "", stripped)
            rt = Text()
            rt.append("  • ", style=Style(color=theme.accent))
            rt.append_text(_inline_markup(content, theme))
            renderables.append(rt)
        # Numbered list
        elif re.match(r"^\d+\.\s+", stripped):
            flush_buffer()
            num = re.match(r"^(\d+)\.\s+", stripped).group(1)
            content = re.sub(r"^\d+\.\s+", "", stripped)
            rt = Text()
            rt.append(f"  {num}. ", style=Style(color=theme.accent))
            rt.append_text(_inline_markup(content, theme))
            renderables.append(rt)
        elif stripped == "":
            flush_buffer()
        else:
            buffer.append(line)

    flush_buffer()
    return renderables


def _inline_markup(text: str, theme: Theme) -> Text:
    """Convert inline **bold** and *italic* to Rich Text."""
    result = Text()
    # We'll do a simple state-machine parse
    i = 0
    while i < len(text):
        if text[i:i+2] == "**":
            end = text.find("**", i + 2)
            if end != -1:
                result.append(text[i+2:end], style=Style(bold=True, color=theme.foreground))
                i = end + 2
            else:
                result.append(text[i], style=Style(color=theme.foreground))
                i += 1
        elif text[i] == "*":
            end = text.find("*", i + 1)
            if end != -1:
                result.append(text[i+1:end], style=Style(italic=True, color=theme.foreground))
                i = end + 1
            else:
                result.append(text[i], style=Style(color=theme.foreground))
                i += 1
        else:
            # Accumulate plain text
            j = i
            while j < len(text) and text[j] not in ("*",):
                j += 1
            result.append(text[i:j], style=Style(color=theme.foreground))
            i = j

    return result


def build_slide_renderable(slide: Slide, theme: Theme) -> Panel:
    """Build the full Rich Panel for a slide."""
    from rich.console import Group

    title_text = Text(slide.title or "", style=Style(
        bold=True,
        color=theme.title_color,
    ))
    title_text.stylize(Style(bold=True))

    body_renderables = _render_body(slide.body, theme)

    content_parts = [Padding(title_text, pad=(1, 0, 1, 2))]
    for r in body_renderables:
        content_parts.append(Padding(r, pad=(0, 0, 0, 4)))

    group = Group(*content_parts)

    panel = Panel(
        group,
        border_style=Style(color=theme.accent),
        box=box.ROUNDED,
        expand=True,
    )
    return panel


def render_slide_to_console(
    console: Console,
    slide: Slide,
    theme: Theme,
    slide_num: int,
    total: int,
) -> None:
    """Render a slide directly to the given console (used for PDF-like capture)."""
    panel = build_slide_renderable(slide, theme)
    console.print(panel)
