"""Dense Temporal Evidence & Diagnostic Metric Generator for Rejected Baseline.

Processes rejected master (106.355s) and 7 chapter MP4s:
- FFprobe detailed stream/format inspection
- Full FFmpeg decode validation
- 0.5-second cadence frame sampling
- Diagnostic pixel difference / motion metric computation
- Contact sheet generation marked REJECTED_PRODUCT_BASELINE
- Bound to exact file SHA-256
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TARGET_VIDEOS = [
    {
        "id": "master_106s",
        "label": "Master 2min Showcase (7 Styles)",
        "path": "projects/prj_1787139301_all_vox_styles_2min_master/final/vox_all_styles_2min_showcase_master.mp4",
    },
    {
        "id": "ch01_archival_vintage",
        "label": "Chapter 1: Archival Vintage",
        "path": "projects/prj_1787139301_all_vox_styles_2min_master/chapters/prj_1787139301_01_archival_vintag/final/final_vox_video.mp4",
    },
    {
        "id": "ch02_tactical_radar",
        "label": "Chapter 2: Tactical Radar",
        "path": "projects/prj_1787139301_all_vox_styles_2min_master/chapters/prj_1787139524_02_tactical_radar_/final/final_vox_video.mp4",
    },
    {
        "id": "ch03_johnny_harris_map",
        "label": "Chapter 3: Johnny Harris Map",
        "path": "projects/prj_1787139301_all_vox_styles_2min_master/chapters/prj_1787139722_03_johnny_harris_m/final/final_vox_video.mp4",
    },
    {
        "id": "ch04_magnates_media",
        "label": "Chapter 4: Magnates Media",
        "path": "projects/prj_1787139301_all_vox_styles_2min_master/chapters/prj_1787140026_04_magnates_media_/final/final_vox_video.mp4",
    },
    {
        "id": "ch05_true_crime",
        "label": "Chapter 5: True Crime",
        "path": "projects/prj_1787139301_all_vox_styles_2min_master/chapters/prj_1787140229_05_true_crime_khab/final/final_vox_video.mp4",
    },
    {
        "id": "ch06_cyberpunk_tech",
        "label": "Chapter 6: Cyberpunk Tech",
        "path": "projects/prj_1787139301_all_vox_styles_2min_master/chapters/prj_1787140664_06_cyberpunk_tech_/final/final_vox_video.mp4",
    },
    {
        "id": "ch07_vox_classic",
        "label": "Chapter 7: Vox Classic",
        "path": "projects/prj_1787139301_all_vox_styles_2min_master/chapters/prj_1787140836_07_vox_classic_vie/final/final_vox_video.mp4",
    },
]


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def run_ffprobe(video_path: Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,size,bit_rate",
        "-show_entries",
        "stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
        "-of",
        "json",
        str(video_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def run_ffmpeg_decode_check(video_path: Path) -> dict[str, Any]:
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(video_path),
        "-f",
        "null",
        "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "status": "PASS" if res.returncode == 0 and not res.stderr.strip() else "FAIL",
        "returncode": res.returncode,
        "stderr": res.stderr.strip(),
    }


def sample_frames_and_metrics(
    video_path: Path, cadence_sec: float = 0.5
) -> tuple[list[tuple[float, np.ndarray]], list[dict[str, Any]]]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps

    frames: list[tuple[float, np.ndarray]] = []
    t = 0.0
    while t < duration:
        frame_idx = int(round(t * fps))
        if frame_idx >= total_frames:
            break
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame_bgr = cap.read()
        if not ret or frame_bgr is None:
            break
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frames.append((round(t, 2), frame_rgb))
        t += cadence_sec

    cap.release()

    # Compute diagnostic delta between consecutive sampled frames
    metrics: list[dict[str, Any]] = []
    for i in range(len(frames)):
        t_curr, img_curr = frames[i]
        if i == 0:
            metrics.append({
                "timestamp_sec": t_curr,
                "delta_from_prev_mad": 0.0,
                "delta_pct": 0.0,
                "diagnostic_label": "START_FRAME",
            })
        else:
            _, img_prev = frames[i - 1]
            diff = np.abs(img_curr.astype(np.float32) - img_prev.astype(np.float32))
            mad = float(np.mean(diff))
            pct = round((mad / 255.0) * 100.0, 3)
            # Label diagnostic activity
            if pct < 1.0:
                diag = "DEAD_HOLD_CANDIDATE"
            elif pct < 5.0:
                diag = "LOW_ACTIVITY"
            else:
                diag = "MOTION_ACTIVITY"
            metrics.append({
                "timestamp_sec": t_curr,
                "delta_from_prev_mad": round(mad, 3),
                "delta_pct": pct,
                "diagnostic_label": diag,
            })

    return frames, metrics


def create_dense_sheets(
    frames: list[tuple[float, np.ndarray]],
    meta: dict[str, Any],
    out_dir: Path,
    video_id: str,
    cols: int = 5,
    max_rows_per_page: int = 8,
    thumb_w: int = 360,
    thumb_h: int = 202,
) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    total_frames = len(frames)
    frames_per_page = cols * max_rows_per_page
    num_pages = math.ceil(total_frames / frames_per_page) if total_frames > 0 else 1

    sheet_paths: list[str] = []

    for page in range(num_pages):
        page_frames = frames[page * frames_per_page : (page + 1) * frames_per_page]
        rows = math.ceil(len(page_frames) / cols)

        header_h = 70
        cell_pad = 8
        label_h = 24
        cell_w = thumb_w + cell_pad * 2
        cell_h = thumb_h + label_h + cell_pad * 2

        sheet_w = cols * cell_w + cell_pad * 2
        sheet_h = header_h + rows * cell_h + cell_pad * 2

        img = Image.new("RGB", (sheet_w, sheet_h), color=(20, 20, 24))
        draw = ImageDraw.Draw(img)

        # Header
        header_text = (
            f"[REJECTED_PRODUCT_BASELINE] {meta['label']} (Page {page + 1}/{num_pages})\n"
            f"File: {meta['path']} | SHA-256: {meta['sha256'][:16]}... | "
            f"Duration: {meta['duration_sec']}s | Cadence: 0.5s"
        )
        draw.text((cell_pad * 2, 12), header_text, fill=(240, 70, 70))

        for idx, (t_sec, frame_np) in enumerate(page_frames):
            r = idx // cols
            c = idx % cols
            x = cell_pad * 2 + c * cell_w + cell_pad
            y = header_h + r * cell_h + cell_pad

            thumb = Image.fromarray(frame_np).resize(
                (thumb_w, thumb_h), Image.Resampling.LANCZOS
            )
            img.paste(thumb, (x, y))

            # Border
            draw.rectangle(
                [x - 1, y - 1, x + thumb_w, y + thumb_h],
                outline=(60, 60, 70),
                width=1,
            )

            # Label
            draw.text(
                (x, y + thumb_h + 3),
                f"t = {t_sec:05.1f}s | #{idx + page * frames_per_page + 1}",
                fill=(200, 200, 210),
            )

        filename = f"{video_id}_dense_p{page + 1:02d}.jpg"
        sheet_path = out_dir / filename
        img.save(sheet_path, "JPEG", quality=85)
        sheet_paths.append(str(sheet_path.relative_to(PROJECT_ROOT).as_posix()))

    return sheet_paths


def process_all() -> None:
    out_dir = PROJECT_ROOT / ".hermes" / "evidence" / "vox-v3" / "phase0" / "temporal_evidence"
    out_dir.mkdir(parents=True, exist_ok=True)

    report_items: list[dict[str, Any]] = []

    for item in TARGET_VIDEOS:
        v_path = PROJECT_ROOT / item["path"]
        print(f"Processing {item['id']}: {v_path}...")
        sha = compute_sha256(v_path)
        ffprobe_data = run_ffprobe(v_path)
        decode_check = run_ffmpeg_decode_check(v_path)

        fmt = ffprobe_data.get("format", {})
        duration_sec = float(fmt.get("duration", 0.0))
        size_bytes = int(fmt.get("size", 0))

        frames, metrics = sample_frames_and_metrics(v_path, cadence_sec=0.5)

        meta = {
            "id": item["id"],
            "label": item["label"],
            "path": item["path"],
            "sha256": sha,
            "duration_sec": duration_sec,
            "size_bytes": size_bytes,
        }

        sheet_paths = create_dense_sheets(frames, meta, out_dir, item["id"])

        # Calculate dead-hold percentage diagnostic
        dead_holds = [m for m in metrics if m["diagnostic_label"] == "DEAD_HOLD_CANDIDATE"]
        dead_hold_pct = round((len(dead_holds) / max(len(metrics), 1)) * 100.0, 2)

        report_items.append({
            "id": item["id"],
            "label": item["label"],
            "path": item["path"],
            "sha256": sha,
            "size_bytes": size_bytes,
            "duration_sec": duration_sec,
            "ffprobe": ffprobe_data,
            "decode_check": decode_check,
            "cadence_sec": 0.5,
            "total_sampled_frames": len(frames),
            "dense_sheet_paths": sheet_paths,
            "diagnostic_summary": {
                "notice": "DIAGNOSTIC_ONLY: Frame differences are diagnostic metrics and do not represent semantic motion truth",
                "sampled_frame_count": len(frames),
                "dead_hold_frames_pct": dead_hold_pct,
                "motion_active_frames_pct": round(100.0 - dead_hold_pct, 2),
            },
            "temporal_metrics": metrics,
        })
        print(f"  -> Generated {len(sheet_paths)} sheet(s), {len(frames)} sampled frames, decode={decode_check['status']}")

    report_path = out_dir / "temporal_evidence_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "report_version": "1.0",
                "phase": "phase0",
                "classification": "REJECTED_PRODUCT_BASELINE",
                "total_analyzed_videos": len(report_items),
                "items": report_items,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"Temporal evidence report written to {report_path}")


if __name__ == "__main__":
    process_all()
