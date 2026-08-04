from __future__ import annotations

import json
from pathlib import Path

import pytest

from ashare_edge_scout.research_watchlist import (
    ResearchWatchlistError,
    add_research_code,
    load_research_watchlist,
    remove_research_code,
)


def _normalize(value: str) -> str:
    if value == "600000":
        return "sh.600000"
    if value == "000001":
        return "sz.000001"
    raise ValueError("invalid")


def test_atomic_add_remove_and_duplicate_are_stable(tmp_path: Path) -> None:
    path = tmp_path / "config" / "watchlist.json"

    assert add_research_code(path, "600000", normalize=_normalize) == ("sh.600000",)
    assert add_research_code(path, "600000", normalize=_normalize) == ("sh.600000",)
    assert add_research_code(path, "000001", normalize=_normalize) == ("sh.600000", "sz.000001")
    assert remove_research_code(path, "600000", normalize=_normalize) == ("sz.000001",)
    assert load_research_watchlist(path) == ("sz.000001",)
    assert not path.with_name(f".{path.name}.tmp").exists()
    assert json.loads(path.read_text(encoding="utf-8"))["research_only"] is True


def test_watchlist_limit_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.json"
    add_research_code(path, "600000", normalize=_normalize, maximum=1)
    with pytest.raises(ResearchWatchlistError) as error:
        add_research_code(path, "000001", normalize=_normalize, maximum=1)
    assert error.value.code == "watchlist_full"


def test_invalid_persisted_watchlist_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.json"
    path.write_text('{"codes":["sh.600000","sh.600000"]}', encoding="utf-8")
    with pytest.raises(ResearchWatchlistError) as error:
        load_research_watchlist(path)
    assert error.value.code == "invalid_watchlist"
