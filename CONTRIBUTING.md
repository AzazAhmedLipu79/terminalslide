# Contributing to TerminalSlide

Thanks for taking the time to contribute. TerminalSlide is a small, focused tool and contributions are very welcome — whether it's a bug fix, a new feature, a theme, or just improving the docs.

---

## Getting Started

```bash
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/terminalslide.git
cd terminalslide

# 2. Create a virtual environment and install in editable mode
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 3. Verify everything works
terminalslide --version
terminalslide -r starter.md
```

---

## Project Structure

```
terminalslide/
├── __init__.py       # Package version
├── main.py           # Textual app + CLI entry point
├── parser.py         # Markdown → Deck/Slide objects
├── renderer.py       # Slide → Rich Panel renderables
├── themes.py         # Theme definitions (dark / light / minimal)
├── overview.py       # Tab overview grid screen
├── editor.py         # Inline slide editor screen
├── timer.py          # Talk timer logic
├── watcher.py        # watchdog file watcher
├── keybinds.py       # ? help overlay
└── pdf_export.py     # PDF generation via reportlab
```

---

## Making Changes

1. **Create a branch** for your work:
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Make your changes** — keep them focused. One feature or fix per PR.

3. **Test manually** — there are no automated tests yet, so run the tool and verify your change works:
   ```bash
   terminalslide starter.md
   ```

4. **Check for syntax errors**:
   ```bash
   python -m py_compile terminalslide/*.py && echo "all clean"
   ```

5. **Commit with a clear message**:
   ```bash
   git commit -m "feat: add search by slide title"
   git commit -m "fix: overview not updating on delete"
   git commit -m "docs: improve installation instructions"
   ```

6. **Push and open a Pull Request** against `main`.

---

## What to Work On

Here are good first areas if you're looking for somewhere to start:

- **Search** (`/`) — jump to a slide by title keyword
- **Duplicate slide** (`c`) — copy the current slide
- **Theme customization** — allow user-defined themes via front matter or config
- **Presenter view** — split screen with notes on one side
- **Tests** — any pytest coverage for `parser.py` or `renderer.py` would be very welcome
- **Windows support** — currently untested on Windows terminals

---

## Code Style

- Python 3.10+, type hints where it makes the code clearer
- Keep modules small and single-purpose (see structure above)
- Avoid adding dependencies unless clearly necessary — the install footprint matters
- Internal imports use relative imports (`from .parser import Deck`)

---

## Reporting Bugs

Open an issue at [github.com/azazahmedlipu79/terminalslide/issues](https://github.com/azazahmedlipu79/terminalslide/issues) with:

- Your OS and terminal emulator
- Python version (`python --version`)
- The command you ran and the full error output
- Your `.md` file content if relevant (a minimal example is best)

---

## Questions

Open a GitHub Discussion or an issue tagged `question`. There's no mailing list or Discord yet.

---

*TerminalSlide is MIT licensed. By contributing, you agree your changes will be released under the same license.*
