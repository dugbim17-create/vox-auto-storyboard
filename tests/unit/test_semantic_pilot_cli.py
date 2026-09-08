from __future__ import annotations

import json
from pathlib import Path

from app.cli import main


def test_semantic_pilot_cli_renders_six_scenes_and_final_without_providers(
    tmp_path: Path,
    capsys,
) -> None:
    code = main(["render-semantic-pilot", "--output-root", str(tmp_path)])

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["renderer"] == "vox_semantic_ffmpeg_pillow"
    assert result["provider_calls"] == 0
    assert len(result["scenes"]) == 6
    assert Path(result["final_mp4"]).is_file()
    report = json.loads(Path(result["qa_report"]).read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert report["scene_count"] == 6
    assert all(scene["status"] == "PASS" for scene in report["scenes"])
