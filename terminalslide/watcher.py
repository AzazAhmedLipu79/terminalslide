from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Callable

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent
    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False


class _Handler(FileSystemEventHandler if _WATCHDOG_AVAILABLE else object):
    def __init__(self, path: str, callback: Callable[[], None]) -> None:
        if _WATCHDOG_AVAILABLE:
            super().__init__()
        self._path = str(Path(path).resolve())
        self._callback = callback
        self._lock = threading.Lock()

    def on_modified(self, event: "FileModifiedEvent") -> None:
        if str(Path(event.src_path).resolve()) == self._path:
            with self._lock:
                self._callback()


class FileWatcher:
    """
    Watch a single file for modifications.
    Calls `callback` on the calling thread via watchdog's background thread.
    The callback should post a Textual message — not touch UI directly.
    """

    def __init__(self, path: str, callback: Callable[[], None]) -> None:
        self._path = path
        self._callback = callback
        self._observer: "Observer | None" = None

    def start(self) -> None:
        if not _WATCHDOG_AVAILABLE:
            print("Warning: watchdog not installed — live reload disabled.", file=sys.stderr)
            return
        try:
            handler = _Handler(self._path, self._callback)
            directory = str(Path(self._path).parent.resolve())
            self._observer = Observer()
            self._observer.schedule(handler, directory, recursive=False)
            self._observer.start()
        except Exception as e:
            print(f"Warning: file watcher failed to start: {e}", file=sys.stderr)

    def stop(self) -> None:
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except Exception:
                pass
            self._observer = None
