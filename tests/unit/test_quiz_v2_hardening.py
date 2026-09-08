"""Offline regression gates for the real custom-quiz runtime."""
import asyncio

import pytest


def test_asset_resolution_never_spends_without_explicit_permission(tmp_path, monkeypatch):
    from app.services import quiz_asset_resolver as resolver

    calls = []

    async def generate(*args, **kwargs):
        calls.append(args)
        raise RuntimeError("provider was called")

    monkeypatch.setattr(resolver, "generate_ai_image_asset", generate)
    questions = [{"id": "q1", "question": "Chọn A", "choices": [
        {"id": "A", "text": "Một"}, {"id": "B", "text": "Hai"}],
        "correct_id": "A", "reveal_image_prompt": "One red circle"}]
    with pytest.raises(RuntimeError):
        asyncio.run(resolver.resolve_quiz_assets(questions, tmp_path))
    assert calls == [], "Unapproved image generation must never reach the provider"


def test_production_requires_review_of_exact_content_and_asset_bytes(tmp_path):
    from PIL import Image
    from app.services import quiz_v2_runtime as runtime

    image = tmp_path / "scene.png"
    Image.new("RGB", (32, 32), "red").save(image)
    document = {"engine_v2": True, "questions": [{
        "id": "q1", "question": "Hình màu gì?", "choices": [
            {"id": "A", "text": "Đỏ"}, {"id": "B", "text": "Xanh"}],
        "correct_id": "A", "reveal_image_path": str(image)}]}
    with pytest.raises(ValueError, match="review"):
        runtime.require_review(document)
    reviewed = runtime.approve_document(document)
    runtime.require_review(reviewed)
    image.write_bytes(image.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="review"):
        runtime.require_review(reviewed)


def test_v2_draft_roundtrip_preserves_voice_and_questions(tmp_path):
    from app.services import quiz_v2_runtime as runtime
    document = {"engine_v2": True, "language": "vi", "settings": {
        "piper_voice": "manh_dung", "piper_speed": 1.2}, "questions": [{
        "id": "q1", "question": "Một cộng một?", "choices": [
            {"id": "A", "text": "Hai"}, {"id": "B", "text": "Ba"}],
        "correct_id": "A"}]}
    path = runtime.save_document(document, tmp_path)
    assert runtime.load_document(path) == document


def test_ui_draft_not_approved_and_settings_roundtrip(tmp_path):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from app.ui_qt.main_window import VoxStudioWindow
    from app.gui_qt import VoxQtApp
    app = QApplication.instance() or QApplication([])
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    document = {"engine_v2": True, "language": "vi", "questions": [{
        "id": "q1", "question": "Một cộng một?", "choices": [
            {"id": "A", "text": "Hai"}, {"id": "B", "text": "Ba"}],
        "correct_id": "A"}]}
    try:
        controller.quiz_document = document
        window.set_quiz_document(document)
        assert window.approve_quiz_button.isEnabled()
        assert not window.render_quiz_button.isEnabled()
        window.quiz_output_dir.setText(str(tmp_path))
        window.quiz_voice_combo.setCurrentText("manh_dung")
        window.quiz_speed_spin.setValue(1.2)
        saved = controller._save_quiz_draft_sync()
        assert saved["questions"] == document["questions"]
        assert saved["settings"]["piper_speed"] == 1.2
        controller._load_quiz()
        assert controller.quiz_document == saved
    finally:
        window.close()


def test_controller_rejects_unreviewed_pilot_before_tts(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from types import SimpleNamespace
    from app.gui_qt import VoxQtApp
    from app.services.quiz_engine_v2 import QuizVideoEngineV2
    def forbidden(*args, **kwargs):
        pytest.fail("Unreviewed images reached renderer")
    monkeypatch.setattr(QuizVideoEngineV2, "render_quiz_video", forbidden)
    questions = json.loads(Path("output/quiz-hardening-live/20260907_225940/resolved_questions.json").read_text(encoding="utf-8"))
    controller = SimpleNamespace(quiz_document={"engine_v2": True, "questions": questions})
    with pytest.raises(ValueError, match="review"):
        VoxQtApp._render_quiz_sync(controller, str(tmp_path))


def test_voice_cache_changes_on_voice_speed_and_model_and_rejects_corruption(tmp_path, monkeypatch):
    import wave
    from pathlib import Path
    from app.services import quiz_engine_v2 as module
    models = tmp_path / "models"
    models.mkdir()
    for name in ["one", "two"]:
        (models / f"{name}.onnx").write_bytes(b"test model identity")
    opt = module.QuizRenderOptions(tts_engine="piper", piper_model_dir=models,
                                  piper_voice="one", language="vi")
    engine = module.QuizVideoEngineV2(opt)
    calls = []
    class Process:
        returncode = 0
        def __init__(self, cmd, **kwargs):
            self.path = Path(cmd[cmd.index("--output_file") + 1])
        def communicate(self, **kwargs):
            calls.append(self.path)
            with wave.open(str(self.path), "wb") as output:
                output.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
                output.writeframes(b"\x01\x00" * 2205)
            return "", ""
    monkeypatch.setattr(module.subprocess, "Popen", Process)
    units = [{"id": "q1", "question": "Một?", "voice_a": "Hai."}]
    cache = tmp_path / "cache"
    cache.mkdir()
    first = engine._synthesize_voice_tracks(units, cache)
    again = engine._synthesize_voice_tracks(units, cache)
    assert first == again and len(calls) == 4
    opt.piper_voice = "two"
    second = engine._synthesize_voice_tracks(units, cache)
    assert second != first, "Selected voice must invalidate audio"
    opt.piper_speed = 1.5
    third = engine._synthesize_voice_tracks(units, cache)
    assert third != second
    (models / "two.onnx").write_bytes(b"changed model")
    fourth = engine._synthesize_voice_tracks(units, cache)
    assert fourth != third
    fourth["q1_q"].write_bytes(b"corrupt")
    engine._synthesize_voice_tracks(units, cache)
    assert engine.tts_calls == 1
    assert engine.tts_cache_hits == 3


def test_missing_selected_piper_model_never_falls_back(tmp_path):
    from app.services.quiz_engine_v2 import QuizRenderOptions, QuizVideoEngineV2
    (tmp_path / "other.onnx").write_bytes(b"unrelated")
    engine = QuizVideoEngineV2(QuizRenderOptions(tts_engine="piper", piper_voice="missing", piper_model_dir=tmp_path))
    with pytest.raises(RuntimeError, match="model"):
        engine._synthesize_voice_tracks([], tmp_path)


def test_declining_visual_review_does_not_approve(tmp_path, monkeypatch):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QDialog
    from app.gui_qt import VoxQtApp
    from app.ui_qt.main_window import VoxStudioWindow
    app = QApplication.instance() or QApplication([])
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    document = {"engine_v2": True, "questions": [{"id": "q1", "question": "Một cộng một?",
        "choices": [{"id": "A", "text": "Hai"}, {"id": "B", "text": "Ba"}], "correct_id": "A"}]}
    try:
        controller.quiz_document = document
        window.set_quiz_document(document)
        window.quiz_output_dir.setText(str(tmp_path))
        monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
        controller._approve_quiz()
        assert controller.quiz_document.get("approval", {}).get("status") != "approved"
    finally:
        window.close()


def test_asset_cache_separates_models(tmp_path, monkeypatch):
    from PIL import Image
    from app.services import quiz_asset_resolver as resolver
    calls = []
    async def generate(prompt, path, model):
        calls.append(model)
        Image.new("RGB", (768, 512), "red").save(path)
    monkeypatch.setattr(resolver, "generate_ai_image_asset", generate)
    questions = [{"id": "q1", "question": "Chọn A", "choices": [
        {"id": "A", "text": "Đỏ"}, {"id": "B", "text": "Xanh"}],
        "correct_id": "A", "reveal_image_prompt": "Red circle"}]
    first = asyncio.run(resolver.resolve_quiz_assets(questions, tmp_path, "model-one", allow_generation=True))
    second = asyncio.run(resolver.resolve_quiz_assets(questions, tmp_path, "model-two", allow_generation=True))
    assert calls == ["model-one", "model-two"]
    assert first[0]["reveal_image_path"] != second[0]["reveal_image_path"]


def test_vertical_riddle_preserves_all_four_colors(tmp_path):
    from PIL import Image, ImageDraw
    import numpy as np
    from app.services.quiz_engine_v2 import QuizRenderOptions, QuizVideoEngineV2
    image = Image.new("RGB", (1920, 940), "black")
    draw = ImageDraw.Draw(image)
    colors = [(220, 30, 30), (30, 70, 220), (30, 200, 70), (220, 200, 30)]
    for i, color in enumerate(colors):
        draw.rectangle((i * 480 + 100, 330, i * 480 + 380, 610), fill=color)
    path = tmp_path / "scene.png"
    image.save(path)
    engine = QuizVideoEngineV2(QuizRenderOptions(aspect_ratio="9:16"))
    canvas = Image.new("RGBA", (1080, 1920), "black")
    event = {"idx": 1, "data": {"scene_image": str(path), "question": "Ô xanh lá?", "options": ["1", "2", "3", "4"], "correct_option": "3"}, "cd_start": 2, "cd_dur": 1, "rev_start": 3}
    frame = engine._render_riddle_mystra(canvas, ImageDraw.Draw(canvas), 1, event, 0, False, False)
    pixels = np.asarray(frame)[:, :, :3]
    for color in colors:
        assert np.count_nonzero(np.all(pixels == color, axis=2)) > 1000, f"Cropped clue color {color}"
