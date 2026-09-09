from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from scripts.quiz_style_pilot import FIXTURE, STYLES, validate_fixture, validate_run


RUN = "20260908T110725Z"
HYBRID_RUN = "20260908T160220Z"


def test_phase_a_fixture_is_single_locale_and_has_comparison_cases() -> None:
    validate_fixture()
    assert FIXTURE["locale"] == "en-US"
    assert [choice["id"] for choice in FIXTURE["content"]["choices"]] == ["A", "B", "C", "D"]
    assert len(STYLES) == 3
    assert {style.style_id for style in STYLES} == {
        "sport-scoreboard",
        "editorial-culture",
        "clear-knowledge",
    }


def test_phase_a_run_readback_has_exact_png_artifacts_and_no_video() -> None:
    result = validate_run(RUN)
    assert result == {
        "status": "PASS",
        "run": RUN,
        "artifact_count": 11,
        "provider_calls": 0,
        "tts_calls": 0,
        "video_exports": 0,
    }
    run_dir = Path("output/channel-style-packs") / RUN
    manifest = json.loads((run_dir / "artifact-manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["artifacts"]) == 11
    assert not list(run_dir.glob("*.mp4"))
    assert not list(run_dir.glob("*.partial*"))


def test_phase_a_pngs_are_real_decodable_pixels() -> None:
    run_dir = Path("output/channel-style-packs") / RUN
    manifest = json.loads((run_dir / "artifact-manifest.json").read_text(encoding="utf-8"))
    for item in manifest["artifacts"]:
        with Image.open(item["path"]) as image:
            image.load()
            assert image.format == "PNG"
            assert image.mode == "RGB"
            assert image.getbbox() is not None


def test_hybrid_phase_a_run_readback_has_three_pngs_and_no_video() -> None:
    result = validate_run(HYBRID_RUN)
    assert result == {
        "status": "PASS",
        "run": HYBRID_RUN,
        "artifact_count": 3,
        "provider_calls": 0,
        "tts_calls": 0,
        "video_exports": 0,
    }
    run_dir = Path("output/channel-style-packs") / HYBRID_RUN
    assert {path.name for path in run_dir.glob("*.png")} == {
        "knowledge-editorial-question.png",
        "knowledge-editorial-long-question.png",
        "knowledge-editorial-reveal.png",
    }
    assert not list(run_dir.glob("*.mp4"))
    assert not list(run_dir.glob("*.partial*"))
