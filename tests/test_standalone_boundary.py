from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_runtime_tree_has_no_legacy_project_dependency() -> None:
    forbidden = (
        "a_share_short_swing",
        "/Users/artx/Local/Git/Stock/CN",
        "/Users/artx/Local/Git/CNstock",
        "com.vartw.stock-cn.edge-scout",
    )
    paths = [
        *ROOT.glob("src/**/*.py"),
        *ROOT.glob("scripts/*.py"),
        *ROOT.glob("scripts/*.sh"),
        *ROOT.glob("config/**/*.plist"),
        *ROOT.glob("config/**/*.json"),
    ]
    for path in paths:
        content = path.read_text(encoding="utf-8")
        assert not any(value in content for value in forbidden), path


def test_source_tree_contains_only_edge_scout_package() -> None:
    assert {path.name for path in (ROOT / "src").iterdir() if path.is_dir()} <= {
        "ashare_edge_scout",
        "ashare_edge_scout.egg-info",
    }
