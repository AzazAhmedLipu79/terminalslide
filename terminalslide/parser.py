from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Slide:
    title: str
    body: str          # raw markdown body (no title line, no notes)
    notes: str         # presenter notes (lines starting with > note:)
    raw: str           # original raw text of this slide block


@dataclass
class FrontMatter:
    title: str = ""
    author: str = ""
    theme: str = "dark"
    date: str = ""


@dataclass
class Deck:
    slides: list[Slide] = field(default_factory=list)
    front_matter: FrontMatter = field(default_factory=FrontMatter)
    source_path: str = ""


_YAML_FENCE = re.compile(r"^---\s*$")
_NOTE_LINE = re.compile(r"^>\s*note:\s*", re.IGNORECASE)
_HEADING = re.compile(r"^#{1,6}\s+(.+)")


def _parse_front_matter(text: str) -> tuple[FrontMatter, str]:
    """
    If the text starts with a YAML front matter block (--- ... ---),
    parse it and return (FrontMatter, remaining_text).
    Otherwise return (FrontMatter(), text).
    """
    lines = text.splitlines(keepends=True)
    if not lines or not _YAML_FENCE.match(lines[0].rstrip()):
        return FrontMatter(), text

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if _YAML_FENCE.match(line.rstrip()):
            end_idx = i
            break

    if end_idx is None:
        return FrontMatter(), text

    yaml_block = "".join(lines[1:end_idx])
    rest = "".join(lines[end_idx + 1:])

    fm = FrontMatter()
    try:
        import yaml
        data = yaml.safe_load(yaml_block) or {}
        fm.title = str(data.get("title", ""))
        fm.author = str(data.get("author", ""))
        fm.theme = str(data.get("theme", "dark"))
        fm.date = str(data.get("date", ""))
    except Exception:
        pass

    return fm, rest


def _split_slides(text: str) -> list[str]:
    """Split raw markdown text on bare --- lines into slide blocks."""
    blocks: list[str] = []
    current: list[str] = []

    for line in text.splitlines(keepends=True):
        if re.match(r"^\s*---\s*$", line):
            blocks.append("".join(current))
            current = []
        else:
            current.append(line)

    blocks.append("".join(current))
    return [b for b in blocks if b.strip()]


def _parse_slide(raw: str) -> Slide:
    lines = raw.splitlines(keepends=True)
    title = ""
    body_lines: list[str] = []
    note_lines: list[str] = []

    title_found = False
    for line in lines:
        stripped = line.rstrip("\n")
        if not title_found:
            m = _HEADING.match(stripped)
            if m:
                title = m.group(1).strip()
                title_found = True
                continue
        if _NOTE_LINE.match(stripped):
            note_text = _NOTE_LINE.sub("", stripped).strip()
            note_lines.append(note_text)
        else:
            body_lines.append(line)

    body = "".join(body_lines).strip()
    notes = "\n".join(note_lines).strip()
    return Slide(title=title, body=body, notes=notes, raw=raw)


def parse_file(path: str) -> Deck:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return parse_text(content, source_path=path)


def parse_text(content: str, source_path: str = "") -> Deck:
    fm, rest = _parse_front_matter(content.lstrip())
    blocks = _split_slides(rest)

    slides = [_parse_slide(b) for b in blocks]

    deck = Deck(slides=slides, front_matter=fm, source_path=source_path)
    return deck


def reassemble(deck: Deck) -> str:
    """Reassemble a Deck back into a markdown string (for saving)."""
    parts: list[str] = []

    fm = deck.front_matter
    if fm.title or fm.author or fm.theme != "dark" or fm.date:
        lines = ["---\n"]
        if fm.title:
            lines.append(f"title: {fm.title}\n")
        if fm.author:
            lines.append(f"author: {fm.author}\n")
        if fm.theme:
            lines.append(f"theme: {fm.theme}\n")
        if fm.date:
            lines.append(f"date: {fm.date}\n")
        lines.append("---\n")
        parts.append("".join(lines))

    slide_texts = []
    for slide in deck.slides:
        slide_texts.append(slide.raw.strip())

    parts.append("\n\n---\n\n".join(slide_texts))
    return "\n\n".join(parts) + "\n"
