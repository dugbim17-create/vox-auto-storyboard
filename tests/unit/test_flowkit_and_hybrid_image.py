"""Unit tests for FlowKit Batch Prompt Export and CLIProxy Image Fallback."""

from __future__ import annotations

from pathlib import Path

from app.providers.image.flowkit import export_google_flow_batch_prompts
from app.providers.image.cliproxy_image import CliproxyImageProvider


def test_export_google_flow_batch_prompts_writes_formatted_file(tmp_path: Path) -> None:
    prompts = [
        "vintage 1911 Nha Rong port in Saigon",
        "vintage French registration certificate",
        "vintage world navigation map",
    ]
    out_file = tmp_path / "batch_prompts.txt"
    result = export_google_flow_batch_prompts(prompts, out_file)

    assert result.is_file()
    content = result.read_text(encoding="utf-8")
    assert "GOOGLE FLOW BATCH PROMPTS" in content
    assert "Prompt 01: vintage 1911 Nha Rong port in Saigon" in content
    assert "Prompt 03: vintage world navigation map" in content


def test_cliproxy_image_provider_initializes_with_fallback_models() -> None:
    provider = CliproxyImageProvider(
        base_url="http://127.0.0.1:8317/v1",
        model="gpt-image-2",
        fallback_models=["gpt-image-2", "gpt-image-1.5"],
    )
    assert provider.model == "gpt-image-2"
    assert "gpt-image-1.5" in provider.fallback_models


def test_cliproxy_image_provider_defaults_use_grok_as_last_resort_only() -> None:
    # 2026-09-12: grok-imagine-image is fallback-only (never the default model),
    # tried last after the usual gpt-image pair.
    provider = CliproxyImageProvider(base_url="http://127.0.0.1:8317/v1")
    assert provider.model == "gpt-image-2"
    assert provider.model != "grok-imagine-image"
    assert provider.fallback_models[-1] == "grok-imagine-image"
