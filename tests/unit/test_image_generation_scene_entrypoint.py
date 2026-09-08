from pathlib import Path


def test_image_service_exposes_selected_scene_entrypoint() -> None:
    source = Path("app/services/image_generation.py").read_text(encoding="utf-8-sig")
    assert "async def generate_scene(" in source
    assert "SceneRepo.get(session, project_id, scene_id)" in source
    assert "await self._process_scene(" in source
