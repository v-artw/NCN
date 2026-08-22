from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path

from ashare_edge_scout.research_web import create_context, make_handler

ROOT = Path(__file__).parents[1]


def test_demo_portfolio_endpoints_work_without_publication(tmp_path: Path) -> None:
    context = create_context(ROOT, output_root=tmp_path / "missing-output")
    server, thread = _server(context)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        status = _get_json(f"{base}/api/demo-portfolio/status?portfolio_id=default")
        assert status["portfolio"]["schema_version"] == "ncn_demo_portfolio_v1"
        assert status["paper_only"] is True
        add = _post_json(f"{base}/api/demo-portfolio/add", {"portfolio_id": "default", "code": "600000", "state": "WATCH"})
        assert add["portfolio"]["positions"]["sh.600000"]["state"] == "WATCH"
        assert add["allow_live_order_submission"] is False
        listed = _get_json(f"{base}/api/demo-portfolios")
        assert "default" in listed["portfolios"]
        factors = _get_json(f"{base}/api/demo-factors")
        assert factors["factors"] == []
    finally:
        _shutdown(server, thread)


def test_demo_portfolio_rejects_unsafe_and_force_buy_absent(tmp_path: Path) -> None:
    context = create_context(ROOT, output_root=tmp_path / "missing-output")
    server, thread = _server(context)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        for route in ("/force_buy", "/api/force_buy"):
            try:
                urllib.request.urlopen(f"{base}{route}", timeout=2)
            except urllib.error.HTTPError as exc:
                payload = json.loads(exc.read().decode("utf-8"))
                assert exc.code == 404
                assert payload["error"] == "not_found"
        try:
            _post_json(f"{base}/api/demo-portfolio/add", {"portfolio_id": "../x", "code": "600000"})
        except urllib.error.HTTPError as exc:
            payload = json.loads(exc.read().decode("utf-8"))
            assert exc.code == 400
            assert payload["error"] == "invalid_portfolio_id"
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
