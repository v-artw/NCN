from __future__ import annotations

from pathlib import Path


def test_repurchase_probe_uses_structured_precision70_sample() -> None:
    script = Path("scripts/probe_cninfo_repurchase_counts.py").read_text(encoding="utf-8")
    assert (
        'DEFAULT_SAMPLE_PATH = Path("docs/research/results/stage1/'
        'precision70-stage1-2021-2026.json")'
    ) in script
    assert 'parser.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE_PATH)' in script
