from __future__ import annotations

import json
import hashlib
from pathlib import Path
from types import SimpleNamespace

from PIL import Image


def test_render_options_accept_persisted_visual_style_snapshot() -> None:
    from app.services.quiz_engine_v2 import QuizRenderOptions
    from app.services.quiz_style_packs import resolve_style_snapshot

    snapshot = resolve_style_snapshot("clear-knowledge", locale="vi-VN", motion="low")
    options = QuizRenderOptions(visual_style=snapshot)
    assert options.visual_style == snapshot


def test_controller_passes_document_snapshot_to_options_without_provider(tmp_path, monkeypatch) -> None:
    from app.gui_qt import VoxQtApp
    from app.services.quiz_style_packs import resolve_style_snapshot
    from app.services.quiz_v2_runtime import approve_document

    image_path = tmp_path / "scene.png"
    Image.new("RGB", (64, 64), "red").save(image_path)
    document = {
        "engine_v2": True,
        "language": "vi-VN",
        "title": "Style wiring",
        "visual_style": resolve_style_snapshot("clear-knowledge", locale="vi-VN", motion="low"),
        "questions": [{
            "id": "q1",
            "question": "Màu gì?",
            "choices": [{"id": "A", "text": "Đỏ"}, {"id": "B", "text": "Xanh"}],
            "correct_id": "A",
            "reveal_image_path": str(image_path),
            "reveal_image_rights": {
                "kind": "licensed", "license": "OWNED", "reviewed": True,
                "author": "test fixture", "source_url": image_path.as_uri(),
                "evidence_url": Path(__file__).resolve().as_uri(),
                "license_url": "urn:quiz:test-fixture-owned", "changes": "none",
                "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            },
        }],
    }
    from app.services.quiz_source_review import register_review
    unit = document['questions'][0]
    unit['reveal_image_rights'] = register_review(image_path, unit['reveal_image_rights'], Path(__file__))
    approved = approve_document(document)
    seen = {}

    class FakeEngine:
        def __init__(self, options):
            seen["style"] = options.visual_style
            seen["channel_profile"] = options.channel_profile
            self.tts_calls = 0
            self.tts_cache_hits = 0

        def render_quiz_video(self, questions, title):
            seen["questions"] = questions
            seen["title"] = title
            output = tmp_path / "rendered.mp4"
            output.write_bytes(b"offline-render-sentinel")
            return output

        def _probe_dur(self, path):
            return 1.0

    monkeypatch.setattr("app.services.quiz_engine_v2.QuizVideoEngineV2", FakeEngine)
    controller = SimpleNamespace(quiz_document=approved)
    result = VoxQtApp._render_quiz_sync(controller, str(tmp_path), "16:9", approved)

    assert seen["style"] == approved["visual_style"]
    assert seen["style"] is not approved["visual_style"]
    assert result["provider_calls"] == 0
    manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
    assert manifest["visual_style"] == approved["visual_style"]


def test_legacy_render_options_without_style_keep_legacy_default() -> None:
    from app.services.quiz_engine_v2 import QuizRenderOptions

    options = QuizRenderOptions()
    assert options.visual_style is None
