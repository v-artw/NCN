from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path

from ashare_edge_scout.research_web import create_context, make_handler

ROOT = Path(__file__).parents[1]


def test_paper_endpoints_are_paper_only_and_intents_disabled(tmp_path: Path) -> None:
    context = create_context(ROOT, output_root=tmp_path / "missing-output")
    server, thread = _server(context)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        _post_json(f"{base}/api/demo-portfolio/add", {"portfolio_id": "default", "code": "600000", "state": "PAPER_HOLD"})
        status = _get_json(f"{base}/api/paper/status?portfolio_id=default")
        assert status["schema_version"] == "ncn_paper_status_v1"
        assert status["paper_only"] is True
        assert status["live_execution_enabled"] is False
        assert status["allow_live_order_submission"] is False
        assert status["simulated_positions"][0]["code"] == "sh.600000"
        data_status = _get_json(f"{base}/api/paper/data-status?portfolio_id=default")
        assert data_status["limitations"] == ["local_research_parquet_only", "not_execution_freshness", "no_broker_feed"]
        history = _get_json(f"{base}/api/paper/history?portfolio_id=default")
        assert history["source"] == "ncn_demo_portfolio_audit_jsonl"
        try:
            _post_json(f"{base}/api/paper/intent", {"portfolio_id": "default", "code": "600000"})
        except urllib.error.HTTPError as exc:
            payload = json.loads(exc.read().decode("utf-8"))
            assert exc.code == 403
            assert payload["error"] == "paper_intents_disabled"
            assert payload["live_execution_enabled"] is False
    finally:
        _shutdown(server, thread)


def test_pmkf_mkf_summary_endpoint_is_precomputed_report_only(tmp_path: Path) -> None:
    context = create_context(ROOT, output_root=tmp_path / "output")
    server, thread = _server(context)
    try:
        payload = _get_json(f"http://127.0.0.1:{server.server_port}/api/pmkf-mkf/summary")
        assert payload["schema_version"] == "ncn_pmkf_mkf_summary_v1"
        assert "no_all_universe_scan_in_web_request" in payload["warnings"]
        assert payload["allow_live_order_submission"] is False
    finally:
        _shutdown(server, thread)


def _server(context):
    server = HTTPServer(("127.0.0.1", 0), make_handler(context))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _shutdown(server, thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=2) as response:
        return json.load(response)


def _post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.load(response)
