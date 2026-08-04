"""Atomic local persistence for a research-only manually selected watchlist."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable


class ResearchWatchlistError(ValueError):
    """Stable validation error for the local research watchlist."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


def load_research_watchlist(path: Path) -> tuple[str, ...]:
    """Load a strictly validated code list; a missing file means no selections."""

    if not path.exists():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResearchWatchlistError("invalid_watchlist", "自选研究列表不是有效 JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("codes"), list):
        raise ResearchWatchlistError("invalid_watchlist", "自选研究列表必须包含 codes 数组")
    codes = payload["codes"]
    if len(codes) > 50 or any(not isinstance(code, str) or not code for code in codes):
        raise ResearchWatchlistError("invalid_watchlist", "自选研究列表代码无效或超过 50 只")
    if len(set(codes)) != len(codes):
        raise ResearchWatchlistError("invalid_watchlist", "自选研究列表包含重复代码")
    return tuple(codes)


def add_research_code(
    path: Path,
    raw_code: str,
    *,
    normalize: Callable[[str], str],
    maximum: int = 20,
) -> tuple[str, ...]:
    code = normalize(raw_code)
    codes = list(load_research_watchlist(path))
    if code in codes:
        return tuple(codes)
    if len(codes) >= maximum:
        raise ResearchWatchlistError("watchlist_full", f"自选研究列表最多 {maximum} 只")
    codes.append(code)
    _write_atomic(path, codes)
    return tuple(codes)


def remove_research_code(
    path: Path,
    raw_code: str,
    *,
    normalize: Callable[[str], str],
) -> tuple[str, ...]:
    code = normalize(raw_code)
    codes = list(load_research_watchlist(path))
    if code in codes:
        codes.remove(code)
        _write_atomic(path, codes)
    return tuple(codes)


def _write_atomic(path: Path, codes: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    content = json.dumps(
        {"schema_version": "research_watchlist_v1", "research_only": True, "codes": codes},
        ensure_ascii=False,
        indent=2,
    )
    try:
        temporary.write_text(content + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
