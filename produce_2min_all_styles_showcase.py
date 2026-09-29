"""Multi-Style Showcase Documentary Producer (Resumable Edition).

Renders remaining chapters and concats into the master 2-minute showcase video.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from pathlib import Path
from typing import Any

from app.services.vox_cinematic_engine import CinematicTheme, VoxCinematicEngine

logger = logging.getLogger(__name__)

CHAPTER_SCRIPTS = [
    # 1. Archival Vintage History (0:00 - 0:18)
    (
        "Archival_Vintage_1911",
        "archival_vintage_history",
        (
            "Ngày 5 tháng 6 năm 1911, tại bến cảng Nhà Rồng Sài Gòn, người thanh niên yêu nước Nguyễn Tất Thành với tên gọi Văn Ba "
            "đã bước chân lên con tàu Đô đốc Latouche-Tréville, bắt đầu cuộc hành trình lịch sử bôn ba qua ba đại dương để tìm kiếm con đường giải phóng cho dân tộc."
        ),
        CinematicTheme(
            surface_type="corkboard",
            accent_color=(255, 215, 0),
            secondary_color=(200, 30, 30),
            tag_prefix="TƯ LIỆU BẢO TÀNG LỊCH SỬ",
        ),
    ),
    # 2. Tactical Radar Military (0:18 - 0:36)
    (
        "Tactical_Radar_1954",
        "tactical_investigation",
        (
            "Năm 1954, thung lũng Điện Biên Phủ trở thành điểm hẹn lịch sử khi Đại tướng Võ Nguyên Giáp chỉ huy quân đội kéo pháo qua đèo cao, "
            "thiết lập thế trận vòng vây thép và bắn hạ từng chiếc máy bay tiếp tế của tập đoàn cứ điểm Pháp."
        ),
        CinematicTheme(
            surface_type="dark_dossier",
            accent_color=(50, 240, 255),
            secondary_color=(255, 60, 60),
            tag_prefix="HỒ SƠ TÁC CHIẾN QUÂN SỰ",
        ),
    ),
    # 3. Johnny Harris Geopolitics (0:36 - 0:54)
    (
        "Johnny_Harris_MH370",
        "johnny_harris_geopolitics",
        (
            "Đêm ngày 8 tháng 3 năm 2014, chiếc Boeing 777 mang số hiệu MH370 đột ngột bẻ lái gắt 180 độ, bay qua eo biển Malacca "
            "rồi biến mất hoàn toàn vào vùng biển sâu thẳm của Nam Ấn Độ Dương, để lại bí ẩn hàng không lớn nhất thế kỷ 21."
        ),
        CinematicTheme(
            surface_type="corkboard",
            accent_color=(255, 200, 50),
            secondary_color=(230, 40, 40),
            tag_prefix="BẢN ĐỒ ĐỊA CHÍNH TRỊ QUỐC TẾ",
        ),
    ),
    # 4. Magnates Media Billionaires (0:54 - 1:12)
    (
        "Magnates_Media_SCB",
        "magnates_media_billionaires",
        (
            "304 nghìn tỷ đồng, tương đương hơn 12 tỷ đô la Mỹ. Đây là quy mô thiệt hại khổng lồ trong đại án Trương Mỹ Lan và Vạn Thịnh Phát, "
            "khi thao túng hơn 91% cổ phần Ngân hàng SCB để lập hàng nghìn hồ sơ vay khống thâu tóm các bất động sản đắt đỏ bậc nhất Sài Gòn."
        ),
        CinematicTheme(
            surface_type="dark_dossier",
            accent_color=(255, 215, 0),
            secondary_color=(50, 240, 100),
            tag_prefix="HỒ SƠ ĐẠI ÁN TÀI PHIỆT",
        ),
    ),
    # 5. True Crime Police Dossier (1:12 - 1:30)
    (
        "True_Crime_KhaBanh",
        "true_crime_dossier",
        (
            "Năm 2019, hiện tượng giang hồ mạng Khá Bảnh bùng nổ khắp mạng xã hội với những video múa quạt hàng triệu lượt xem, "
            "trước khi bị Công an tỉnh Bắc Ninh bắt giữ và tuyên phạt 10 năm tù vì hành vi đánh bạc và tổ chức đánh bạc hàng trăm triệu đồng."
        ),
        CinematicTheme(
            surface_type="corkboard",
            accent_color=(255, 60, 60),
            secondary_color=(255, 220, 0),
            tag_prefix="HỒ SƠ ĐIỀU TRA HÌNH SỰ",
        ),
    ),
    # 6. Cyberpunk Tech Breakdown (1:30 - 1:48)
    (
        "Cyberpunk_Tech_AI",
        "cyberpunk_tech_breakdown",
        (
            "Bước sang năm 2026, cuộc đua trí tuệ nhân tạo và siêu chip bán dẫn của Nvidia, OpenAI và Google bùng nổ nghìn tỷ đô la, "
            "định hình lại toàn bộ nền kinh tế toàn cầu và thay đổi hoàn toàn cách con người làm việc và sáng tạo."
        ),
        CinematicTheme(
            surface_type="dark_dossier",
            accent_color=(0, 255, 200),
            secondary_color=(255, 0, 128),
            tag_prefix="BẢN VẼ CÔNG NGHỆ TƯƠNG LAI",
        ),
    ),
    # 7. Vox Classic Editorial Collage (1:48 - 2:06)
    (
        "Vox_Classic_VietnamFuture",
        "editorial_collage",
        (
            "Từ những trang sử hào hùng đến kỷ nguyên công nghệ số, bài học lớn nhất luôn là khả năng thích ứng và bản lĩnh vươn lên mạnh mẽ của con người Việt Nam trên trường quốc tế."
        ),
        CinematicTheme(
            surface_type="corkboard",
            accent_color=(255, 220, 20),
            secondary_color=(240, 40, 40),
            tag_prefix="VOX STUDIO // KẾT LUẬN",
        ),
    ),
]


async def resume_and_render_all() -> Path:
    master_dir = Path("projects/prj_1787139301_all_vox_styles_2min_master")
    master_final = master_dir / "final"
    master_final.mkdir(parents=True, exist_ok=True)
    chap_base = master_dir / "chapters"
    chap_base.mkdir(parents=True, exist_ok=True)

    engine = VoxCinematicEngine(output_base_dir=chap_base)
    chapter_mp4s: list[Path] = []

    # Map existing completed chapters
    for idx, (title, style_id, script, theme) in enumerate(CHAPTER_SCRIPTS, 1):
        # Check if already rendered
        existing_mp4 = None
        for sub in chap_base.iterdir():
            if sub.is_dir() and f"_{idx:02d}_" in sub.name:
                cand = sub / "final" / "final_vox_video.mp4"
                if cand.is_file() and cand.stat().st_size > 100000:
                    existing_mp4 = cand
                    break

        if existing_mp4:
            print(f"✓ Found existing Chapter {idx}: {existing_mp4.name} ({existing_mp4.stat().st_size / 1024 / 1024:.1f} MB)")
            chapter_mp4s.append(existing_mp4)
        else:
            print(f"\n>>> Rendering Chapter {idx}/7: [{style_id.upper()}] - {title}...")
            res = await engine.produce_master_video(
                script,
                project_title=f"{idx:02d}_{title}",
                theme=theme,
            )
            print(f"✓ Chapter {idx} completed: {res.video_path.name}")
            chapter_mp4s.append(res.video_path)

    # Concat
    print("\n>>> Concatenating all 7 chapters into 2-minute Master MP4...")
    concat_list = master_final / "chapters_concat.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for mp4 in chapter_mp4s:
            f.write(f"file '{mp4.resolve().as_posix()}'\n")

    final_master_mp4 = master_final / "vox_all_styles_2min_showcase_master.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(final_master_mp4),
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    print(f"\n=== [2-MINUTE MASTERPIECE SUCCESS] -> {final_master_mp4.resolve()} ===")
    return final_master_mp4


if __name__ == "__main__":
    asyncio.run(resume_and_render_all())
