from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class TalkTimer:
    _start_time: float = field(default=0.0, init=False)
    _elapsed_at_pause: float = field(default=0.0, init=False)
    _running: bool = field(default=False, init=False)
    target_seconds: float = 0.0  # 0 means no target

    def start(self) -> None:
        if not self._running:
            self._start_time = time.monotonic()
            self._running = True

    def pause(self) -> None:
        if self._running:
            self._elapsed_at_pause += time.monotonic() - self._start_time
            self._running = False

    def toggle(self) -> None:
        if self._running:
            self.pause()
        else:
            self.start()

    def reset(self) -> None:
        self._running = False
        self._start_time = 0.0
        self._elapsed_at_pause = 0.0

    def elapsed(self) -> float:
        if self._running:
            return self._elapsed_at_pause + (time.monotonic() - self._start_time)
        return self._elapsed_at_pause

    @property
    def is_running(self) -> bool:
        return self._running

    def formatted(self) -> str:
        total = int(self.elapsed())
        mins = total // 60
        secs = total % 60
        return f"{mins}:{secs:02d}"

    def color(self) -> str:
        """Return a Rich color string based on progress vs target."""
        if self.target_seconds <= 0:
            return "white"
        ratio = self.elapsed() / self.target_seconds
        if ratio >= 1.0:
            return "red"
        if ratio >= 0.8:
            return "yellow"
        return "white"
