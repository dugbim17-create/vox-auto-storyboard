"""Derive artifact freshness from current lineage hashes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Freshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"
    MISSING = "missing"


@dataclass(frozen=True)
class FreshnessResult:
    state: Freshness
    reason: str


def classify_image_asset(
    asset: Any | None,
    *,
    applied_visual_hash: str,
) -> FreshnessResult:
    if asset is None:
        return FreshnessResult(Freshness.MISSING, "asset is missing")
    asset_hash = str(getattr(asset, "visual_style_hash", "") or "")
    if not asset_hash:
        return FreshnessResult(Freshness.UNKNOWN, "legacy asset has no visual hash")
    if asset_hash == applied_visual_hash:
        return FreshnessResult(Freshness.FRESH, "visual hash matches")
    return FreshnessResult(
        Freshness.STALE,
        f"visual hash differs: asset={asset_hash} applied={applied_visual_hash}",
    )


def summarize_assets(
    assets: list[Any | None],
    *,
    applied_visual_hash: str,
) -> dict[str, int]:
    counts = {state.value: 0 for state in Freshness}
    for asset in assets:
        result = classify_image_asset(asset, applied_visual_hash=applied_visual_hash)
        counts[result.state.value] += 1
    return counts


__all__ = ["Freshness", "FreshnessResult", "classify_image_asset", "summarize_assets"]
