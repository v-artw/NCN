"""Research watchlist route boundary for the NCN Web console."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ...research_watchlist import add_research_code, load_research_watchlist, remove_research_code


def research_watchlist_payload(watchlist_path: Path) -> dict[str, Any]:
    return {"codes": list(load_research_watchlist(watchlist_path)), "research_only": True}


def mutate_research_watchlist_payload(
    *,
    path: str,
    watchlist_path: Path,
    payload: Mapping[str, Any],
    normalize_code: Callable[[str], str],
) -> dict[str, Any]:
    raw_code = payload.get("code", "")
    if path.endswith("/add"):
        codes = add_research_code(
            watchlist_path,
            raw_code,
            normalize=normalize_code,
        )
    else:
        codes = remove_research_code(
            watchlist_path,
            raw_code,
            normalize=normalize_code,
        )
    return {"codes": list(codes), "research_only": True}


__all__ = [
    "add_research_code",
    "load_research_watchlist",
    "mutate_research_watchlist_payload",
    "remove_research_code",
    "research_watchlist_payload",
]
