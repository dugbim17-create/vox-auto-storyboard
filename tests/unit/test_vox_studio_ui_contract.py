"""Contract tests for the Vox Studio shell and first API slice."""

from fastapi.testclient import TestClient

from app.api.web_app import app


def test_vox_shell_has_six_views_and_real_primary_hooks() -> None:
    body = TestClient(app).get("/").text
    assert 'id="view-projects"' in body
    assert 'id="view-script"' in body
    assert 'id="view-visuals"' in body
    assert 'id="view-style"' in body
    assert 'id="view-voice"' in body
    assert 'id="view-caption"' in body
    assert 'id="view-render"' in body
    assert "function saveScript()" in body
    assert "function planProject()" in body
    assert "function generateImage()" in body
    assert "function generateVoice()" in body
    assert "function generateCaption()" in body
    assert "function renderProject()" in body
    assert "aria-live=\"polite\"" in body


def test_vox_catalogs_contract() -> None:
    response = TestClient(app).get("/api/vox/catalogs")
    assert response.status_code == 200
    data = response.json()
    assert {item["id"] for item in data["styles"]} >= {
        "editorial_collage", "documentary", "minimal_motion"
    }
    assert "9:16" in data["aspect_ratios"]


def test_vox_create_project_and_script_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path / "projects"))
    from app import settings

    settings._settings = None
    client = TestClient(app)
    created = client.post(
        "/api/vox/projects",
        json={"title": "Test Vox", "script": "First scene.\nSecond scene."},
    )
    assert created.status_code == 200
    project_id = created.json()["project_id"]

    saved = client.put(
        f"/api/vox/projects/{project_id}/script",
        json={"title": "Updated Vox", "script": "Updated script."},
    )
    assert saved.status_code == 200
    loaded = client.get(f"/api/vox/projects/{project_id}/script")
    assert loaded.status_code == 200
    assert loaded.json()["script"] == "Updated script."


def test_vox_media_rejects_path_traversal(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path / "projects"))
    from app import settings

    settings._settings = None
    response = TestClient(app).get("/api/vox/media/p1/final/..%2F..%2Fsecret.txt")
    assert response.status_code in {400, 404}


def test_legacy_dashboard_contract_remains_available() -> None:
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "Vox Studio" in response.text
    assert "Tạo dự án mới" in response.text
    assert "Render" in response.text


def test_vox_project_routes_are_registered() -> None:
    paths = {route.path for route in app.routes}
    assert "/api/vox/projects" in paths
    assert "/api/vox/projects/{project_id}/script" in paths
    assert "/api/vox/projects/{project_id}/plan" in paths
    assert "/api/vox/projects/{project_id}/artifacts" in paths
    assert "/api/vox/media/{project_id}/{artifact_kind}/{name}" in paths
    assert "/api/vox/projects/{project_id}/voice" in paths
    assert "/api/vox/projects/{project_id}/captions" in paths
    assert "/api/vox/projects/{project_id}/render" in paths
    assert "/api/vox/voices" in paths
