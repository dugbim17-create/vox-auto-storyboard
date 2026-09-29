"""Synthetic Adversarial Fixture Generator for Vox Semantic V3 Phase 0.

Generates 100% owned/synthetic claims, assets, audio, and scene specs:
1. mh370_wrong_aircraft: Claim requires Boeing 777-200ER (2 engines), candidate is Boeing 747 (4 engines).
2. scb_wrong_institution: Claim requires Saigon Commercial Bank (VN), candidate is Siam Commercial Bank (TH).
3. true_crime_foreign_placeholder: Claim is VN criminal case, candidate is US J. Doe casefile.
4. provider_logo_or_gibberish: Synthetic asset with forbidden donor watermark & AI gibberish text.
5. reveal_only_dead_hold: Action scene with 1.5s entrance + 8.5s dead hold (85% dead hold).
6. map_reposition_without_route_continuity: Map scene with plane position teleportation and detached path.
7. financial_connectors_without_transfer: Financial scene with static lines, zero directional transfer/value flow.
8. style_labels_share_one_skeleton: Three styles sharing identical kraft/grid/box/string skeleton.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import wave
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "vox_v3"


def create_claim_fixtures() -> None:
    claims_dir = FIXTURES_DIR / "claims"
    claims_dir.mkdir(parents=True, exist_ok=True)

    # 1. MH370 Claim
    claim_mh370 = {
        "schema_version": "story_evidence/1.0",
        "claim_id": "C001_MH370_AIRCRAFT",
        "claim_text": "Chuyến bay MH370 của Malaysia Airlines mất tích là loại máy bay Boeing 777-200ER, đăng ký 9M-MRO.",
        "claim_type": "confirmed",
        "date": "2014-03-08",
        "place": "Kuala Lumpur - Beijing route",
        "entities": [
            {
                "entity_id": "aircraft_mh370",
                "canonical_name": "Boeing 777-200ER",
                "manufacturer": "Boeing",
                "family": "777",
                "variant": "200ER",
                "engine_count": 2,
                "operator": "Malaysia Airlines",
                "registration": "9M-MRO",
                "aliases": ["9M-MRO", "Boeing 777", "B777-200ER"],
            }
        ],
        "must_show": ["aircraft_mh370"],
        "must_not_invent": ["four_engine_aircraft", "cockpit_fire_visual", "unconfirmed_crash_site"],
        "confidence": 1.0,
    }
    with open(claims_dir / "claim_mh370.json", "w", encoding="utf-8") as f:
        json.dump(claim_mh370, f, indent=2, ensure_ascii=False)

    # 2. SCB Claim
    claim_scb = {
        "schema_version": "story_evidence/1.0",
        "claim_id": "C002_SCB_VIETNAM",
        "claim_text": "Ngân hàng Thương mại Cổ phần Sài Gòn (SCB) tại Việt Nam trong vụ đại án Vạn Thịnh Phát.",
        "claim_type": "confirmed",
        "date": "2022-10-08",
        "place": "TP. Hồ Chí Minh, Việt Nam",
        "entities": [
            {
                "entity_id": "institution_scb_vn",
                "canonical_name": "Saigon Commercial Bank",
                "vietnamese_name": "Ngân hàng Thương mại Cổ phần Sài Gòn",
                "country": "Vietnam",
                "jurisdiction": "VN",
                "headquarters": "TP. Hồ Chí Minh, Việt Nam",
                "ticker_alias": "SCB",
                "forbidden_aliases": ["Siam Commercial Bank", "Standard Chartered Bank", "SCB Thailand"],
            }
        ],
        "must_show": ["institution_scb_vn"],
        "must_not_invent": ["foreign_bank_headquarters"],
        "confidence": 1.0,
    }
    with open(claims_dir / "claim_scb_vn.json", "w", encoding="utf-8") as f:
        json.dump(claim_scb, f, indent=2, ensure_ascii=False)

    # 3. True Crime VN Claim
    claim_tc = {
        "schema_version": "story_evidence/1.0",
        "claim_id": "C003_TRUE_CRIME_VN",
        "claim_text": "Hồ sơ lưu trữ tư liệu điều tra hình sự tại Việt Nam, đối tượng Ngô Bá Khá (Khá Bảnh).",
        "claim_type": "confirmed",
        "date": "2019-04-02",
        "place": "Bắc Ninh, Việt Nam",
        "entities": [
            {
                "entity_id": "person_ngo_ba_kha",
                "canonical_name": "Ngô Bá Khá",
                "aliases": ["Khá Bảnh"],
                "country": "Vietnam",
                "locale": "vi-VN",
            },
            {
                "entity_id": "doc_casefile_vn",
                "canonical_name": "Hồ sơ vụ án hình sự Việt Nam",
                "country": "Vietnam",
                "locale": "vi-VN",
                "forbidden_placeholders": [
                    "John Doe",
                    "J. Doe",
                    "Jane Doe",
                    "Law Enforcement Case File",
                    "US Police Dept",
                    "FBI Case File",
                ],
            },
        ],
        "must_show": ["person_ngo_ba_kha", "doc_casefile_vn"],
        "must_not_invent": ["foreign_law_enforcement_badge", "us_case_template"],
        "confidence": 1.0,
    }
    with open(claims_dir / "claim_true_crime_vn.json", "w", encoding="utf-8") as f:
        json.dump(claim_tc, f, indent=2, ensure_ascii=False)


def create_asset_fixtures() -> None:
    assets_dir = FIXTURES_DIR / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # 1. MH370 Mismatch Asset: Boeing 747 image + metadata
    b747_img = Image.new("RGBA", (800, 450), color=(240, 240, 245, 255))
    d = ImageDraw.Draw(b747_img)
    d.rectangle([20, 20, 780, 430], outline=(100, 100, 120), width=3)
    d.text((40, 40), "[SYNTHETIC FIXTURE] BOEING 747-400 JUMBO JET", fill=(180, 20, 20))
    d.text((40, 80), "Configuration: 4 Engines (Quad-Jet), Double-Deck Cockpit Hump", fill=(50, 50, 60))
    # Draw 4 engine icons
    for i, x in enumerate([150, 250, 550, 650]):
        d.ellipse([x - 30, 220, x + 30, 280], fill=(70, 80, 100))
        d.text((x - 20, 290), f"Eng #{i+1}", fill=(30, 30, 30))
    d.rectangle([320, 160, 480, 340], fill=(120, 140, 160))
    d.text((330, 240), "FUSELAGE (747)", fill=(255, 255, 255))
    b747_img_path = assets_dir / "asset_mh370_b747_mismatch.png"
    b747_img.save(b747_img_path)

    b747_meta = {
        "schema_version": "asset_spec/1.0",
        "asset_id": "asset_b747_candidate",
        "file_path": "tests/fixtures/vox_v3/assets/asset_mh370_b747_mismatch.png",
        "sha256": hashlib.sha256(b747_img_path.read_bytes()).hexdigest(),
        "source_type": "synthetic_fixture",
        "identified_metadata": {
            "canonical_name": "Boeing 747-400",
            "manufacturer": "Boeing",
            "family": "747",
            "variant": "400",
            "engine_count": 4,
            "airframe_type": "widebody_quadjet",
        },
        "intended_claim_target": "C001_MH370_AIRCRAFT",
        "mismatch_reason": "Entity mismatch: candidate has 4 engines / Boeing 747, claim requires Boeing 777-200ER with 2 engines.",
    }
    with open(assets_dir / "asset_mh370_b747_mismatch.json", "w", encoding="utf-8") as f:
        json.dump(b747_meta, f, indent=2, ensure_ascii=False)

    # 2. SCB Thailand Mismatch Asset
    scb_th_img = Image.new("RGBA", (800, 450), color=(250, 245, 255, 255))
    d = ImageDraw.Draw(scb_th_img)
    d.rectangle([20, 20, 780, 430], outline=(120, 40, 140), width=3)
    d.text((40, 40), "[SYNTHETIC FIXTURE] SIAM COMMERCIAL BANK (SCB THAILAND)", fill=(120, 20, 140))
    d.text((40, 80), "Location: Bangkok, Thailand | Currency: Thai Baht (THB)", fill=(50, 50, 60))
    d.rectangle([250, 160, 550, 320], fill=(90, 30, 120))
    d.text((270, 230), "SIAM COMMERCIAL BANK", fill=(255, 255, 255))
    scb_th_path = assets_dir / "asset_scb_thailand_mismatch.png"
    scb_th_img.save(scb_th_path)

    scb_th_meta = {
        "schema_version": "asset_spec/1.0",
        "asset_id": "asset_scb_thailand_candidate",
        "file_path": "tests/fixtures/vox_v3/assets/asset_scb_thailand_mismatch.png",
        "sha256": hashlib.sha256(scb_th_path.read_bytes()).hexdigest(),
        "source_type": "synthetic_fixture",
        "identified_metadata": {
            "canonical_name": "Siam Commercial Bank",
            "country": "Thailand",
            "jurisdiction": "TH",
            "ticker_alias": "SCB",
            "headquarters": "Bangkok, Thailand",
        },
        "intended_claim_target": "C002_SCB_VIETNAM",
        "mismatch_reason": "Entity mismatch: candidate is Siam Commercial Bank (Thailand/TH), claim requires Saigon Commercial Bank (Vietnam/VN).",
    }
    with open(assets_dir / "asset_scb_thailand_mismatch.json", "w", encoding="utf-8") as f:
        json.dump(scb_th_meta, f, indent=2, ensure_ascii=False)

    # 3. US Casefile Placeholder
    tc_us_img = Image.new("RGBA", (800, 450), color=(245, 240, 230, 255))
    d = ImageDraw.Draw(tc_us_img)
    d.rectangle([20, 20, 780, 430], outline=(150, 100, 50), width=3)
    d.text((40, 40), "[SYNTHETIC FIXTURE] US LAW ENFORCEMENT CASE FILE", fill=(180, 30, 30))
    d.text((40, 90), "SUBJECT: J. DOE (JOHN DOE)", fill=(30, 30, 30))
    d.text((40, 130), "AGENCY: METRO POLICE DEPARTMENT - SECTOR 4", fill=(50, 50, 50))
    d.rectangle([100, 180, 700, 380], fill=(230, 220, 200), outline=(100, 100, 100))
    d.text((120, 200), "CASE CLASSIFICATION: GENERIC PLACEHOLDER", fill=(100, 40, 40))
    d.text((120, 240), "PLACEHOLDER EVIDENCE LOG #99481-US", fill=(70, 70, 70))
    tc_us_path = assets_dir / "asset_true_crime_us_placeholder.png"
    tc_us_img.save(tc_us_path)

    tc_us_meta = {
        "schema_version": "asset_spec/1.0",
        "asset_id": "asset_us_casefile_jdoe",
        "file_path": "tests/fixtures/vox_v3/assets/asset_true_crime_us_placeholder.png",
        "sha256": hashlib.sha256(tc_us_path.read_bytes()).hexdigest(),
        "source_type": "synthetic_fixture",
        "identified_metadata": {
            "canonical_name": "US Law Enforcement Case File",
            "locale": "en-US",
            "detected_placeholders": ["J. DOE", "JOHN DOE", "METRO POLICE DEPARTMENT"],
            "country": "United States",
        },
        "intended_claim_target": "C003_TRUE_CRIME_VN",
        "mismatch_reason": "Locale/placeholder mismatch: foreign US placeholder template attached to Vietnamese documentary claim.",
    }
    with open(assets_dir / "asset_true_crime_us_placeholder.json", "w", encoding="utf-8") as f:
        json.dump(tc_us_meta, f, indent=2, ensure_ascii=False)

    # 4. Donor Watermark & AI Gibberish Asset
    gib_img = Image.new("RGBA", (800, 450), color=(230, 235, 245, 255))
    d = ImageDraw.Draw(gib_img)
    d.rectangle([20, 20, 780, 430], outline=(100, 120, 140), width=3)
    d.text((40, 40), "[SYNTHETIC FIXTURE] AI GENERATED WITH WATERMARK & GIBBERISH", fill=(200, 40, 40))
    d.text((40, 100), "GLOBAL FORUM SUMMIT 2026 WORLD AI INNOVATION", fill=(40, 40, 120))
    d.text((40, 150), "FLX-CONVERGENCE INTERNATIONALE FORUM DE SYNTHESIS", fill=(80, 80, 90))
    # Draw simulated diagonal watermark
    d.line([(0, 450), (800, 0)], fill=(200, 100, 100, 180), width=6)
    d.text((250, 230), "DONOR_STOCK_WATERMARK_FORBIDDEN", fill=(220, 50, 50))
    gib_path = assets_dir / "asset_provider_logo_gibberish.png"
    gib_img.save(gib_path)

    gib_meta = {
        "schema_version": "asset_spec/1.0",
        "asset_id": "asset_provider_logo_gibberish",
        "file_path": "tests/fixtures/vox_v3/assets/asset_provider_logo_gibberish.png",
        "sha256": hashlib.sha256(gib_path.read_bytes()).hexdigest(),
        "source_type": "synthetic_fixture",
        "identified_metadata": {
            "detected_donor_watermark": True,
            "watermark_text": "DONOR_STOCK_WATERMARK_FORBIDDEN",
            "detected_ai_gibberish": [
                "GLOBAL FORUM SUMMIT 2026 WORLD AI INNOVATION",
                "FLX-CONVERGENCE INTERNATIONALE FORUM DE SYNTHESIS",
            ],
            "contains_unverified_text": True,
        },
        "mismatch_reason": "Asset quality rejection: forbidden donor watermark and hallucinated AI text detected.",
    }
    with open(assets_dir / "asset_provider_logo_gibberish.json", "w", encoding="utf-8") as f:
        json.dump(gib_meta, f, indent=2, ensure_ascii=False)


def create_audio_fixture() -> None:
    audio_dir = FIXTURES_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    wav_path = audio_dir / "performance_30s.wav"

    sample_rate = 44100
    duration_sec = 30.0
    total_samples = int(sample_rate * duration_sec)

    # Synthesize 30s structured speech-like audio with explicit phrases & pauses
    # Phrase intervals: [0-5s speech], [5-7s pause], [7-14s speech], [14-16s pause], [16-24s speech], [24-26s pause], [26-30s speech]
    segments = [
        (0.0, 5.0, True, 220.0),    # speech phrase 1
        (5.0, 7.0, False, 0.0),     # pause 1
        (7.0, 14.0, True, 240.0),   # speech phrase 2 (emphasis)
        (14.0, 16.0, False, 0.0),   # pause 2
        (16.0, 24.0, True, 200.0),  # speech phrase 3
        (24.0, 26.0, False, 0.0),   # pause 3
        (26.0, 30.0, True, 230.0),  # speech phrase 4 (punchline)
    ]

    samples: list[int] = []
    for i in range(total_samples):
        t = i / sample_rate
        # Find active segment
        amp = 0.0
        freq = 0.0
        for start, end, is_speech, f in segments:
            if start <= t < end:
                if is_speech:
                    # Speech envelope with harmonics
                    freq = f
                    # Slight modulation
                    amp = 0.6 * math.sin(2 * math.pi * 3.0 * t) + 0.4
                    amp = max(0.2, min(1.0, abs(amp)))
                break
        if freq > 0.0:
            val = amp * 0.5 * (
                math.sin(2 * math.pi * freq * t)
                + 0.5 * math.sin(2 * math.pi * freq * 2.0 * t)
                + 0.25 * math.sin(2 * math.pi * freq * 3.0 * t)
            )
            val_int = int(val * 32767.0)
        else:
            val_int = 0
        samples.append(max(-32768, min(32767, val_int)))

    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        data = struct.pack(f"<{len(samples)}h", *samples)
        wf.writeframes(data)

    print(f"Generated synthetic audio fixture: {wav_path} ({duration_sec}s, SHA-256={hashlib.sha256(wav_path.read_bytes()).hexdigest()[:16]}...)")


def create_scene_fixtures() -> None:
    scenes_dir = FIXTURES_DIR / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    # 5. Reveal-only dead hold scene
    scene_dead_hold = {
        "schema_version": "scene_spec/3.0",
        "scene_id": "SCN_01_REVEAL_DEAD_HOLD",
        "grammar": "action_scene",
        "visual_thesis": "Showcase tactical pursuit action",
        "duration_ms": 10000,
        "fps": 30,
        "motion_fps": 12,
        "canvas": {"width": 1920, "height": 1080},
        "entities": [
            {
                "entity_id": "background",
                "role": "background",
                "asset": "asset://bg/dark_grid",
                "transform": {"position": [0, 0], "scale": 1.0},
            },
            {
                "entity_id": "tactical_vehicle",
                "role": "object",
                "asset": "asset://object/vehicle",
                "transform": {"position": [960, 540], "scale": 1.0},
            },
        ],
        "events": [
            {
                "event_id": "evt_01_reveal",
                "anchor": "xe đặc nhiệm xuất hiện",
                "start_ms": 0,
                "duration_ms": 1500,
                "action": "reveal",
                "target": "tactical_vehicle",
                "enter": "popup",
            }
        ],
        "temporal_profile": {
            "entrance_duration_ms": 1500,
            "action_duration_ms": 0,
            "dead_hold_duration_ms": 8500,
            "dead_hold_ratio": 0.85,
            "declared_hold_purpose": None,
        },
        "rejection_reason": "Grammar-aware temporal rejection: action scene contains only reveal entrance (1.5s) followed by 85% dead hold (8.5s) without sustained semantic movement.",
    }
    with open(scenes_dir / "scene_reveal_only_dead_hold.json", "w", encoding="utf-8") as f:
        json.dump(scene_dead_hold, f, indent=2, ensure_ascii=False)

    # 6. Map reposition without route continuity
    scene_map_broken = {
        "schema_version": "scene_spec/3.0",
        "scene_id": "SCN_02_MAP_DISCONTINUOUS",
        "grammar": "map_route",
        "visual_thesis": "Máy bay chuyển hướng bất ngờ từ điểm A sang điểm B",
        "duration_ms": 6000,
        "fps": 30,
        "motion_fps": 12,
        "canvas": {"width": 1920, "height": 1080},
        "entities": [
            {"entity_id": "map_base", "role": "map_base", "asset": "asset://map/sea_region"},
            {"entity_id": "plane_marker", "role": "traveling_marker", "asset": "asset://map/plane_icon"},
        ],
        "route_spec": {
            "declared_polyline": None,
            "continuous_path": False,
        },
        "events": [
            {
                "event_id": "evt_01_pos_a",
                "start_ms": 0,
                "duration_ms": 2000,
                "action": "hold",
                "target": "plane_marker",
                "position": [300, 400],
            },
            {
                "event_id": "evt_02_teleport_b",
                "start_ms": 2000,
                "duration_ms": 4000,
                "action": "hold",
                "target": "plane_marker",
                "position": [1500, 800],
                "motion_type": "instant_teleport_without_path",
            },
        ],
        "rejection_reason": "Route and marker continuity rejection: plane jumps coordinates ([300,400] -> [1500,800]) without monotonic path progression or route polyline attachment.",
    }
    with open(scenes_dir / "scene_map_reposition_without_route_continuity.json", "w", encoding="utf-8") as f:
        json.dump(scene_map_broken, f, indent=2, ensure_ascii=False)

    # 7. Financial connectors without transfer
    scene_fin_static = {
        "schema_version": "scene_spec/3.0",
        "scene_id": "SCN_03_FINANCIAL_STATIC_CONNECTORS",
        "grammar": "process_flow",
        "visual_thesis": "Dòng tiền chuyển dịch giữa Tập đoàn Vạn Thịnh Phát và Ngân hàng SCB",
        "duration_ms": 8000,
        "fps": 30,
        "canvas": {"width": 1920, "height": 1080},
        "entities": [
            {"entity_id": "source_corp", "role": "node", "label": "Tập đoàn VTP", "state": "initial"},
            {"entity_id": "target_bank", "role": "node", "label": "Ngân hàng SCB", "state": "initial"},
            {"entity_id": "static_line", "role": "connector", "type": "undirected_static_line"},
        ],
        "process_spec": {
            "has_direction": False,
            "has_token_transfer": False,
            "has_state_mutation": False,
            "transferred_value": None,
        },
        "events": [
            {
                "event_id": "evt_01_draw_static_line",
                "start_ms": 1000,
                "duration_ms": 1000,
                "action": "reveal",
                "target": "static_line",
            },
            {
                "event_id": "evt_02_hold",
                "start_ms": 2000,
                "duration_ms": 6000,
                "action": "hold",
                "target": "static_line",
            },
        ],
        "rejection_reason": "Process-flow rejection: financial scene connects nodes with static undirected lines; lacks direction, token transfer, amount flow, and node state change.",
    }
    with open(scenes_dir / "scene_financial_connectors_without_transfer.json", "w", encoding="utf-8") as f:
        json.dump(scene_fin_static, f, indent=2, ensure_ascii=False)

    # 8. Style labels share one skeleton
    scene_shared_skeleton = {
        "schema_version": "visual_language/1.0",
        "fixture_id": "FIX_08_SHARED_SKELETON",
        "declared_styles": [
            {"style_id": "archival_vintage", "label": "Archival Vintage 1980s"},
            {"style_id": "tactical_radar", "label": "Tactical Military Radar"},
            {"style_id": "vox_classic", "label": "Vox Classic Explainer"},
        ],
        "layout_skeletons": {
            "archival_vintage": {
                "background_texture": "kraft_paper_grid.png",
                "title_card_box": {"x": 120, "y": 80, "w": 650, "h": 90},
                "subtitle_box": {"x": 120, "y": 180, "w": 500, "h": 45},
                "asset_border": {"type": "white_sticker_outline", "stroke_px": 4},
                "connector_element": "red_string_diagonal",
                "grid_density": "16x9_grid_subdivided",
            },
            "tactical_radar": {
                "background_texture": "kraft_paper_grid.png",
                "title_card_box": {"x": 120, "y": 80, "w": 650, "h": 90},
                "subtitle_box": {"x": 120, "y": 180, "w": 500, "h": 45},
                "asset_border": {"type": "white_sticker_outline", "stroke_px": 4},
                "connector_element": "red_string_diagonal",
                "grid_density": "16x9_grid_subdivided",
            },
            "vox_classic": {
                "background_texture": "kraft_paper_grid.png",
                "title_card_box": {"x": 120, "y": 80, "w": 650, "h": 90},
                "subtitle_box": {"x": 120, "y": 180, "w": 500, "h": 45},
                "asset_border": {"type": "white_sticker_outline", "stroke_px": 4},
                "connector_element": "red_string_diagonal",
                "grid_density": "16x9_grid_subdivided",
            },
        },
        "skeleton_similarity_score": 1.0,
        "blind_separation_pass": False,
        "rejection_reason": "Style-separation rejection: 3 distinct style IDs share 100% identical layout skeleton, kraft/grid texture, white sticker outline, and red-string connectors.",
    }
    with open(scenes_dir / "scene_styles_shared_skeleton.json", "w", encoding="utf-8") as f:
        json.dump(scene_shared_skeleton, f, indent=2, ensure_ascii=False)


def main() -> None:
    print(f"Generating synthetic adversarial fixtures in {FIXTURES_DIR}...")
    create_claim_fixtures()
    create_asset_fixtures()
    create_audio_fixture()
    create_scene_fixtures()
    print("All adversarial fixtures created successfully.")


if __name__ == "__main__":
    main()
