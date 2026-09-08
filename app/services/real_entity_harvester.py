"""Real-World Entity Media Harvester & Auto-Crawler Service (High-Precision Edition).

Borrowed and adapted from Snap-Tool architecture (D:/ALL AI/TestProjects/Snap-Tool):
1. Detects local/national public figures, viral personalities, cultural events, and specific brands.
2. Extracts clean core search keywords (e.g. "Khá Bảnh Ngô Bá Khá", "Bùi Xuân Huấn", "Trương Mỹ Lan").
3. Automatically crawls high-resolution real-world documentary archival photos via Bing Image Async Engine.
4. Automatically upgrades quality, removes background via Rembg, and crafts 3D tactile paper stickers.
5. Seamlessly blends with AI-generated assets (AI creates evidence documents/money, Crawler provides exact faces).
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image

from app.services.paper_craft import PaperCraftService, PaperCutoutOptions
from app.services.segmentation import RembgBackend

logger = logging.getLogger(__name__)

# Dictionary of specialized target search queries for viral / local figures to guarantee 100% exact real photo
CORE_ENTITY_QUERY_MAP: dict[str, str] = {
    "khá bảnh": "Khá Bảnh Ngô Bá Khá",
    "ngô bá khá": "Khá Bảnh Ngô Bá Khá",
    "múa quạt": "Khá Bảnh múa quạt",
    "huấn hoa hồng": "Huấn Hoa Hồng Bùi Xuân Huấn",
    "bùi xuân huấn": "Huấn Hoa Hồng Bùi Xuân Huấn",
    "trương mỹ lan": "Trương Mỹ Lan chân dung",
    "vạn thịnh phát": "Tập đoàn Vạn Thịnh Phát tòa nhà Times Square Saigon",
    "scb": "Ngân hàng Thương mại Cổ phần Sài Gòn SCB hội sở",
    "nguyễn phương hằng": "Nguyễn Phương Hằng Đại Nam",
    "dũng lò vôi": "Dũng Lò Vôi Huỳnh Uy Dũng",
    "tiến bịp": "Tiến Bịp Nguyễn Thành Long",
    "ngọc trinh": "Ngọc Trinh người mẫu",
    "hồ chí minh": "Chủ tịch Hồ Chí Minh Bác Hồ",
    "nguyễn tất thành": "Nguyễn Tất Thành Bác Hồ",
    "phạm văn phú": "Thiếu tướng Phạm Văn Phú",
    "tướng phú": "Thiếu tướng Phạm Văn Phú",
    "phạm nhật vượng": "Phạm Nhật Vượng Vingroup",
    "donald trump": "Donald Trump portrait",
    "elon musk": "Elon Musk portrait",
}


class RealEntityHarvester:
    """Intelligent crawler that fetches high-res real-world archival portraits & documentary images."""

    def __init__(self, cache_dir: str | Path = "cache/real_entities") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.segmenter = RembgBackend()

    @staticmethod
    def is_real_entity_phrase(phrase: str) -> bool:
        """Check if a phrase contains specific real-world individuals or brands."""
        p_lower = phrase.lower()
        return any(k in p_lower for k in CORE_ENTITY_QUERY_MAP) or bool(
            re.search(r"\b(ông|bà|chủ tịch|đại gia|tổng giám đốc|ca sĩ|diễn viên)\s+[A-ZĐ][a-zà-ỹ]+", phrase)
        )

    @staticmethod
    def extract_search_query(phrase: str) -> str:
        """Extract a laser-targeted search keyword from a long phrase."""
        p_lower = phrase.lower()
        for k, query in CORE_ENTITY_QUERY_MAP.items():
            if k in p_lower:
                return query
        # Fallback: extract title + name
        m = re.search(r"(?:ông|bà|chủ tịch|đại gia|ca sĩ|diễn viên)\s+([A-ZĐ][a-zà-ỹ]+(?:\s+[A-ZĐ][a-zà-ỹ]+){1,3})", phrase)
        if m:
            return m.group(0)
        return phrase[:40]

    def search_real_images(self, query: str, max_results: int = 6) -> list[str]:
        """Crawl real documentary / portrait image URLs using high-speed async image index."""
        # Clean query: if query contains 'logo' or 'tòa nhà' don't append 'chân dung'
        if any(w in query.lower() for w in ("logo", "tòa nhà", "ngân hàng", "tập đoàn", "building")):
            q_suffix = ""
        else:
            q_suffix = " chân dung"

        url = f"https://www.bing.com/images/async?q={urllib.parse.quote(query + q_suffix)}&count=12&first=0&datsrc=I&layout=RowBased&mmasync=1"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        try:
            html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8")
            murls = re.findall(r'murl&quot;:&quot;(http[^&]+)&quot;', html)
            if not murls:
                murls = re.findall(r'\"murl\":\"(http[^\"]+)\"', html)
            return murls[:max_results]
        except Exception as exc:
            logger.warning(f"Real image search failed for '{query}': {exc}")
            return []

    async def harvest_and_craft_sticker(
        self,
        phrase: str,
        output_cutout_path: Path,
        border_width: int = 14,
    ) -> bool:
        """Download real image, isolate subject silhouette, and build 3D torn paper sticker."""
        clean_query = self.extract_search_query(phrase)
        logger.info(f"Targeted real image crawl query: '{clean_query}' (from phrase: '{phrase[:40]}')")

        urls = self.search_real_images(clean_query, max_results=6)
        if not urls:
            return False

        for url in urls:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64)"})
                resp = urllib.request.urlopen(req, timeout=8)
                data = resp.read()
                if len(data) < 10000:
                    continue

                raw_im = Image.open(io.BytesIO(data)).convert("RGBA")
                if raw_im.width < 250 or raw_im.height < 250:
                    continue

                # Run Rembg background removal
                mask = self.segmenter.produce_mask(raw_im)
                mask_arr = np.array(mask)
                fg_ratio = float((mask_arr > 30).mean())
                if fg_ratio < 0.10 or fg_ratio > 0.96:
                    logger.warning(f"Mask integrity failed (kept {fg_ratio*100:.1f}%) for '{clean_query}', skipping candidate...")
                    continue

                clean_im = raw_im.copy()
                clean_im.putalpha(mask)

                # Craft 3D torn cutout sticker
                torn_stk = PaperCraftService.create_torn_cutout(
                    clean_im, PaperCutoutOptions(border_width=border_width, roughness=0.65, shadow=True)
                )
                output_cutout_path.parent.mkdir(parents=True, exist_ok=True)
                torn_stk.save(output_cutout_path)
                logger.info(f"Successfully harvested and crafted REAL FACE sticker for '{clean_query}' -> {output_cutout_path}")
                return True
            except Exception as exc:
                logger.debug(f"Failed crawling candidate {url}: {exc}")
                continue

        return False
