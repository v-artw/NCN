"""Demo portfolio state for paper-only NCN Web workflows."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "ncn_demo_portfolio_v1"
ALLOWED_POSITION_STATES = {
    "WATCH",
    "RESEARCH_REVIEW",
    "PAPER_PRE_BUY",
    "PAPER_HOLD",
    "PAPER_EXITED",
}
BOUNDARY_FLAGS = {
    "paper_only": True,
    "live_execution_enabled": False,
    "allow_live_order_submission": False,
    "production_enabled": False,
}
_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_FACTOR_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}\.txt$")


class DemoPortfolioError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


def validate_portfolio_id(portfolio_id: str) -> str:
    if not isinstance(portfolio_id, str):
        raise DemoPortfolioError("invalid_portfolio_id", "portfolio_id 必须是字符串")
    value = portfolio_id.strip()
    if (
        not _ID_PATTERN.fullmatch(value)
        or ".." in value
        or value.startswith(".")
        or value.endswith(".")
        or "/" in value
        or "\\" in value
    ):
        raise DemoPortfolioError("invalid_portfolio_id", "portfolio_id 只能使用安全 slug")
    return value


def validate_factor_filename(filename: str) -> str:
    if not isinstance(filename, str):
        raise DemoPortfolioError("invalid_factor_filename", "factor filename 必须是字符串")
    value = filename.strip()
    if (
        not _FACTOR_PATTERN.fullmatch(value)
        or Path(value).name != value
        or ".." in value
        or value.startswith(".")
    ):
        raise DemoPortfolioError("invalid_factor_filename", "factor filename 必须是安全 .txt 文件名")
    return value


def default_portfolio(portfolio_id: str, *, initial_capital: float, max_positions: int) -> dict[str, Any]:
    safe_id = validate_portfolio_id(portfolio_id)
    capital = float(initial_capital)
    if capital <= 0:
        raise DemoPortfolioError("invalid_initial_capital", "initial_capital 必须大于 0")
    return {
        "schema_version": SCHEMA_VERSION,
        "portfolio_id": safe_id,
        "mode": "demo_portfolio",
        **BOUNDARY_FLAGS,
        "broker_account_id": None,
        "initial_capital": capital,
        "demo_cash": capital,
        "demo_max_equity_high": capital,
        "settings": {"max_positions": int(max_positions)},
        "positions": {},
    }


def list_portfolios(state_root: Path) -> list[str]:
    state_root.mkdir(parents=True, exist_ok=True)
    return sorted(path.stem for path in state_root.glob("*.json") if _safe_portfolio_path(state_root, path.stem) == path.resolve())


def load_portfolio(state_root: Path, portfolio_id: str, *, initial_capital: float, max_positions: int) -> dict[str, Any]:
    path = portfolio_path(state_root, portfolio_id)
    if not path.is_file():
        portfolio = default_portfolio(portfolio_id, initial_capital=initial_capital, max_positions=max_positions)
        save_portfolio(state_root, portfolio)
        return portfolio
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DemoPortfolioError("invalid_portfolio_state", "demo portfolio state 不是有效 JSON") from exc
    if not isinstance(payload, dict):
        raise DemoPortfolioError("invalid_portfolio_state", "demo portfolio state 必须是对象")
    return normalize_portfolio(payload, initial_capital=initial_capital, max_positions=max_positions)


def save_portfolio(state_root: Path, portfolio: Mapping[str, Any]) -> None:
    portfolio_id = validate_portfolio_id(str(portfolio.get("portfolio_id", "")))
    path = portfolio_path(state_root, portfolio_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(dict(portfolio), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def portfolio_path(state_root: Path, portfolio_id: str) -> Path:
    safe_id = validate_portfolio_id(portfolio_id)
    state_root.mkdir(parents=True, exist_ok=True)
    path = (state_root / f"{safe_id}.json").resolve()
    if path.parent != state_root.resolve():
        raise DemoPortfolioError("invalid_portfolio_id", "portfolio_id 超出状态目录")
    return path


def normalize_portfolio(payload: Mapping[str, Any], *, initial_capital: float, max_positions: int) -> dict[str, Any]:
    portfolio_id = validate_portfolio_id(str(payload.get("portfolio_id", "default")))
    positions_raw = payload.get("positions", {})
    if not isinstance(positions_raw, dict):
        raise DemoPortfolioError("invalid_portfolio_state", "positions 必须是对象")
    positions = {
        str(code): normalize_position(str(code), value)
        for code, value in positions_raw.items()
    }
    settings = payload.get("settings", {}) if isinstance(payload.get("settings", {}), dict) else {}
    configured_max = int(settings.get("max_positions", max_positions))
    if configured_max < 1 or configured_max > int(max_positions):
        raise DemoPortfolioError("invalid_settings", "max_positions 超出配置上限")
    result = default_portfolio(portfolio_id, initial_capital=initial_capital, max_positions=configured_max)
    result["initial_capital"] = float(payload.get("initial_capital", initial_capital))
    result["demo_cash"] = float(payload.get("demo_cash", result["initial_capital"]))
    result["demo_max_equity_high"] = float(payload.get("demo_max_equity_high", result["initial_capital"]))
    result["settings"] = {"max_positions": configured_max}
    result["positions"] = positions
    return result


def normalize_position(code: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DemoPortfolioError("invalid_position", "position 必须是对象")
    state = str(value.get("state", "WATCH")).strip().upper()
    if state not in ALLOWED_POSITION_STATES:
        raise DemoPortfolioError("invalid_position_state", "position state 不在允许范围内")
    quantity = _non_negative_float(value.get("quantity", 0.0), "quantity")
    reference_price = _non_negative_float(value.get("reference_price", 0.0), "reference_price")
    note = str(value.get("note", ""))[:240]
    return {
        "code": code,
        "state": state,
        "quantity": quantity,
        "reference_price": reference_price,
        "note": note,
        "updated_at": str(value.get("updated_at") or _now()),
    }


def add_position(
    portfolio: Mapping[str, Any],
    *,
    code: str,
    state: str = "WATCH",
    quantity: float = 0.0,
    reference_price: float = 0.0,
    note: str = "",
) -> dict[str, Any]:
    result = dict(portfolio)
    positions = dict(result.get("positions", {}))
    max_positions = int(result.get("settings", {}).get("max_positions", 20))
    if code not in positions and len(positions) >= max_positions:
        raise DemoPortfolioError("max_positions_exceeded", "demo portfolio positions 已达上限")
    positions[code] = normalize_position(code, {
        "state": state,
        "quantity": quantity,
        "reference_price": reference_price,
        "note": note,
        "updated_at": _now(),
    })
    result["positions"] = positions
    return result


def update_position(portfolio: Mapping[str, Any], *, code: str, updates: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(portfolio)
    positions = dict(result.get("positions", {}))
    if code not in positions:
        raise DemoPortfolioError("position_not_found", "demo position 不存在")
    allowed = {"state", "quantity", "reference_price", "note"}
    unknown = set(updates) - allowed
    if unknown:
        raise DemoPortfolioError("invalid_position_update", "position update 包含不允许字段")
    current = dict(positions[code])
    current.update({key: updates[key] for key in allowed if key in updates})
    current["updated_at"] = _now()
    positions[code] = normalize_position(code, current)
    result["positions"] = positions
    return result


def remove_position(portfolio: Mapping[str, Any], *, code: str) -> dict[str, Any]:
    result = dict(portfolio)
    positions = dict(result.get("positions", {}))
    positions.pop(code, None)
    result["positions"] = positions
    return result


def set_settings(portfolio: Mapping[str, Any], *, max_positions: int, configured_max_positions: int) -> dict[str, Any]:
    value = int(max_positions)
    if value < 1 or value > int(configured_max_positions):
        raise DemoPortfolioError("invalid_settings", "max_positions 超出配置上限")
    if len(dict(portfolio.get("positions", {}))) > value:
        raise DemoPortfolioError("invalid_settings", "max_positions 不能小于当前 position 数量")
    result = dict(portfolio)
    result["settings"] = {"max_positions": value}
    return result


def import_positions(portfolio: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], *, max_import_positions: int, normalize_code) -> dict[str, Any]:
    if len(rows) > int(max_import_positions):
        raise DemoPortfolioError("max_import_positions_exceeded", "导入 positions 超出上限")
    result = dict(portfolio)
    positions = dict(result.get("positions", {}))
    max_positions = int(result.get("settings", {}).get("max_positions", 20))
    for row in rows:
        if not isinstance(row, Mapping):
            raise DemoPortfolioError("invalid_import", "导入项必须是对象")
        code = normalize_code(str(row.get("code", "")))
        if code not in positions and len(positions) >= max_positions:
            raise DemoPortfolioError("max_positions_exceeded", "demo portfolio positions 已达上限")
        positions[code] = normalize_position(code, row)
    result["positions"] = positions
    return result


def reset_capital(portfolio: Mapping[str, Any], *, initial_capital: float) -> dict[str, Any]:
    capital = float(initial_capital)
    if capital <= 0:
        raise DemoPortfolioError("invalid_initial_capital", "initial_capital 必须大于 0")
    result = dict(portfolio)
    result["initial_capital"] = capital
    result["demo_cash"] = capital
    result["demo_max_equity_high"] = capital
    return result


def list_factors(factor_root: Path) -> list[dict[str, Any]]:
    factor_root.mkdir(parents=True, exist_ok=True)
    factors = []
    for path in sorted(factor_root.glob("*.txt")):
        if path.name.startswith(".") or path.resolve().parent != factor_root.resolve():
            continue
        factors.append({"filename": path.name, "size_bytes": path.stat().st_size})
    return factors


def append_audit_event(audit_root: Path, event_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    audit_root.mkdir(parents=True, exist_ok=True)
    event = {
        "schema_version": "ncn_demo_portfolio_audit_v1",
        "event_type": event_type,
        "created_at": _now(),
        **BOUNDARY_FLAGS,
        "payload": dict(payload),
    }
    with (audit_root / "demo_portfolio_events.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    return event


def read_audit_events(audit_root: Path, *, limit: int = 50) -> list[dict[str, Any]]:
    path = audit_root / "demo_portfolio_events.jsonl"
    if not path.is_file():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def _safe_portfolio_path(state_root: Path, portfolio_id: str) -> Path:
    return (state_root / f"{validate_portfolio_id(portfolio_id)}.json").resolve()


def _non_negative_float(value: Any, label: str) -> float:
    parsed = float(value or 0.0)
    if parsed < 0:
        raise DemoPortfolioError("invalid_position", f"{label} 必须非负")
    return parsed


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "ALLOWED_POSITION_STATES",
    "BOUNDARY_FLAGS",
    "DemoPortfolioError",
    "add_position",
    "append_audit_event",
    "default_portfolio",
    "import_positions",
    "list_factors",
    "list_portfolios",
    "load_portfolio",
    "normalize_portfolio",
    "normalize_position",
    "portfolio_path",
    "read_audit_events",
    "remove_position",
    "reset_capital",
    "save_portfolio",
    "set_settings",
    "update_position",
    "validate_factor_filename",
    "validate_portfolio_id",
]
