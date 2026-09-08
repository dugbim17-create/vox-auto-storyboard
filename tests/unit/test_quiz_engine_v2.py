from __future__ import annotations

import os
from pathlib import Path
from PIL import Image

import pytest

from app.services.quiz_engine_v2 import (
    REBUS_BANK,
    DynamicBackgroundCompositor,
    QuizRenderOptions,
    QuizVideoEngineV2,
    apply_diecut_outline,
    draw_rabbit_mascot,
    create_alarm_clock_icon,
)


def test_rebus_bank_categories():
    expected_categories = {
        "emoji_rebus",
        "concept_rebus",
        "open_visual",
        "dont_say_same",
        "multiple_choice",
        "eat_or_pass",
        "fast_math",
        "vocab_flashcard",
        "mystery_box",
        "missing_letters",
        "silhouette_shadow",
        "this_or_that",
    }
    assert expected_categories.issubset(set(REBUS_BANK.keys()))
    assert len(REBUS_BANK["emoji_rebus"]) >= 3
    assert len(REBUS_BANK["mystery_box"]) >= 1
    assert len(REBUS_BANK["missing_letters"]) >= 1
    assert len(REBUS_BANK["this_or_that"]) >= 1


def test_diecut_outline_generator():
    im = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(im)
    draw.ellipse((30, 30, 90, 90), fill=(255, 100, 100, 255))
    
    out = apply_diecut_outline(im, outline_px=6)
    assert out.size == (120, 120)
    assert out.mode == "RGBA"
    # Center pixel is red
    assert out.getpixel((60, 60)) == (255, 100, 100, 255)


def test_rabbit_mascot_render_all_states():
    for state in ["WELCOME", "THINKING", "CELEBRATE"]:
        mascot = draw_rabbit_mascot(size=180, state=state, time_s=1.5)
        assert mascot.size == (180, 180)
        assert mascot.mode == "RGBA"


def test_dynamic_background_render_and_particles():
    bg = DynamicBackgroundCompositor(640, 360, (235, 110, 30), (190, 60, 10))
    frame0 = bg.render(0.0)
    frame1 = bg.render(1.0)
    assert frame0.size == (640, 360)
    assert frame1.size == (640, 360)
    # Background should change smoothly over time due to ray rotation
    assert frame0.tobytes() != frame1.tobytes()


def test_quiz_engine_dual_aspect_options():
    opt_16_9 = QuizRenderOptions(aspect_ratio="16:9")
    engine_16_9 = QuizVideoEngineV2(opt_16_9)
    assert engine_16_9.width == 1920
    assert engine_16_9.height == 1080

    opt_9_16 = QuizRenderOptions(aspect_ratio="9:16")
    engine_9_16 = QuizVideoEngineV2(opt_9_16)
    assert engine_9_16.width == 1080
    assert engine_9_16.height == 1920


def test_new_rabbit_modes_frame_render():
    from PIL import ImageDraw
    engine = QuizVideoEngineV2(QuizRenderOptions(aspect_ratio="16:9"))
    bg = DynamicBackgroundCompositor(1920, 1080, (235, 110, 30), (190, 60, 10))
    
    # 1. Mystery box
    ev_mb = {
        "idx": 1,
        "data": REBUS_BANK["mystery_box"][0],
        "q_start": 0.0,
        "cd_start": 2.0,
        "cd_dur": 4.0,
        "rev_start": 6.0,
        "rev_dur": 4.0,
    }
    c_mb = bg.render(1.0)
    frame_mb = engine._render_question_card(c_mb, ImageDraw.Draw(c_mb), 1.0, ev_mb)
    assert frame_mb.size == (1920, 1080)

    # 2. Missing letters
    ev_ml = {
        "idx": 2,
        "data": REBUS_BANK["missing_letters"][0],
        "q_start": 0.0,
        "cd_start": 2.0,
        "cd_dur": 4.0,
        "rev_start": 6.0,
        "rev_dur": 4.0,
    }
    c_ml = bg.render(1.0)
    frame_ml = engine._render_question_card(c_ml, ImageDraw.Draw(c_ml), 1.0, ev_ml)
    assert frame_ml.size == (1920, 1080)

    # 3. This or that
    ev_tot = {
        "idx": 3,
        "data": REBUS_BANK["this_or_that"][0],
        "q_start": 0.0,
        "cd_start": 2.0,
        "cd_dur": 4.0,
        "rev_start": 6.0,
        "rev_dur": 4.0,
    }
    c_tot = bg.render(1.0)
    frame_tot = engine._render_question_card(c_tot, ImageDraw.Draw(c_tot), 1.0, ev_tot)
    assert frame_tot.size == (1920, 1080)


def test_quiz_engine_dict_choices_and_four_choices_render():
    from PIL import ImageDraw

    # Test 16:9 with dict choices
    engine_169 = QuizVideoEngineV2(QuizRenderOptions(aspect_ratio="16:9"))
    bg_169 = DynamicBackgroundCompositor(1920, 1080, (235, 110, 30), (190, 60, 10))
    q_dict = {
        "question": "Thủ đô của Việt Nam là gì?",
        "choices": [
            {"id": "A", "text": "Hà Nội"},
            {"id": "B", "text": "Huế"},
            {"id": "C", "text": "Đà Nẵng"},
            {"id": "D", "text": "TP Hồ Chí Minh"},
        ],
        "correct_id": "A",
        "answer_text": "A: HÀ NỘI",
    }
    ev = {
        "idx": 1,
        "data": q_dict,
        "q_start": 0.0,
        "cd_start": 2.0,
        "cd_dur": 4.0,
        "rev_start": 6.0,
        "rev_dur": 4.0,
    }
    canvas_169 = bg_169.render(1.0)
    frame_169 = engine_169._render_question_card(canvas_169, ImageDraw.Draw(canvas_169), 1.0, ev)
    assert frame_169.size == (1920, 1080)

    # Test 9:16 with reveal and long text
    engine_916 = QuizVideoEngineV2(QuizRenderOptions(aspect_ratio="9:16"))
    bg_916 = DynamicBackgroundCompositor(1080, 1920, (235, 110, 30), (190, 60, 10))
    canvas_916 = bg_916.render(7.0)
    frame_916 = engine_916._render_question_card(canvas_916, ImageDraw.Draw(canvas_916), 7.0, ev)
    assert frame_916.size == (1080, 1920)

    # Test reveal bar long text
    draw_rev = ImageDraw.Draw(canvas_916)
    long_text = "HỘP XANH: +100 TRIỆU ĐỒNG • HỘP ĐỎ: NỢ 50 TRIỆU • HỘP VÀNG: +10 NGHÌN ĐỒNG"
    engine_916._draw_reveal_bar(draw_rev, 80, 1530, 920, 110, long_text, 8.0, 6.0)

