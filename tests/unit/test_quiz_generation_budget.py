import pytest


def test_budget_survives_restart_and_blocks_unknown_submission(tmp_path):
    from app.services.quiz_generation_budget import GenerationBudget
    budget = GenerationBudget(tmp_path, limit=6)
    ticket = budget.reserve('asset-one')
    with pytest.raises(RuntimeError, match='unknown'):
        GenerationBudget(tmp_path, limit=6).reserve('asset-one')
    budget.complete(ticket)
    for i in range(5):
        ticket = GenerationBudget(tmp_path, limit=6).reserve(f'asset-{i+2}')
        budget.complete(ticket)
    with pytest.raises(RuntimeError, match='budget'):
        GenerationBudget(tmp_path, limit=6).reserve('seventh')


@pytest.mark.asyncio
async def test_quiz_image_preserves_prompt_and_disables_fallback(tmp_path, monkeypatch):
    from PIL import Image
    from app.services import quiz_asset_resolver as resolver
    seen = {}
    class Provider:
        def __init__(self, **kwargs):
            seen.update(kwargs)
        async def generate(self, request):
            seen['prompt'] = request.prompt
            # Valid provider output under the new geometry/resolution contract.
            Image.new('RGB', (768, 512), 'red').save(request.output_path)
        async def aclose(self):
            pass
    monkeypatch.setattr(resolver, 'CliproxyImageProvider', Provider, raising=False)
    await resolver.generate_quiz_image('A museum with four doors', tmp_path / 'scene.png', model='gpt-image-2')
    assert seen['fallback_models'] == ['gpt-image-2']
    assert seen['prompt'] == 'A museum with four doors'


def test_ui_generation_cancel_submits_nothing(monkeypatch):
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication, QMessageBox
    from app.gui_qt import VoxQtApp
    from app.ui_qt.main_window import VoxStudioWindow
    app = QApplication.instance() or QApplication([])
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    controller.quiz_document = {'engine_v2': True, 'questions': []}
    calls = []
    monkeypatch.setattr(controller.bridge, 'run', lambda *args: calls.append(args))
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    try:
        window.quiz_generate_assets_button.click()
        assert calls == []
    finally:
        window.close()


def test_vertical_title_stays_inside_header_safe_area():
    from PIL import Image, ImageDraw
    from app.services.quiz_engine_v2 import QuizVideoEngineV2, QuizRenderOptions
    engine = QuizVideoEngineV2(QuizRenderOptions(aspect_ratio='9:16'))
    image = Image.new('RGBA', (1080, 1920))
    draw = ImageDraw.Draw(image)
    captured = []
    original = draw.text
    title = 'BÌNH NÀO CÓ SỐ HOA KHÁC BA BÌNH CÒN LẠI?'
    def record(xy, text, **kwargs):
        if text == title:
            captured.append(draw.textbbox(xy, text, font=kwargs['font'], anchor=kwargs.get('anchor')))
        return original(xy, text, **kwargs)
    draw.text = record
    event = {'idx':1, 'data':{'question':title,'cards':[]},'cd_start':2,'cd_dur':5,'rev_start':7}
    engine._render_riddle_mystra(image,draw,1,event,0,False,False)
    assert captured
    assert all(box[0] >= 160 and box[2] <= 1050 for box in captured)
