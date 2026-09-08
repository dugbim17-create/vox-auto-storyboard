from __future__ import annotations

from types import SimpleNamespace

from app.services.artifact_freshness import Freshness, classify_image_asset, summarize_assets


def test_matching_visual_hash_is_fresh() -> None:
    asset = SimpleNamespace(visual_style_hash="style-A", path="a.jpg")
    result = classify_image_asset(asset, applied_visual_hash="style-A")
    assert result.state == Freshness.FRESH
    assert result.reason == "visual hash matches"


def test_mismatched_visual_hash_is_stale() -> None:
    asset = SimpleNamespace(visual_style_hash="style-A", path="a.jpg")
    result = classify_image_asset(asset, applied_visual_hash="style-B")
    assert result.state == Freshness.STALE


def test_legacy_asset_without_hash_is_unknown() -> None:
    asset = SimpleNamespace(visual_style_hash=None, path="legacy.jpg")
    result = classify_image_asset(asset, applied_visual_hash="style-B")
    assert result.state == Freshness.UNKNOWN


def test_missing_asset_is_missing() -> None:
    result = classify_image_asset(None, applied_visual_hash="style-B")
    assert result.state == Freshness.MISSING


def test_summary_counts_all_states() -> None:
    assets = [
        SimpleNamespace(visual_style_hash="A", path="a.jpg"),
        SimpleNamespace(visual_style_hash="B", path="b.jpg"),
        SimpleNamespace(visual_style_hash=None, path="legacy.jpg"),
        None,
    ]
    assert summarize_assets(assets, applied_visual_hash="A") == {
        "fresh": 1,
        "stale": 1,
        "unknown": 1,
        "missing": 1,
    }
