from __future__ import annotations

from pathlib import Path


def test_remote_sync_excludes_local_claude_settings() -> None:
    script = Path("scripts/remote_test_env.sh").read_text(encoding="utf-8")
    assert "--exclude '/.claude/settings.local.json'" in script
    assert "--exclude '/Key/'" in script
    assert "--exclude '/.runtime/'" in script


def test_edge_scout_scan_requires_executable_python() -> None:
    script = Path("scripts/edge_scout_scan.sh").read_text(encoding="utf-8")
    assert 'if [ ! -x "${VENV}" ]; then' in script
    assert "DEFAULT_AS_OF" not in script


def test_remote_study_fetch_uses_structured_evidence_destination() -> None:
    script = Path("scripts/remote_test_env.sh").read_text(encoding="utf-8")
    assert 'local destination="${1:-docs/research/results/strategy/signal-study-2018-2026.json}"' in script
    assert 'mkdir -p "$(dirname "${destination}")"' in script
