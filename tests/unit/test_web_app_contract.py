"""Direct API contract tests for the web entrypoint."""

from fastapi.testclient import TestClient

from app.api.web_app import _jobs, app


def test_health_contract() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_run_and_cancel_contract(monkeypatch) -> None:
    async def fake_pipeline(job_id: str, script_text: str, opts: dict) -> None:
        return None

    monkeypatch.setattr("app.api.web_app._run_pipeline", fake_pipeline)
    client = TestClient(app)
    response = client.post("/api/run", json={"script": "hello", "project_id": "p1"})
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert _jobs[job_id]["project_id"] == "p1"

    cancel = client.post("/projects/p1/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelling"


def test_cli_contract_exposes_plan_aliases_and_run_options() -> None:
    from app.cli import _build_parser

    parser = _build_parser()
    args = parser.parse_args(
        [
            "run",
            "--script",
            "input.txt",
            "--image-provider",
            "antigravity_image",
            "--motion-tier",
            "local",
            "--voice-profile",
            "voice_custom",
        ]
    )
    assert args.image_provider == "antigravity_image"
    assert args.motion_tier == "local"
    assert args.voice_profile == "voice_custom"

    assert parser.parse_args(["render-scenes", "--project", "p"]).command == "render-scenes"
    assert parser.parse_args(["render-final", "--project", "p"]).command == "render-final"


def test_dashboard_exposes_progress_cancel_and_accessibility_contract() -> None:
    response = TestClient(app).get("/")
    body = response.text
    assert response.status_code == 200
    assert 'id="cancel-render"' in body
    assert 'id="render-progress"' in body
    assert 'data-render-stage="compose"' in body
    assert 'aria-live="polite"' in body
