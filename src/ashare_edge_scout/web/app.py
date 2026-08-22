"""Read-only local web console for published Edge Scout research."""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlparse

from ..candle_rules import CandleRuleSet, HammerRule
from ..config import ALLOWED_MODES, load_config, validate_config
from ..portfolio.demo import BOUNDARY_FLAGS, DemoPortfolioError
from ..data.intraday_data import IntradayDataClient
from ..portfolio.paper_risk import normalize_paper_risk
from ..portfolio.paper_state import PaperTradingError
from ..research_watchlist import ResearchWatchlistError
from .errors import ResearchWebError
from .routes.market import (
    build_research_alert as _build_research_alert,
    load_candle_research as _load_candle_research,
    load_dashboard as _load_dashboard,
    load_snapshot_research as _load_snapshot_research,
    normalize_a_share_code,
)
from .routes.demo import (
    demo_factors_payload as _demo_factors_payload,
    demo_portfolio_status_payload as _demo_portfolio_status_payload,
    handle_demo_portfolio_mutation,
    list_demo_portfolios_payload as _list_demo_portfolios_payload,
)
from .routes.paper import (
    paper_data_status_for_portfolio,
    paper_history_payload,
    paper_status_for_portfolio,
)
from .routes.pmkf_mkf import (
    pmkf_mkf_code_payload as _pmkf_mkf_code_payload,
    pmkf_mkf_reports_payload as _pmkf_mkf_reports_payload,
    pmkf_mkf_summary_payload as _pmkf_mkf_summary_payload,
)
from .routes.watchlist import mutate_research_watchlist_payload, research_watchlist_payload


_STATIC_ROOT = Path(__file__).resolve().parents[1] / "web_static"
_STATIC_FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/app.js": "app.js",
    "/style.css": "style.css",
}
@dataclass(frozen=True)
class ResearchWebContext:
    project_root: Path
    data_root: Path
    output_root: Path
    config_path: Path
    candle_rules: CandleRuleSet
    confirmation_volume_ratio: float
    intraday_client: IntradayDataClient
    watchlist_path: Path
    mode: str
    allow_demo_portfolio: bool
    allow_paper_trading: bool
    demo_portfolio_enabled: bool
    demo_state_root: Path
    demo_audit_root: Path
    demo_factor_root: Path
    demo_default_portfolio_id: str
    demo_initial_capital: float
    demo_max_portfolios: int
    demo_max_positions: int
    demo_max_import_positions: int
    paper_trading_enabled: bool
    paper_state_root: Path
    paper_engine_enabled: bool
    paper_manual_intents_enabled: bool
    paper_max_snapshot_codes: int
    paper_risk_controls: dict[str, Any]


def create_context(
    project_root: str | Path,
    *,
    data_root: str | Path | None = None,
    output_root: str | Path | None = None,
    config_path: str | Path | None = None,
    intraday_client: IntradayDataClient | None = None,
    watchlist_path: str | Path | None = None,
) -> ResearchWebContext:
    """Build and validate immutable paths and candle rules for the server."""

    root = Path(project_root).expanduser().resolve()
    config_file = _resolve_from_root(root, config_path or "yaml/edge_scout_v1.yaml")
    config = load_config(config_file)
    validate_config(config, config_file)
    if config.get("mode") not in ALLOWED_MODES:
        raise ResearchWebError("invalid_mode", "研究台仅允许 read_only_research 或 phased_production_adjacent 模式")

    candle = config["setup"]["candle"]
    hammer = candle["hammer"]
    demo_config = dict(config.get("demo_portfolio", {}))
    paper_config = dict(config.get("paper_trading", {}))
    return ResearchWebContext(
        project_root=root,
        data_root=_resolve_from_root(root, data_root or config["paths"]["data_root"]),
        output_root=_resolve_from_root(root, output_root or config["paths"]["output_root"]),
        config_path=config_file,
        candle_rules=CandleRuleSet(
            enabled_patterns=tuple(candle["enabled"]),
            hammer=HammerRule(
                max_body_to_range=float(hammer["max_body_to_range"]),
                min_lower_shadow_to_body=float(hammer["min_lower_shadow_to_body"]),
                max_upper_shadow_to_body=float(hammer["max_upper_shadow_to_body"]),
                min_close_location=float(hammer["min_close_location"]),
                uses_documented_upper_shadow_range_guard=True,
            ),
        ),
        confirmation_volume_ratio=float(config["setup"]["confirmation"]["min_volume_to_ma20"]),
        intraday_client=intraday_client or IntradayDataClient(),
        watchlist_path=_resolve_from_root(
            root,
            watchlist_path or "config/research_watchlist.json",
        ),
        mode=str(config.get("mode")),
        allow_demo_portfolio=bool(config.get("allow_demo_portfolio", False)),
        allow_paper_trading=bool(config.get("allow_paper_trading", False)),
        demo_portfolio_enabled=bool(demo_config.get("enabled", False)),
        demo_state_root=_resolve_from_root(root, demo_config.get("state_root", "output/edge_scout/demo_portfolios")),
        demo_audit_root=_resolve_from_root(root, demo_config.get("audit_root", "output/edge_scout/audit_logs")),
        demo_factor_root=_resolve_from_root(root, demo_config.get("factor_root", "output/edge_scout/demo_factors")),
        demo_default_portfolio_id=str(demo_config.get("default_portfolio_id", "default")),
        demo_initial_capital=float(demo_config.get("initial_capital", 20000.0)),
        demo_max_portfolios=int(demo_config.get("max_portfolios", 5)),
        demo_max_positions=int(demo_config.get("max_positions", 20)),
        demo_max_import_positions=int(demo_config.get("max_import_positions", 50)),
        paper_trading_enabled=bool(paper_config.get("enabled", False)),
        paper_state_root=_resolve_from_root(root, paper_config.get("state_root", "output/edge_scout/paper_trading")),
        paper_engine_enabled=bool(paper_config.get("engine_enabled", False)),
        paper_manual_intents_enabled=bool(paper_config.get("manual_intents_enabled", False)),
        paper_max_snapshot_codes=int(paper_config.get("max_snapshot_codes", 20)),
        paper_risk_controls=normalize_paper_risk(config.get("paper_risk")),
    )


def load_dashboard(context: ResearchWebContext) -> dict[str, Any]:
    return _load_dashboard(
        context,
        read_json_object=_read_json_object,
        published_run_directory=_published_run_directory,
        read_csv_rows=_read_csv_rows,
    )


def load_candle_research(
    context: ResearchWebContext,
    code: str,
    *,
    limit: int = 120,
    period: str = "1d",
) -> dict[str, Any]:
    return _load_candle_research(context, code, limit=limit, period=period)


def load_snapshot_research(context: ResearchWebContext, code: str) -> dict[str, Any]:
    return _load_snapshot_research(context, code)


def _boundary_payload(context: ResearchWebContext) -> dict[str, Any]:
    return {
        **BOUNDARY_FLAGS,
        "mode": context.mode,
        "allow_demo_portfolio": context.allow_demo_portfolio,
        "allow_paper_trading": context.allow_paper_trading,
        "live_broker_enabled": False,
    }


def list_demo_portfolios_payload(context: ResearchWebContext) -> dict[str, Any]:
    return _list_demo_portfolios_payload(context, _boundary_payload(context))


def demo_portfolio_status_payload(context: ResearchWebContext, portfolio_id: str | None = None) -> dict[str, Any]:
    return _demo_portfolio_status_payload(context, _boundary_payload(context), portfolio_id)


def pmkf_mkf_reports_payload(context: ResearchWebContext) -> dict[str, Any]:
    return _pmkf_mkf_reports_payload(
        context,
        boundary_payload=_boundary_payload(context),
        read_json_object=_read_json_object,
        web_error=ResearchWebError,
    )


def pmkf_mkf_summary_payload(context: ResearchWebContext) -> dict[str, Any]:
    return _pmkf_mkf_summary_payload(
        context,
        boundary_payload=_boundary_payload(context),
        read_json_object=_read_json_object,
        web_error=ResearchWebError,
    )


def pmkf_mkf_code_payload(context: ResearchWebContext, code: str) -> dict[str, Any]:
    return _pmkf_mkf_code_payload(
        context,
        code,
        boundary_payload=_boundary_payload(context),
        normalize_code=normalize_a_share_code,
        load_candle_payload=load_candle_research,
        web_error=ResearchWebError,
    )


def make_handler(context: ResearchWebContext) -> type[BaseHTTPRequestHandler]:
    """Create a request handler bound to one validated context."""

    class ResearchRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib hook
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/health":
                    self._send_json({"status": "ok", "read_only": True, **_boundary_payload(context)})
                    return
                if parsed.path == "/api/dashboard":
                    self._send_json(load_dashboard(context))
                    return
                if parsed.path == "/api/candles":
                    query = parse_qs(parsed.query)
                    code = query.get("code", [""])[0]
                    period = query.get("period", ["1d"])[0]
                    try:
                        limit = int(query.get("limit", ["120"])[0])
                    except ValueError as exc:
                        raise ResearchWebError("invalid_limit", "limit 必须是整数") from exc
                    self._send_json(load_candle_research(context, code, limit=limit, period=period))
                    return
                if parsed.path == "/api/snapshot":
                    query = parse_qs(parsed.query)
                    self._send_json(load_snapshot_research(context, query.get("code", [""])[0]))
                    return
                if parsed.path == "/api/research-watchlist":
                    self._send_json(research_watchlist_payload(context.watchlist_path))
                    return
                if parsed.path == "/api/demo-portfolios":
                    self._send_json(list_demo_portfolios_payload(context))
                    return
                if parsed.path == "/api/demo-portfolio/status":
                    query = parse_qs(parsed.query)
                    self._send_json(demo_portfolio_status_payload(context, query.get("portfolio_id", [None])[0]))
                    return
                if parsed.path == "/api/demo-factors":
                    self._send_json(_demo_factors_payload(context, _boundary_payload(context)))
                    return
                if parsed.path == "/api/paper/status":
                    query = parse_qs(parsed.query)
                    self._send_json(paper_status_for_portfolio(context, query.get("portfolio_id", [None])[0]))
                    return
                if parsed.path == "/api/paper/history":
                    query = parse_qs(parsed.query)
                    portfolio_id = query.get("portfolio_id", [context.demo_default_portfolio_id])[0]
                    self._send_json(paper_history_payload(audit_root=context.demo_audit_root, portfolio_id=portfolio_id))
                    return
                if parsed.path == "/api/paper/data-status":
                    query = parse_qs(parsed.query)
                    self._send_json(paper_data_status_for_portfolio(context, query.get("portfolio_id", [None])[0]))
                    return
                if parsed.path == "/api/pmkf-mkf/summary":
                    self._send_json(pmkf_mkf_summary_payload(context))
                    return
                if parsed.path == "/api/pmkf-mkf/reports":
                    self._send_json(pmkf_mkf_reports_payload(context))
                    return
                if parsed.path == "/api/pmkf-mkf/code":
                    query = parse_qs(parsed.query)
                    self._send_json(pmkf_mkf_code_payload(context, query.get("code", [""])[0]))
                    return
                if parsed.path in _STATIC_FILES:
                    self._send_static(_STATIC_FILES[parsed.path])
                    return
                self._send_json({"error": "not_found", "detail": "资源不存在"}, HTTPStatus.NOT_FOUND)
            except ResearchWebError as exc:
                self._send_json({"error": exc.code, "detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            except ResearchWatchlistError as exc:
                self._send_json({"error": exc.code, "detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            except FileNotFoundError as exc:
                self._send_json(
                    {"error": "publication_missing", "detail": str(exc)},
                    HTTPStatus.SERVICE_UNAVAILABLE,
                )
            except Exception:
                self._send_json(
                    {"error": "internal_error", "detail": "研究数据加载失败"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )

        def do_POST(self) -> None:  # noqa: N802 - stdlib hook
            parsed = urlparse(self.path)
            try:
                if parsed.path in {"/api/research-watchlist/add", "/api/research-watchlist/remove"}:
                    self._send_json(mutate_research_watchlist_payload(
                        path=parsed.path,
                        watchlist_path=context.watchlist_path,
                        payload=self._read_json_body(),
                        normalize_code=normalize_a_share_code,
                    ))
                    return
                if parsed.path.startswith("/api/demo-portfolio/"):
                    self._send_json(handle_demo_portfolio_mutation(
                        context=context,
                        path=parsed.path,
                        payload=self._read_json_body(),
                        boundary_payload=_boundary_payload(context),
                        normalize_code=normalize_a_share_code,
                    ))
                    return
                if parsed.path == "/api/paper/intent":
                    self._send_json({"error": "paper_intents_disabled", "detail": "manual paper intents are disabled", **_boundary_payload(context)}, HTTPStatus.FORBIDDEN)
                    return
                self._send_json({"error": "not_found", "detail": "资源不存在"}, HTTPStatus.NOT_FOUND)
            except (ResearchWebError, ResearchWatchlistError, DemoPortfolioError, PaperTradingError) as exc:
                self._send_json({"error": exc.code, "detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception:
                self._send_json(
                    {"error": "internal_error", "detail": "自选研究列表更新失败"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )


        def _read_json_body(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise ResearchWebError("invalid_request", "Content-Length 无效") from exc
            if length < 1 or length > 65536:
                raise ResearchWebError("invalid_request", "请求正文大小无效")
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ResearchWebError("invalid_request", "请求正文必须是 JSON") from exc
            if not isinstance(payload, dict):
                raise ResearchWebError("invalid_request", "请求正文必须是 JSON 对象")
            return payload

        def _send_json(self, payload: Mapping[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            content = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def _send_static(self, filename: str) -> None:
            path = _STATIC_ROOT / filename
            content = path.read_bytes()
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, format: str, *args: object) -> None:
            print(f"[research-web] {self.address_string()} {format % args}")

    return ResearchRequestHandler


def serve(context: ResearchWebContext, *, host: str = "127.0.0.1", port: int = 9091) -> None:
    """Run the local read-only research server until interrupted."""

    server = HTTPServer((host, port), make_handler(context))
    print(f"NCN K线研究台: http://{host}:{server.server_port}")
    print("边界: 分阶段 production-adjacent；Demo/Paper-only；Live orders off；无 broker connection。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NCN read-only candlestick research web console")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9091)
    args = parser.parse_args(argv)
    context = create_context(
        args.project_root,
        data_root=args.data_root,
        output_root=args.output_root,
        config_path=args.config,
    )
    serve(context, host=args.host, port=args.port)
    return 0


def _resolve_from_root(root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResearchWebError("invalid_publication", f"{label} 不是有效 JSON") from exc
    if not isinstance(payload, dict):
        raise ResearchWebError("invalid_publication", f"{label} 必须是 JSON 对象")
    return payload


def _published_run_directory(output_root: Path, latest: Mapping[str, Any]) -> Path:
    run_name = latest.get("run_directory")
    if not isinstance(run_name, str) or not run_name or Path(run_name).name != run_name:
        raise ResearchWebError("invalid_publication", "latest.json 包含无效 run_directory")
    run_directory = (output_root / run_name).resolve()
    if run_directory.parent != output_root.resolve():
        raise ResearchWebError("invalid_publication", "run_directory 超出发布目录")
    return run_directory


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))



if __name__ == "__main__":
    raise SystemExit(main())
