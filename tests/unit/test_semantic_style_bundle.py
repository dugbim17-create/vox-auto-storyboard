from __future__ import annotations

import json
from pathlib import Path

from app.cli import main


def test_vox_style_bundle_cli_renders_four_distinct_families(tmp_path: Path) -> None:
    code = main(["render-vox-style-bundle", "--output-root", str(tmp_path)])

    assert code == 0
    root = tmp_path / "vox-style-approval-bundle"
    report = json.loads((root / "manifests" / "style-bundle-qa.json").read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert report["provider_calls"] == 0
    assert report["style_count"] == 4
    assert report["scene_count"] >= 8
    assert set(report["styles"]) == {
        "cutout_character_story",
        "editorial_map_data",
        "archival_document_collage",
        "diagram_process_explainer",
    }
    assert all(len(style["scenes"]) >= 2 for style in report["styles"].values())
    assert all(style["status"] == "PASS" for style in report["styles"].values())
    final = Path(report["final"]["path"])
    assert final.is_file() and final.stat().st_size > 0
    assert len(report["final"]["sha256"]) == 64
