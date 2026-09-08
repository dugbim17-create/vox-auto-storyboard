from __future__ import annotations

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

import pytest

from app.schemas.quiz import (
    QuizValidationError,
    SUPPORTED_QUESTION_TYPES,
    SUPPORTED_TEMPLATES,
    approve_quiz_project,
    validate_quiz_project,
)


def make_question(
    order: int,
    qtype: str,
    template_id: str,
    question_text: str,
    answer_text: str,
    answer_voice: str,
    *,
    choices: list[dict[str, str]] | None = None,
    correct_choice_id: str | None = None,
    clue_images: list[str] | None = None,
) -> dict:
    data = {
        "question_id": f"q_{order:03d}",
        "order": order,
        "type": qtype,
        "template_id": template_id,
        "question": question_text,
        "question_voice": f"Câu hỏi {order}: {question_text}",
        "answer_text": answer_text,
        "answer_voice": answer_voice,
        "countdown_seconds": 5,
        "fact_sources": [
            {
                "source_id": f"src_{order}",
                "title": "Reference Source",
                "url": "https://example.com/facts",
                "publisher": "Verified Authority",
                "accessed_at": "2026-09-02T12:00:00Z",
                "claim_supported": answer_text,
            }
        ],
    }
    if choices:
        data["choices"] = choices
        data["correct_choice_id"] = correct_choice_id or choices[0]["id"]
    if clue_images:
        data["clue_images"] = clue_images
    return data


def test_supported_archetypes_and_templates_registered():
    expected_types = {
        "emoji_rebus",
        "concept_rebus",
        "open_visual",
        "dont_say_same",
        "eat_or_pass",
        "fast_math",
        "vocab_flashcard",
    }
    assert expected_types.issubset(SUPPORTED_QUESTION_TYPES)

    expected_templates = {
        "emoji_rebus_grid",
        "concept_rebus_horizontal",
        "open_visual_card",
        "dont_say_same_mystery",
        "eat_or_pass_split",
        "fast_math_blackboard",
        "vocab_flashcard_split",
    }
    assert expected_templates.issubset(SUPPORTED_TEMPLATES)


def test_validate_all_archetypes_in_single_quiz():
    questions = [
        # 1. Emoji Rebus
        make_question(
            1,
            "emoji_rebus",
            "emoji_rebus_grid",
            "Nhìn emoji này bạn đoán được từ ghép nào?",
            "Áo mưa",
            "Chính xác là Áo mưa nhé bạn.",
            clue_images=["shirt.png", "rain.png"],
        ),
        # 2. Concept Rebus
        make_question(
            2,
            "concept_rebus",
            "concept_rebus_horizontal",
            "Đây là trò chơi dân gian nào của Việt Nam?",
            "Ô ăn quan",
            "Chuẩn rồi! Đó là trò chơi Ô ăn quan.",
            clue_images=["umbrella.png", "eating.png", "mandarin.png"],
        ),
        # 3. Open Visual
        make_question(
            3,
            "open_visual",
            "open_visual_card",
            "Đây là logo của câu lạc bộ bóng đá nào?",
            "Barcelona",
            "Đáp án chính xác là câu lạc bộ Barcelona.",
        ),
        # 4. Don't Say Same (Reverse Mind Game)
        make_question(
            4,
            "dont_say_same",
            "dont_say_same_mystery",
            "Kể tên một môn học quen thuộc",
            "Toán",
            "Nếu bạn nói môn Toán là bạn đã thua cuộc rồi nha.",
        ),
        # 5. Multiple Choice Pop Trivia
        make_question(
            5,
            "multiple_choice_image",
            "image_left_mcq_right",
            "Messi là cầu thủ của đội tuyển quốc gia nào?",
            "Argentina",
            "Đúng rồi! Messi là cầu thủ của Argentina.",
            choices=[
                {"id": "A", "text": "Brazil"},
                {"id": "B", "text": "Argentina"},
                {"id": "C", "text": "Bồ Đào Nha"},
            ],
            correct_choice_id="B",
        ),
        # 6. Fast Math
        make_question(
            6,
            "fast_math",
            "fast_math_blackboard",
            "90 : 9 + 5 = ?",
            "15",
            "Chính xác! Kết quả là 15.",
            choices=[
                {"id": "A", "text": "10"},
                {"id": "B", "text": "15"},
                {"id": "C", "text": "20"},
                {"id": "D", "text": "25"},
            ],
            correct_choice_id="B",
        ),
        # 7. Bilingual Vocab Flashcard
        make_question(
            7,
            "vocab_flashcard",
            "vocab_flashcard_split",
            "Tên tiếng Anh của Con Cáo là gì?",
            "Fox",
            "Chính xác! Con cáo trong tiếng Anh là Fox.",
            choices=[
                {"id": "A", "text": "Fox"},
                {"id": "B", "text": "Wolf"},
                {"id": "C", "text": "Hyena"},
            ],
            correct_choice_id="A",
        ),
    ]

    project = {
        "schema_version": "quiz_project_v1",
        "title": "Thử Thách Đố Vui Tổng Hợp Rabbit Style",
        "language": "vi",
        "theme_id": "rabbit_vibrant_warm",
        "target_question_count": 7,
        "question_count": 7,
        "seconds_per_question": 5,
        "questions": questions,
        "intro": {
            "title": "THẾ GIỚI TRÒ CHƠI & ĐỐ VUI",
            "subtitle": "Thử thách 7 câu hỏi cực hack não!",
        },
        "outro": {
            "title": "XIN CHÚC MỪNG!",
            "subtitle": "Bạn đã trả lời đúng bao nhiêu câu?",
        },
    }

    validated = validate_quiz_project(project)
    assert len(validated["questions"]) == 7
    approved = approve_quiz_project(validated, approved_at="2026-09-02T12:00:00Z")
    assert approved["approval"]["status"] == "approved"
    assert len(approved["approval"]["content_fingerprint"]) == 64


def test_diecut_sticker_outline_filter():
    # Test diecut filter logic with pure PIL
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((25, 25, 75, 75), fill=(255, 100, 100, 255))

    alpha = img.split()[-1]
    expanded = alpha.filter(ImageFilter.MaxFilter(9))
    border_layer = Image.new("RGBA", img.size, (255, 255, 255, 255))
    border_layer.putalpha(expanded)

    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(border_layer, (0, 0), border_layer)
    out.paste(img, (0, 0), img)

    # Pixel at (50, 22) should be white border (radius 25 + 4px filter expansion)
    pixel_border = out.getpixel((50, 22))
    assert pixel_border[0] == 255 and pixel_border[1] == 255 and pixel_border[2] == 255 and pixel_border[3] == 255
    # Pixel at (50, 50) should be red circle
    pixel_center = out.getpixel((50, 50))
    assert pixel_center[0] == 255 and pixel_center[1] == 100 and pixel_center[2] == 100
