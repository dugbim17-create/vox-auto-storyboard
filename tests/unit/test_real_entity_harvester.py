"""Unit tests for RealEntityHarvester crawling and fallback mechanics."""

from __future__ import annotations

from pathlib import Path
import pytest
from PIL import Image

from app.services.real_entity_harvester import RealEntityHarvester


def test_real_entity_keyword_detection() -> None:
    assert RealEntityHarvester.is_real_entity_phrase("Bùi Xuân Huấn livestream bán nước hoa") is True
    assert RealEntityHarvester.is_real_entity_phrase("bà Trương Mỹ Lan rút ruột SCB") is True
    assert RealEntityHarvester.is_real_entity_phrase("Một người đàn ông vô danh đi qua đường") is False


def test_real_entity_offline_fallback(tmp_path: Path) -> None:
    harvester = RealEntityHarvester(cache_dir=tmp_path)
    urls = harvester.search_real_images("non_existent_random_key_12345_xyz")
    assert isinstance(urls, list)
