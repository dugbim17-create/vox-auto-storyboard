from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.quiz_pilot import QuizPilotComposer, QuizPilotError, QuizPilotLedger


def _valid_probe() -> dict:
    return {
        "video": {"codec": "h264", "width": 1280, "height": 720, "fps": 30.0, "pix_fmt": "yuv420p"},
        "audio": {"codec": "aac", "sample_rate": 48000, "channels": 2},
        "duration_ms": 7900,
    }


def test_ledger_initializes_intro_five_questions_and_outro(tmp_path: Path) -> None:
    ledger = QuizPilotLedger.create(tmp_path / "pilot-ledger.json", [f"q{i:03d}" for i in range(1, 6)])

    assert [item["item_id"] for item in ledger.document["items"]] == [
        "intro", "q001", "q002", "q003", "q004", "q005", "outro"
    ]
    assert all(item["status"] == "planned" for item in ledger.document["items"])
    assert all(item["render_calls"] == 0 for item in ledger.document["items"])


def test_checkpoint_then_validate_persists_hash_probe_and_resume_skips_item(tmp_path: Path) -> None:
    path = tmp_path / "q001.mp4"
    path.write_bytes(b"validated-unit")
    ledger_path = tmp_path / "pilot-ledger.json"
    ledger = QuizPilotLedger.create(ledger_path, ["q001", "q002", "q003", "q004", "q005"])

    ledger.checkpoint_render("q001")
    ledger.mark_validated("q001", path, _valid_probe())
    reloaded = QuizPilotLedger.load(ledger_path)

    q001 = reloaded.item("q001")
    assert q001["status"] == "validated"
    assert q001["render_calls"] == 1
    assert q001["bytes"] == path.stat().st_size
    assert len(q001["sha256"]) == 64
    assert reloaded.pending_items() == ["intro", "q002", "q003", "q004", "q005", "outro"]


def test_adopt_existing_validated_artifact_records_reuse_without_render_call(tmp_path: Path) -> None:
    path = tmp_path / "q001.mp4"
    path.write_bytes(b"existing-validated-unit")
    ledger = QuizPilotLedger.create(
        tmp_path / "pilot-ledger.json", ["q001", "q002", "q003", "q004", "q005"]
    )

    ledger.adopt_validated("q001", path, _valid_probe())

    item = ledger.item("q001")
    assert item["status"] == "validated"
    assert item["render_calls"] == 0
    assert item["reused"] is True


def test_resume_rejects_corrupt_completed_artifact_without_incrementing_render_calls(tmp_path: Path) -> None:
    path = tmp_path / "q001.mp4"
    path.write_bytes(b"validated-unit")
    ledger = QuizPilotLedger.create(tmp_path / "pilot-ledger.json", ["q001", "q002", "q003", "q004", "q005"])
    ledger.checkpoint_render("q001")
    ledger.mark_validated("q001", path, _valid_probe())
    path.write_bytes(b"corrupt")

    pending = ledger.pending_items()

    assert "q001" in pending
    assert ledger.item("q001")["status"] == "artifact_invalid"
    assert ledger.item("q001")["render_calls"] == 1


def test_checkpoint_is_create_once_and_ambiguous_status_does_not_retry(tmp_path: Path) -> None:
    ledger = QuizPilotLedger.create(tmp_path / "pilot-ledger.json", ["q001", "q002", "q003", "q004", "q005"])
    ledger.checkpoint_render("q001")
    ledger.mark_unknown("q001", "renderer response ambiguous")

    with pytest.raises(QuizPilotError, match="already dispatched"):
        ledger.checkpoint_render("q001")

    assert ledger.item("q001")["render_calls"] == 1
    assert ledger.item("q001")["status"] == "render_unknown"


def test_authorized_retry_resets_only_target_and_preserves_other_hashes(tmp_path: Path) -> None:
    ledger = QuizPilotLedger.create(
        tmp_path / "pilot-ledger.json", ["q001", "q002", "q003", "q004", "q005"]
    )
    for qid in ("q001", "q002", "q003", "q004", "q005"):
        path = tmp_path / f"{qid}.mp4"
        path.write_bytes(f"artifact-{qid}".encode())
        ledger.checkpoint_render(qid)
        ledger.mark_validated(qid, path, _valid_probe())
    before = {qid: ledger.item(qid)["sha256"] for qid in ("q001", "q002", "q004", "q005")}

    ledger.authorize_retry("q003", reason="deliberate corruption test")
    ledger.checkpoint_render("q003")

    assert ledger.item("q003")["status"] == "rendering"
    assert ledger.item("q003")["render_calls"] == 2
    assert ledger.item("q003")["retry_count"] == 1
    assert {qid: ledger.item(qid)["sha256"] for qid in before} == before


def test_ledger_json_readback_is_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "pilot-ledger.json"
    first = QuizPilotLedger.create(path, ["q001", "q002", "q003", "q004", "q005"])
    second = QuizPilotLedger.load(path)

    assert json.loads(path.read_text(encoding="utf-8")) == first.document == second.document


def test_ledger_hard_blocks_resume_for_different_approval_fingerprint(tmp_path: Path) -> None:
    path = tmp_path / "scale-ledger.json"
    QuizPilotLedger.create(path, ["q001", "q002"], content_fingerprint="a" * 64)

    same = QuizPilotLedger.load(path, expected_content_fingerprint="a" * 64)
    assert same.document["content_fingerprint"] == "a" * 64

    with pytest.raises(QuizPilotError, match="fingerprint mismatch"):
        QuizPilotLedger.load(path, expected_content_fingerprint="b" * 64)


def test_title_cards_render_embedded_h264_aac_clips(tmp_path: Path) -> None:
    composer = QuizPilotComposer(fps=30)

    intro_path, intro_probe = composer.render_title_clip(
        output_path=tmp_path / "intro.mp4",
        title="THỬ THÁCH VIỆT NAM",
        subtitle="5 câu hỏi • 3 giây mỗi câu",
        duration_ms=1500,
        intro=True,
    )
    outro_path, outro_probe = composer.render_title_clip(
        output_path=tmp_path / "outro.mp4",
        title="HOÀN THÀNH",
        subtitle="Bạn đúng bao nhiêu câu?",
        duration_ms=1500,
        intro=False,
    )

    assert intro_path.is_file() and outro_path.is_file()
    for probe in (intro_probe, outro_probe):
        assert probe["video"] == {
            "codec": "h264", "width": 1280, "height": 720,
            "fps": 30.0, "pix_fmt": "yuv420p",
        }
        assert probe["audio"] == {"codec": "aac", "sample_rate": 48000, "channels": 2}
        assert abs(probe["duration_ms"] - 1500) <= 34


def test_compose_embedded_clips_preserves_order_audio_and_manifest(tmp_path: Path) -> None:
    composer = QuizPilotComposer(fps=30)
    clips = []
    for item_id in ("intro", "q001", "q002", "q003", "q004", "q005", "outro"):
        path, _probe = composer.render_title_clip(
            output_path=tmp_path / f"{item_id}.mp4",
            title=item_id.upper(),
            subtitle="Pilot fixture",
            duration_ms=500,
            intro=item_id != "outro",
        )
        clips.append((item_id, path))

    result = composer.compose_embedded_clips(
        clips, tmp_path / "final.mp4", manifest_path=tmp_path / "pilot-manifest.json"
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert result.output_path.is_file()
    assert [item["item_id"] for item in manifest["items"]] == [
        "intro", "q001", "q002", "q003", "q004", "q005", "outro"
    ]
    assert manifest["question_ids"] == ["q001", "q002", "q003", "q004", "q005"]
    assert manifest["video"] == {
        "codec": "h264", "width": 1280, "height": 720,
        "fps": 30.0, "pix_fmt": "yuv420p",
    }
    assert manifest["audio"] == {"codec": "aac", "sample_rate": 48000, "channels": 2}
    assert manifest["duration_ms"] == pytest.approx(3500, abs=34)
    assert len(manifest["sha256"]) == 64


def test_composer_scales_to_intro_thirty_questions_outro(tmp_path: Path) -> None:
    composer = QuizPilotComposer(fps=30)
    question_ids = [f"q{i:03d}" for i in range(1, 31)]
    item_ids = ["intro", *question_ids, "outro"]
    clips = []
    for item_id in item_ids:
        path, _probe = composer.render_title_clip(
            output_path=tmp_path / f"{item_id}.mp4",
            title=item_id.upper(),
            subtitle="Scale fixture",
            duration_ms=100,
            intro=item_id != "outro",
        )
        clips.append((item_id, path))

    result = composer.compose_embedded_clips(
        clips,
        tmp_path / "final-30.mp4",
        manifest_path=tmp_path / "manifest-30.json",
        expected_question_ids=question_ids,
    )
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["question_ids"] == question_ids
    assert [row["item_id"] for row in manifest["items"]] == item_ids

    with pytest.raises(QuizPilotError, match="clip order"):
        composer.compose_embedded_clips(
            clips[:-2] + [clips[-1]],
            tmp_path / "invalid.mp4",
            manifest_path=tmp_path / "invalid.json",
            expected_question_ids=question_ids,
        )
