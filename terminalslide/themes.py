from dataclasses import dataclass


@dataclass
class Theme:
    name: str
    background: str
    foreground: str
    title_color: str
    accent: str
    code_background: str
    pygments_style: str


THEMES: dict[str, Theme] = {
    "dark": Theme(
        name="dark",
        background="#1e1e2e",
        foreground="#cdd6f4",
        title_color="#89dceb",
        accent="#89dceb",
        code_background="#313244",
        pygments_style="monokai",
    ),
    "light": Theme(
        name="light",
        background="#fffbf0",
        foreground="#1e1e2e",
        title_color="#1a237e",
        accent="#1565c0",
        code_background="#e8eaf6",
        pygments_style="friendly",
    ),
    "minimal": Theme(
        name="minimal",
        background="#000000",
        foreground="#9e9e9e",
        title_color="#ffffff",
        accent="#ffffff",
        code_background="#111111",
        pygments_style="bw",
    ),
}

THEME_CYCLE = ["dark", "light", "minimal"]


def get_theme(name: str) -> Theme:
    return THEMES.get(name, THEMES["dark"])


def next_theme(current: str) -> Theme:
    idx = THEME_CYCLE.index(current) if current in THEME_CYCLE else 0
    next_name = THEME_CYCLE[(idx + 1) % len(THEME_CYCLE)]
    return THEMES[next_name]
