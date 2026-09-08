from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.providers.base import ImageGenerationResult, TTSRequest
from app.providers.image.cliproxy_image import CliproxyImageProvider
from app.providers.tts.omnivoice import OmniVoiceError, OmniVoiceProvider
from app.services.image_generation import ImageGenerationService
from app.services.scene_audio_mux import SceneAudioMuxer
from app.services.subtitle_generator import allocate_timing
from app.storage.asset_store import AssetStore


def test_cliproxy_image_base_with_v1_does_not_duplicate_route() -> None:
    provider = CliproxyImageProvider(base_url="http://127.0.0.1:8317/v1")
    try:
        url = provider._client.build_request(  # noqa: SLF001
            "POST", f"{provider._route_prefix}images/generations"  # noqa: SLF001
        ).url
        assert str(url) == "http://127.0.0.1:8317/v1/images/generations"
    finally:
        asyncio.run(provider.aclose())


def test_subtitle_allocation_never_exceeds_requested_window() -> None:
    entries = allocate_timing([f"chunk {index}" for index in range(10)], 1_000, 120)
    assert entries
    assert entries[-1].end_ms <= 1_120


def test_scene_audio_mux_pad_audio_command_is_bounded_by_video_duration(tmp_path: Path) -> None:
    video = tmp_path / "scene.mp4"
    audio = tmp_path / "voice.wav"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")
    captured: list[str] = []

    def runner(command, **_kwargs):
        captured.extend(command)
        Path(command[-1]).write_bytes(b"muxed")
        return SimpleNamespace(returncode=0, stderr="")

    muxer = SceneAudioMuxer(runner=runner)
    muxer._probe_duration_ms = lambda _path: 1_000  # type: ignore[method-assign]  # noqa: SLF001
    muxer._probe = lambda _path, **_kwargs: SimpleNamespace(  # type: ignore[method-assign]  # noqa: SLF001
        video_duration_ms=1_000,
        audio_duration_ms=1_000,
        has_audio=True,
        audio_codec="aac",
        fps=30.0,
        verify=lambda **_kwargs: None,
    )
    muxer.mux(video, audio, tmp_path / "out.mp4", pad_audio=True)

    assert "apad" in " ".join(captured)
    assert "-t" in captured or "-shortest" in captured


def test_omnivoice_rejects_ok_response_that_contains_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={"status": "ok", "error": "synthesis failed", "wav_path": "", "duration_ms": 0},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OmniVoiceProvider(base_url="http://voice.test", httpx_client=client)
    try:
        with pytest.raises(OmniVoiceError):
            asyncio.run(
                provider.synthesize(
                    TTSRequest(
                        segment_id="scene_001",
                        text="xin chào",
                        output_path="voice.wav",
                        language="vi",
                    )
                )
            )
    finally:
        asyncio.run(client.aclose())


def test_image_fallback_invokes_fallback_provider(tmp_path: Path) -> None:
    class Primary:
        calls = 0

        async def generate(self, _request):
            self.calls += 1
            raise httpx.ConnectError("transient")

    class Fallback:
        calls = 0
        provider_name = "fallback"

        async def generate(self, request):
            self.calls += 1
            path = Path(request.output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            from PIL import Image

            Image.new("RGB", (8, 8), "red").save(path)
            return ImageGenerationResult(
                path=str(path),
                provider="fallback",
                width=8,
                height=8,
                prompt_hash="p",
                sha256="s",
            )

    primary = Primary()
    fallback = Fallback()
    service = ImageGenerationService(
        primary,
        fallback_provider=fallback,
        provider_name="cliproxy_image",
        project_root=tmp_path,
    )
    plan = SimpleNamespace(
        role="composite",
        prompt="frame",
        negative_constraints=(),
        reference_images=(),
        aspect_ratio="16:9",
    )
    scene = SimpleNamespace(scene_id="scene_001")
    result = asyncio.run(
        service._generate_job(  # noqa: SLF001
            project_id="project",
            scene=scene,
            plan=plan,
            store=AssetStore(tmp_path),
            provider_name="cliproxy_image",
        )
    )
    assert primary.calls == 1
    assert fallback.calls == 1
    assert result.provider == "fallback"
