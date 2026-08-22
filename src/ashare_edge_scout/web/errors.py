"""Stable client-facing Web errors."""

from __future__ import annotations


class ResearchWebError(ValueError):
    """Stable client-facing error raised by the research web service."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)
