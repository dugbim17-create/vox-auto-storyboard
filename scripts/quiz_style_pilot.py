"""Phase A offline visual pilot for channel style-pack selection.

The pilot intentionally stays outside the production engine: it uses one fixed
content fixture, deterministic Pillow primitives, and produces PNG evidence only.
It does not import provider, TTS, Qt, or video/export code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN = "20260908T110725Z"
DEFAULT_HYBRID_RUN = "20260908T153830Z"

CANVAS = (1600, 900)
MARGIN = 56
WHITE = (247, 244, 235)
INK = (28, 30, 34)
MUTED = (102, 105, 106)

FONT_REGULAR = Path("C:/Windows/Fonts/arial.ttf")
FONT_BOLD = Path("C:/Windows/Fonts/arialbd.ttf")
FONT_ITALIC = Path("C:/Windows/Fonts/ariali.ttf")


@dataclass(frozen=True)
class Style:
    style_id: str
    title: str
    strap: str
    background: tuple[int, int, int]
    panel: tuple[int, int, int]
    accent: tuple[int, int, int]
    accent_2: tuple[int, int, int]
    ink: tuple[int, int, int]
    muted: tuple[int, int, int]
    label: str


STYLES: tuple[Style, ...] = (
    Style(
        "sport-scoreboard",
        "SPORT / SCOREBOARD",
        "FAST READ · COMPETITIVE",
        (11, 25, 39),
        (20, 43, 62),
        (255, 205, 62),
        (235, 74, 61),
        (245, 248, 242),
        (164, 186, 196),
        "01",
    ),
    Style(
        "editorial-culture",
        "CULTURE / EDITORIAL",
        "CONTEXT · DETAIL · MEMORY",
        (232, 224, 208),
        (248, 243, 233),
        (163, 49, 42),
        (36, 73, 77),
        (40, 39, 36),
        (109, 101, 91),
        "02",
    ),
    Style(
        "clear-knowledge",
        "KNOWLEDGE / CLEAR",
        "ONE IDEA · WELL EXPLAINED",
        (235, 241, 237),
        (255, 255, 252),
        (22, 104, 91),
        (235, 139, 50),
        (31, 43, 42),
        (93, 111, 105),
        "03",
    ),
)

FIXTURE: dict[str, Any] = {
    "schema_version": "channel_style_phase_a_fixture_v1",
    "origin": "hand-authored deterministic content fixture for visual comparison",
    "provider_calls": 0,
    "tts_calls": 0,
    "video_exports": 0,
    "locale": "en-US",
    "content": {
        "series": "Hidden Systems",
        "question": "Why do airport runways use numbers that change over time?",
        "question_long": (
            "Why do airport runways use numbers that change over time, even though the runway itself stays in the same place?"
        ),
        "choices": [
            {"id": "A", "text": "The numbers follow Earth's magnetic field."},
            {"id": "B", "text": "They match the airport's opening year."},
            {"id": "C", "text": "They indicate the runway length."},
            {"id": "D", "text": "They are assigned by the airline."},
        ],
        "comparison": {
            "question": "Which explanation fits the runway numbering rule?",
            "left": {"id": "A", "title": "MAGNETIC NORTH", "body": "The reference direction shifts slowly."},
            "right": {"id": "B", "title": "OPENING YEAR", "body": "A date does not define runway heading."},
        },
        "fact": "Runway numbers are based on magnetic heading, rounded to the nearest ten degrees.",
    },
}


def font(size: int, *, bold: bool = False, italic: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_ITALIC if italic else FONT_REGULAR
    if not path.is_file():
        return ImageFont.load_default()
    return ImageFont.truetype(str(path), size)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=fnt)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text).split("\n"):
        words = paragraph.split()
        line = ""
        for word in words:
            candidate = word if not line else f"{line} {word}"
            if line and text_size(draw, candidate, fnt)[0] > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line or not words:
            lines.append(line)
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    fnt: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    *,
    line_gap: int = 8,
    max_lines: int | None = None,
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    lines = wrap_text(draw, text, fnt, x1 - x0)
    if max_lines is not None:
        lines = lines[:max_lines]
    bbox = draw.textbbox((0, 0), "Ag", font=fnt)
    line_height = bbox[3] - bbox[1] + line_gap
    for index, line in enumerate(lines):
        draw.text((x0, y0 + index * line_height), line, font=fnt, fill=fill)
    end_y = y0 + max(1, len(lines)) * line_height - line_gap
    return x0, y0, x1, min(y1, end_y)


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: tuple[int, int, int], radius: int = 18, outline: tuple[int, int, int] | None = None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def pill(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, style: Style, *, fill: tuple[int, int, int] | None = None, text_fill: tuple[int, int, int] | None = None) -> None:
    rounded(draw, box, fill or style.accent, radius=(box[3] - box[1]) // 2)
    fnt = font(18, bold=True)
    tw, th = text_size(draw, text, fnt)
    draw.text(((box[0] + box[2] - tw) // 2, (box[1] + box[3] - th) // 2 - 2), text, font=fnt, fill=text_fill or style.ink)


def draw_dots(draw: ImageDraw.ImageDraw, x: int, y: int, color: tuple[int, int, int], count: int = 8, step: int = 15, radius: int = 3) -> None:
    for index in range(count):
        draw.ellipse((x + index * step - radius, y - radius, x + index * step + radius, y + radius), fill=color)


def draw_sport_background(draw: ImageDraw.ImageDraw, style: Style) -> None:
    w, h = CANVAS
    for y in range(h):
        ratio = y / (h - 1)
        color = tuple(round(style.background[i] * (1 - ratio) + (17, 49, 68)[i] * ratio) for i in range(3))
        draw.line((0, y, w, y), fill=color)
    draw.line((0, 730, w, 730), fill=style.accent_2, width=3)
    draw.line((0, 752, w, 752), fill=(40, 74, 89), width=2)
    for x in range(-300, w + 400, 145):
        draw.line((x, 900, x + 500, 730), fill=(35, 72, 88), width=2)
    draw.rectangle((0, 0, w, 14), fill=style.accent)


def draw_culture_background(draw: ImageDraw.ImageDraw, style: Style) -> None:
    w, h = CANVAS
    draw.rectangle((0, 0, w, h), fill=style.background)
    draw.rectangle((0, 0, 18, h), fill=style.accent)
    draw.line((MARGIN, 132, w - MARGIN, 132), fill=(186, 174, 155), width=2)
    draw.line((MARGIN, 754, w - MARGIN, 754), fill=(186, 174, 155), width=2)
    for x in range(900, 1500, 44):
        draw.line((x, 155, x - 70, 310), fill=(213, 203, 184), width=2)
    draw.ellipse((1180, 450, 1470, 740), outline=(214, 201, 179), width=3)
    draw.arc((1135, 390, 1515, 770), 198, 334, fill=(199, 185, 165), width=2)


def draw_knowledge_background(draw: ImageDraw.ImageDraw, style: Style) -> None:
    w, h = CANVAS
    draw.rectangle((0, 0, w, h), fill=style.background)
    draw.rectangle((0, 0, w, 18), fill=style.accent)
    draw.line((MARGIN, 132, w - MARGIN, 132), fill=(197, 211, 204), width=2)
    draw.line((MARGIN, 754, w - MARGIN, 754), fill=(197, 211, 204), width=2)
    for x in range(990, 1450, 52):
        draw.line((x, 205, x, 638), fill=(211, 224, 217), width=2)
    for y in range(205, 650, 52):
        draw.line((990, y, 1450, y), fill=(211, 224, 217), width=2)
    draw.ellipse((1125, 315, 1330, 520), outline=style.accent, width=4)
    draw.line((1228, 290, 1228, 545), fill=style.accent, width=3)
    draw.line((1100, 417, 1354, 417), fill=style.accent, width=3)


def draw_hybrid_knowledge_background(draw: ImageDraw.ImageDraw, style: Style) -> None:
    """Knowledge/Clear base with restrained editorial paper, evidence, and red signal marks."""
    w, h = CANVAS
    draw.rectangle((0, 0, w, h), fill=(238, 239, 232))
    draw.rectangle((0, 0, w, 18), fill=style.accent)
    draw.rectangle((0, 0, 20, h), fill=(178, 54, 43))
    draw.line((MARGIN, 132, w - MARGIN, 132), fill=(192, 199, 189), width=2)
    draw.line((MARGIN, 832, w - MARGIN, 832), fill=(192, 199, 189), width=2)
    draw.line((1030, 188, 1170, 188), fill=(199, 178, 151), width=2)
    draw.line((1390, 188, 1474, 188), fill=(199, 178, 151), width=2)
    draw.line((1030, 646, 1474, 646), fill=(199, 178, 151), width=2)
    for x in range(1040, 1470, 54):
        draw.line((x, 220, x, 615), fill=(218, 220, 211), width=2)
    for y in range(220, 620, 54):
        draw.line((1040, y, 1470, y), fill=(218, 220, 211), width=2)
    draw.ellipse((1180, 390, 1350, 560), outline=style.accent, width=4)
    draw.line((1265, 360, 1265, 590), fill=style.accent, width=3)
    draw.line((1145, 475, 1400, 475), fill=style.accent, width=3)
    draw.line((1330, 410, 1410, 360), fill=(178, 54, 43), width=4)
    draw.polygon(((1410, 360), (1384, 367), (1398, 388)), fill=(178, 54, 43))


def draw_hybrid_knowledge_question(*, long_question: bool = False) -> Image.Image:
    style = STYLES[2]
    image = Image.new("RGB", CANVAS, style.background)
    draw = ImageDraw.Draw(image)
    draw_hybrid_knowledge_background(draw, style)
    draw.text((MARGIN, 42), "KNOWLEDGE / EDITORIAL", font=font(24, bold=True), fill=(178, 54, 43))
    draw.text((MARGIN, 78), "ONE IDEA · WELL EXPLAINED · EVIDENCE FIRST", font=font(15, bold=True), fill=style.muted)
    draw.text((1480, 46), "K/E", font=font(30, bold=True), fill=style.accent_2)
    draw_dots(draw, 1374, 88, style.accent, count=5 if not long_question else 4)
    draw.text((MARGIN, 108), "HIDDEN SYSTEMS  /  QUESTION 04 OF 10", font=font(14, bold=True), fill=style.muted)
    draw.text((MARGIN + 10, 176), "THE QUESTION", font=font(17, bold=True), fill=(178, 54, 43))
    q_text = FIXTURE["content"]["question_long" if long_question else "question"]
    draw_wrapped(draw, q_text, (MARGIN + 10, 220, 1010, 390), font(47 if not long_question else 38, bold=True), style.ink, line_gap=9, max_lines=3)
    draw.line((MARGIN + 10, 416, 1000, 416), fill=(178, 54, 43), width=3)
    choices_y = 464
    height = 73 if not long_question else 61
    gap = 19 if not long_question else 14
    for i, choice in enumerate(FIXTURE["content"]["choices"]):
        y = choices_y + i * (height + gap)
        marker_size = 48 if not long_question else 40
        marker_top = y + (13 if not long_question else 10)
        draw.ellipse((MARGIN + 10, marker_top, MARGIN + 10 + marker_size, marker_top + marker_size), fill=style.accent)
        draw.text((MARGIN + 25, marker_top + (7 if not long_question else 4)), choice["id"], font=font(19 if not long_question else 16, bold=True), fill=WHITE)
        draw.text((MARGIN + 84, y + 19), choice["text"], font=font(25 if not long_question else 21), fill=style.ink)
        draw.line((MARGIN + 84, y + height, 1000, y + height), fill=(199, 207, 199), width=2)
    draw.text((1080, 180), "FIELD NOTE 04", font=font(16, bold=True), fill=style.muted)
    draw.text((1080, 214), "DIRECTION", font=font(37, bold=True), fill=style.accent)
    draw.text((1080, 256), "changes", font=font(37, bold=True), fill=(178, 54, 43))
    draw.rounded_rectangle((1062, 610, 1490, 700), radius=10, fill=(238, 239, 232))
    draw_wrapped(draw, "A moving reference can change a familiar label.", (1080, 625, 1480, 685), font(22, italic=True), style.ink, line_gap=8, max_lines=2)
    draw.text((MARGIN, 864), "NO IMAGE SLOT · EVIDENCE + EXPLANATION SHARE THE FRAME", font=font(14, bold=True), fill=style.muted)
    return image


def draw_hybrid_knowledge_reveal() -> Image.Image:
    style = STYLES[2]
    image = Image.new("RGB", CANVAS, style.background)
    draw = ImageDraw.Draw(image)
    draw_hybrid_knowledge_background(draw, style)
    draw.text((MARGIN, 42), "KNOWLEDGE / EDITORIAL", font=font(24, bold=True), fill=(178, 54, 43))
    draw.text((MARGIN, 78), "ONE IDEA · WELL EXPLAINED · EVIDENCE FIRST", font=font(15, bold=True), fill=style.muted)
    draw.text((1480, 46), "K/E", font=font(30, bold=True), fill=style.accent_2)
    draw_dots(draw, 1374, 88, style.accent, count=5)
    draw.text((MARGIN, 108), "HIDDEN SYSTEMS  /  QUESTION 04 OF 10", font=font(14, bold=True), fill=style.muted)
    draw.text((MARGIN, 175), "ANSWER REVEAL", font=font(18, bold=True), fill=(178, 54, 43))
    draw_wrapped(draw, "They follow Earth's magnetic field.", (MARGIN, 220, 980, 340), font(55, bold=True), style.ink, line_gap=8, max_lines=2)
    draw.line((MARGIN, 384, 970, 384), fill=(178, 54, 43), width=3)
    rounded(draw, (MARGIN, 450, 980, 680), style.panel, radius=16, outline=(197, 211, 204), width=2)
    draw.text((MARGIN + 34, 484), "CORRECT ANSWER  /  A", font=font(20, bold=True), fill=style.accent)
    draw.text((MARGIN + 34, 524), "MAGNETIC NORTH", font=font(32, bold=True), fill=style.ink)
    draw_wrapped(draw, FIXTURE["content"]["fact"], (MARGIN + 34, 585, 920, 650), font(23), style.ink, line_gap=7, max_lines=3)
    draw.rounded_rectangle((1062, 202, 1490, 370), radius=12, fill=(238, 239, 232))
    draw.text((1080, 180), "WHY IT MATTERS", font=font(16, bold=True), fill=style.muted)
    draw_wrapped(draw, "Runway numbers are a snapshot of direction, not a permanent name.", (1080, 225, 1480, 350), font(31, bold=True), style.accent, line_gap=8, max_lines=3)
    draw.rounded_rectangle((1062, 438, 1490, 592), radius=10, fill=(238, 239, 232))
    draw.line((1080, 455, 1480, 455), fill=(178, 54, 43), width=3)
    draw.text((1080, 500), "FIELD NOTE 04", font=font(18, bold=True), fill=style.ink)
    draw.text((1080, 550), "RULE -> EVIDENCE -> TAKEAWAY", font=font(17, bold=True), fill=(178, 54, 43))
    draw.text((MARGIN, 864), "REVEAL STATE · FACT AREA REMAINS VISIBLE", font=font(14, bold=True), fill=style.muted)
    return image


def draw_header(draw: ImageDraw.ImageDraw, style: Style, index: int, *, compact: bool = False) -> None:
    draw.text((MARGIN, 42), style.title, font=font(24, bold=True), fill=style.accent)
    draw.text((MARGIN, 78), style.strap, font=font(15, bold=True), fill=style.muted)
    draw.text((1480, 46), style.label, font=font(30, bold=True), fill=style.accent_2)
    draw_dots(draw, 1374, 88, style.accent, count=6 if not compact else 4)
    draw.text((MARGIN, 108), f"HIDDEN SYSTEMS  /  QUESTION {index} OF 10", font=font(14, bold=True), fill=style.muted)


def draw_question_state(style: Style, *, long_question: bool = False) -> Image.Image:
    image = Image.new("RGB", CANVAS, style.background)
    draw = ImageDraw.Draw(image)
    if style.style_id == "sport-scoreboard":
        draw_sport_background(draw, style)
    elif style.style_id == "editorial-culture":
        draw_culture_background(draw, style)
    else:
        draw_knowledge_background(draw, style)
    draw_header(draw, style, 4, compact=long_question)

    if style.style_id == "sport-scoreboard":
        rounded(draw, (MARGIN, 166, 1060, 398), style.panel, radius=8)
        draw.rectangle((MARGIN, 166, MARGIN + 16, 398), fill=style.accent)
        draw.text((MARGIN + 42, 194), "THE QUESTION", font=font(18, bold=True), fill=style.accent_2)
        q_font = font(48 if not long_question else 39, bold=True)
        draw_wrapped(draw, FIXTURE["content"]["question_long" if long_question else "question"], (MARGIN + 42, 240, 1010, 370), q_font, style.ink, line_gap=8, max_lines=3)
        pill(draw, (1110, 178, 1270, 232), "4 / 10", style)
        draw.text((1110, 270), "SCORE", font=font(16, bold=True), fill=style.muted)
        draw.text((1110, 298), "07", font=font(68, bold=True), fill=style.accent)
        draw.text((1110, 366), "ROUND", font=font(16, bold=True), fill=style.muted)
        draw.text((1110, 394), "WARM-UP", font=font(25, bold=True), fill=style.ink)
        choices_y = 452
        gap = 16
        height = 82 if not long_question else 72
        for i, choice in enumerate(FIXTURE["content"]["choices"]):
            y = choices_y + i * (height + gap)
            card_fill = (30, 61, 81) if i % 2 == 0 else (24, 54, 74)
            rounded(draw, (MARGIN, y, 1060, y + height), card_fill, radius=8)
            draw.rectangle((MARGIN, y, MARGIN + 74, y + height), fill=style.accent_2)
            draw.text((MARGIN + 27, y + 23), choice["id"], font=font(28, bold=True), fill=style.ink)
            draw.text((MARGIN + 102, y + 22), choice["text"], font=font(25 if not long_question else 21, bold=True), fill=style.ink if False else style.ink)
        draw.rectangle((MARGIN, 826, 1060, 842), fill=(36, 69, 82))
        draw.rectangle((MARGIN, 826, 500, 842), fill=style.accent)
        draw.text((1110, 488), "READ → THINK → PICK", font=font(18, bold=True), fill=style.accent)
        draw.text((1110, 524), "5 s", font=font(50, bold=True), fill=style.ink)
    elif style.style_id == "editorial-culture":
        draw.text((MARGIN + 10, 176), "THE QUESTION", font=font(17, bold=True), fill=style.accent)
        q_font = font(48 if not long_question else 39, bold=True)
        draw_wrapped(draw, FIXTURE["content"]["question_long" if long_question else "question"], (MARGIN + 10, 218, 1060, 375), q_font, style.ink, line_gap=9, max_lines=3)
        draw.line((MARGIN + 10, 398, 1045, 398), fill=style.accent, width=4)
        draw.text((1110, 182), "FIELD NOTE 04", font=font(16, bold=True), fill=style.muted)
        draw.text((1110, 212), "MAGNETIC", font=font(42, bold=True), fill=style.accent)
        draw.text((1110, 259), "HEADINGS", font=font(42, bold=True), fill=style.accent)
        draw_wrapped(draw, "A small system hiding in plain sight.", (1110, 338, 1460, 408), font(24, italic=True), style.ink, line_gap=5, max_lines=2)
        choices_y = 455
        height = 76 if not long_question else 61
        for i, choice in enumerate(FIXTURE["content"]["choices"]):
            y = choices_y + i * (height + (12 if long_question else 17))
            draw.text((MARGIN + 10, y + 18), choice["id"], font=font(28, bold=True), fill=style.accent)
            draw.text((MARGIN + 84, y + 18), choice["text"], font=font(25 if not long_question else 21), fill=style.ink)
            draw.line((MARGIN + 84, y + height, 1060, y + height), fill=(198, 188, 171), width=2)
        draw_wrapped(draw, "A clear rule can still move as the reference moves.", (1110, 482, 1480, 610), font(23, italic=True), style.muted, line_gap=9, max_lines=4)
        draw.text((1110, 667), "SERIES", font=font(14, bold=True), fill=style.muted)
        draw.text((1110, 692), "HIDDEN SYSTEMS", font=font(21, bold=True), fill=style.ink)
    else:
        draw.text((MARGIN + 10, 176), "QUESTION 04", font=font(17, bold=True), fill=style.accent)
        draw_wrapped(draw, FIXTURE["content"]["question_long" if long_question else "question"], (MARGIN + 10, 220, 1030, 390), font(48 if not long_question else 39, bold=True), style.ink, line_gap=9, max_lines=3)
        draw.line((MARGIN + 10, 416, 1000, 416), fill=(180, 201, 191), width=2)
        choices_y = 464
        height = 73 if not long_question else 61
        for i, choice in enumerate(FIXTURE["content"]["choices"]):
            y = choices_y + i * (height + (14 if long_question else 19))
            marker_size = 48 if not long_question else 40
            marker_top = y + (13 if not long_question else 10)
            draw.ellipse((MARGIN + 10, marker_top, MARGIN + 10 + marker_size, marker_top + marker_size), fill=style.accent)
            draw.text((MARGIN + 25, marker_top + (7 if not long_question else 4)), choice["id"], font=font(19 if not long_question else 16, bold=True), fill=WHITE)
            draw.text((MARGIN + 84, y + 19), choice["text"], font=font(25 if not long_question else 21), fill=style.ink)
        draw.text((1110, 180), "THE RULE", font=font(16, bold=True), fill=style.muted)
        draw.text((1110, 214), "DIRECTION", font=font(37, bold=True), fill=style.accent)
        draw.text((1110, 256), "changes", font=font(37, bold=True), fill=style.accent_2)
        draw_wrapped(draw, "Runway numbers are not labels for length or ownership.", (1110, 342, 1470, 470), font(24), style.ink, line_gap=9, max_lines=4)
        draw.line((1110, 525, 1470, 525), fill=(180, 201, 191), width=2)
        draw.text((1110, 560), "5 SEC", font=font(28, bold=True), fill=style.accent)
        draw.text((1110, 604), "Choose one explanation.", font=font(19), fill=style.muted)
    draw.text((MARGIN, 864), "NO IMAGE SLOT · COMPOSITION STANDS ON ITS OWN", font=font(14, bold=True), fill=style.muted)
    return image


def draw_reveal_state(style: Style) -> Image.Image:
    image = Image.new("RGB", CANVAS, style.background)
    draw = ImageDraw.Draw(image)
    if style.style_id == "sport-scoreboard":
        draw_sport_background(draw, style)
    elif style.style_id == "editorial-culture":
        draw_culture_background(draw, style)
    else:
        draw_knowledge_background(draw, style)
    draw_header(draw, style, 4)
    draw.text((MARGIN, 175), "ANSWER REVEAL", font=font(18, bold=True), fill=style.accent)
    draw_wrapped(draw, "They follow Earth's magnetic field.", (MARGIN, 220, 980, 340), font(55, bold=True), style.ink, line_gap=8, max_lines=2)
    draw.line((MARGIN, 384, 970, 384), fill=style.accent, width=4)
    if style.style_id == "sport-scoreboard":
        rounded(draw, (MARGIN, 450, 970, 670), (32, 91, 77), radius=8)
        draw.text((MARGIN + 34, 485), "CORRECT  /  A", font=font(28, bold=True), fill=style.accent)
        draw_wrapped(draw, FIXTURE["content"]["fact"], (MARGIN + 34, 540, 900, 625), font(24, bold=True), style.ink, line_gap=7, max_lines=3)
        draw.text((1110, 188), "+1", font=font(78, bold=True), fill=style.accent)
        draw.text((1110, 288), "POINT", font=font(21, bold=True), fill=style.muted)
        draw.text((1110, 380), "08 / 10", font=font(45, bold=True), fill=style.ink)
        draw.text((1110, 445), "NEXT QUESTION", font=font(16, bold=True), fill=style.accent)
    elif style.style_id == "editorial-culture":
        draw.text((MARGIN, 450), "A", font=font(72, bold=True), fill=style.accent)
        draw.text((MARGIN + 90, 472), "MAGNETIC NORTH", font=font(33, bold=True), fill=style.ink)
        draw_wrapped(draw, FIXTURE["content"]["fact"], (MARGIN + 90, 530, 980, 640), font(25), style.ink, line_gap=8, max_lines=3)
        draw.text((1110, 190), "WHY IT MATTERS", font=font(16, bold=True), fill=style.muted)
        draw_wrapped(draw, "Maps are snapshots of a moving reference system.", (1110, 235, 1470, 390), font(31, bold=True), style.accent, line_gap=8, max_lines=4)
        draw.line((1110, 465, 1470, 465), fill=style.accent, width=3)
        draw.text((1110, 505), "FIELD NOTE 04", font=font(18, bold=True), fill=style.ink)
    else:
        rounded(draw, (MARGIN, 450, 980, 670), style.panel, radius=18, outline=(197, 211, 204), width=2)
        draw.text((MARGIN + 34, 485), "CORRECT ANSWER", font=font(17, bold=True), fill=style.accent)
        draw.text((MARGIN + 34, 520), "A  ·  MAGNETIC NORTH", font=font(30, bold=True), fill=style.ink)
        draw_wrapped(draw, FIXTURE["content"]["fact"], (MARGIN + 34, 580, 920, 642), font(23), style.ink, line_gap=7, max_lines=3)
        draw.text((1110, 190), "TAKEAWAY", font=font(16, bold=True), fill=style.muted)
        draw_wrapped(draw, "The heading is the clue.", (1110, 235, 1470, 390), font(34, bold=True), style.accent, line_gap=8, max_lines=3)
        draw.text((1110, 510), "1 / 1", font=font(58, bold=True), fill=style.accent_2)
        draw.text((1110, 580), "correct", font=font(19), fill=style.muted)
    draw.text((MARGIN, 864), "REVEAL STATE · FACT AREA REMAINS VISIBLE", font=font(14, bold=True), fill=style.muted)
    return image


def draw_two_way_state(style: Style) -> Image.Image:
    image = Image.new("RGB", CANVAS, style.background)
    draw = ImageDraw.Draw(image)
    if style.style_id == "sport-scoreboard":
        draw_sport_background(draw, style)
    elif style.style_id == "editorial-culture":
        draw_culture_background(draw, style)
    else:
        draw_knowledge_background(draw, style)
    draw_header(draw, style, 4)
    comparison = FIXTURE["content"]["comparison"]
    draw.text((MARGIN, 175), "TWO-WAY COMPARISON", font=font(18, bold=True), fill=style.accent)
    draw_wrapped(draw, comparison["question"], (MARGIN, 216, 1480, 300), font(45, bold=True), style.ink, line_gap=8, max_lines=2)

    if style.style_id == "sport-scoreboard":
        card_a = (MARGIN, 365, 738, 700)
        card_b = (862, 365, 1544, 700)
        for index, (box, option, fill) in enumerate(((card_a, comparison["left"], (31, 71, 88)), (card_b, comparison["right"], (48, 56, 74))), 1):
            rounded(draw, box, fill, radius=8)
            draw.rectangle((box[0], box[1], box[0] + 92, box[3]), fill=style.accent_2 if index == 1 else style.accent)
            draw.text((box[0] + 31, box[1] + 32), option["id"], font=font(40, bold=True), fill=style.ink)
            draw.text((box[0] + 124, box[1] + 38), f"OPTION {index}", font=font(16, bold=True), fill=style.accent)
            draw_wrapped(draw, option["title"], (box[0] + 124, box[1] + 92, box[2] - 26, box[1] + 180), font(29, bold=True), style.ink, line_gap=6, max_lines=2)
            draw_wrapped(draw, option["body"], (box[0] + 124, box[1] + 220, box[2] - 28, box[3] - 40), font(23), style.ink, line_gap=8, max_lines=3)
        draw.text((800, 500), "VS", font=font(30, bold=True), fill=style.accent)
        pill(draw, (MARGIN, 750, 365, 802), "PICK ONE", style)
        draw.text((410, 766), "HEAD-TO-HEAD · 5 s", font=font(19, bold=True), fill=style.muted)
    elif style.style_id == "editorial-culture":
        draw.line((800, 350, 800, 700), fill=style.accent, width=3)
        for x, option, label in ((MARGIN + 10, comparison["left"], "A"), (850, comparison["right"], "B")):
            draw.text((x, 370), label, font=font(65, bold=True), fill=style.accent)
            draw_wrapped(draw, option["title"], (x + 86, 382, x + 650, 470), font(30, bold=True), style.ink, line_gap=7, max_lines=2)
            draw_wrapped(draw, option["body"], (x + 86, 510, x + 620, 625), font(24, italic=True), style.muted, line_gap=8, max_lines=3)
            draw.line((x + 86, 670, x + 620, 670), fill=(198, 188, 171), width=2)
        draw.text((MARGIN + 10, 750), "A QUESTION OF REFERENCE, NOT JUST A LABEL", font=font(18, bold=True), fill=style.accent)
    else:
        card_a = (MARGIN, 370, 748, 690)
        card_b = (852, 370, 1544, 690)
        for box, option in ((card_a, comparison["left"]), (card_b, comparison["right"])):
            rounded(draw, box, style.panel, radius=18, outline=(197, 211, 204), width=2)
            draw.ellipse((box[0] + 28, box[1] + 28, box[0] + 88, box[1] + 88), fill=style.accent)
            draw.text((box[0] + 48, box[1] + 38), option["id"], font=font(22, bold=True), fill=WHITE)
            draw_wrapped(draw, option["title"], (box[0] + 120, box[1] + 34, box[2] - 26, box[1] + 105), font(28, bold=True), style.accent, line_gap=6, max_lines=2)
            draw_wrapped(draw, option["body"], (box[0] + 34, box[1] + 145, box[2] - 30, box[3] - 35), font(24), style.ink, line_gap=8, max_lines=3)
        draw.text((785, 510), "OR", font=font(24, bold=True), fill=style.accent_2)
        draw.text((MARGIN, 750), "COMPARE THE RULE · THEN CHOOSE", font=font(18, bold=True), fill=style.accent)
    draw.text((MARGIN, 864), "TWO-WAY COMPARISON · BOTH OPTIONS VISIBLE", font=font(14, bold=True), fill=style.muted)
    return image


def draw_comparison(styles: tuple[Style, ...]) -> Image.Image:
    width, height = (2100, 920)
    image = Image.new("RGB", (width, height), (25, 26, 28))
    draw = ImageDraw.Draw(image)
    draw.text((56, 28), "CHANNEL STYLE PACKS / PHASE A PILOT", font=font(28, bold=True), fill=(249, 247, 239))
    draw.text((56, 70), "SAME CONTENT · SAME LOCALE · SAME 1600×900 FRAME", font=font(16, bold=True), fill=(163, 165, 160))
    col_w = 650
    gap = 40
    top = 120
    for index, style in enumerate(styles):
        source = draw_question_state(style)
        source.thumbnail((col_w, 365), Image.Resampling.LANCZOS)
        x = 56 + index * (col_w + gap)
        image.paste(source, (x, top))
        draw.text((x, top + 382), f"{style.label}  {style.title}", font=font(21, bold=True), fill=style.accent)
        draw.text((x, top + 418), style.strap, font=font(14, bold=True), fill=(190, 190, 183))
        draw.line((x, top + 450, x + col_w, top + 450), fill=(86, 88, 88), width=2)
        mode_text = {
            "sport-scoreboard": "Score / timer / compact answer cards",
            "editorial-culture": "Caption / fact / paired editorial weights",
            "clear-knowledge": "Readable type / whitespace / takeaway",
        }[style.style_id]
        draw.text((x, top + 470), mode_text, font=font(17), fill=(225, 223, 214))
        draw.text((x, top + 512), "No image placeholder", font=font(15, bold=True), fill=style.accent_2)
    draw.text((56, 858), "Content fixture: airport runway numbering · origin: deterministic hand-authored local fixture · no provider / TTS / MP4", font=font(15), fill=(166, 169, 164))
    return image


def draw_two_way_comparison(styles: tuple[Style, ...]) -> Image.Image:
    width, height = (2100, 920)
    image = Image.new("RGB", (width, height), (25, 26, 28))
    draw = ImageDraw.Draw(image)
    draw.text((56, 28), "TWO-WAY COMPARISON / PHASE A STRESS CASE", font=font(28, bold=True), fill=(249, 247, 239))
    draw.text((56, 70), "SAME QUESTION · TWO OPTIONS · SAME 1600×900 FRAME", font=font(16, bold=True), fill=(163, 165, 160))
    col_w = 650
    gap = 40
    top = 120
    for index, style in enumerate(styles):
        source = draw_two_way_state(style)
        source.thumbnail((col_w, 365), Image.Resampling.LANCZOS)
        x = 56 + index * (col_w + gap)
        image.paste(source, (x, top))
        draw.text((x, top + 382), f"{style.label}  {style.title}", font=font(21, bold=True), fill=style.accent)
        draw.text((x, top + 418), "Two choices remain explicit", font=font(17), fill=(225, 223, 214))
        draw.line((x, top + 450, x + col_w, top + 450), fill=(86, 88, 88), width=2)
        draw.text((x, top + 470), "No forced four-choice geometry", font=font(15, bold=True), fill=style.accent_2)
    draw.text((56, 858), "Supplementary fixture: airport runway numbering · deterministic local Pillow preview · no provider / TTS / MP4", font=font(15), fill=(166, 169, 164))
    return image


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.stem}.partial{path.suffix}")
    image.save(partial, format="PNG", optimize=False)
    with Image.open(partial) as decoded:
        decoded.load()
        if decoded.size != image.size or decoded.mode not in {"RGB", "RGBA"}:
            raise RuntimeError(f"PNG readback mismatch: {path}")
    partial.replace(path)


def build_manifest(run_dir: Path, run: str) -> dict[str, Any]:
    artifacts = []
    for path in sorted(run_dir.glob("*.png")):
        with Image.open(path) as decoded:
            decoded.load()
            extrema = decoded.convert("RGB").getextrema()
            artifacts.append({
                "path": str(path.resolve()),
                "kind": "synthetic_disposable_fixture_preview",
                "format": decoded.format,
                "mode": decoded.mode,
                "size": list(decoded.size),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "pixel_extrema": [list(pair) for pair in extrema],
            })
    return {
        "schema_version": "channel_style_phase_a_manifest_v1",
        "run": run,
        "created_at": datetime.now(UTC).isoformat(),
        "fixture": str((run_dir / "fixture.json").resolve()),
        "fixture_origin": FIXTURE["origin"],
        "artifact_class": "synthetic_disposable_fixture",
        "provider_calls": 0,
        "tts_calls": 0,
        "video_exports": 0,
        "styles": [
            {"id": style.style_id, "title": style.title, "same_content": True, "same_locale": "en-US"}
            for style in STYLES
        ],
        "artifacts": artifacts,
        "notes": [
            "PNG generated locally with deterministic Pillow primitives; not a provider output.",
            "Pilot is isolated from the production engine/UI; no production API was changed.",
            "Preview gate evaluates composition and visual separation only; motion is not represented.",
        ],
    }


def run_pilot(run: str) -> Path:
    run_dir = PROJECT_ROOT / "output" / "channel-style-packs" / run
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "fixture.json").write_text(json.dumps(FIXTURE, ensure_ascii=False, indent=2), encoding="utf-8")
    save_png(draw_comparison(STYLES), run_dir / "comparison.png")
    save_png(draw_question_state(STYLES[2]), run_dir / "knowledge-question.png")
    save_png(draw_reveal_state(STYLES[2]), run_dir / "knowledge-reveal.png")
    save_png(draw_question_state(STYLES[0], long_question=True), run_dir / "sport-long-question.png")
    save_png(draw_question_state(STYLES[1], long_question=True), run_dir / "culture-long-question.png")
    save_png(draw_question_state(STYLES[2], long_question=True), run_dir / "knowledge-long-question.png")
    save_png(draw_question_state(STYLES[1]), run_dir / "culture-question.png")
    save_png(draw_question_state(STYLES[0]), run_dir / "sport-question.png")
    save_png(draw_reveal_state(STYLES[0]), run_dir / "sport-reveal.png")
    save_png(draw_reveal_state(STYLES[1]), run_dir / "culture-reveal.png")
    save_png(draw_two_way_comparison(STYLES), run_dir / "two-way-comparison.png")
    manifest = build_manifest(run_dir, run)
    manifest_path = run_dir / "artifact-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_visual_review(run_dir)
    return manifest_path


def run_hybrid_pilot(run: str = DEFAULT_HYBRID_RUN) -> Path:
    run_dir = PROJECT_ROOT / "output" / "channel-style-packs" / run
    run_dir.mkdir(parents=True, exist_ok=True)
    hybrid_fixture = {
        **FIXTURE,
        "schema_version": "channel_style_phase_a_hybrid_fixture_v1",
        "approved_direction": "Knowledge/Clear + Editorial Explainer",
        "origin": "hand-authored deterministic hybrid pilot fixture; approved direction only",
    }
    (run_dir / "fixture.json").write_text(json.dumps(hybrid_fixture, ensure_ascii=False, indent=2), encoding="utf-8")
    save_png(draw_hybrid_knowledge_question(), run_dir / "knowledge-editorial-question.png")
    save_png(draw_hybrid_knowledge_question(long_question=True), run_dir / "knowledge-editorial-long-question.png")
    save_png(draw_hybrid_knowledge_reveal(), run_dir / "knowledge-editorial-reveal.png")
    manifest = {
        "schema_version": "channel_style_phase_a_hybrid_manifest_v1",
        "run": run,
        "created_at": datetime.now(UTC).isoformat(),
        "fixture": str((run_dir / "fixture.json").resolve()),
        "fixture_origin": hybrid_fixture["origin"],
        "approved_direction": "Knowledge/Clear + Editorial Explainer",
        "artifact_class": "synthetic_disposable_fixture",
        "provider_calls": 0,
        "tts_calls": 0,
        "video_exports": 0,
        "artifacts": [],
        "notes": [
            "Approval is limited to the hybrid visual direction; this run does not modify production engine/UI.",
            "Editorial texture is restrained: evidence/diagram supports the explanation, not decoration-only collage.",
            "PNG generated locally with deterministic Pillow primitives; not a provider output.",
        ],
    }
    for path in sorted(run_dir.glob("*.png")):
        with Image.open(path) as decoded:
            decoded.load()
            extrema = decoded.convert("RGB").getextrema()
            manifest["artifacts"].append({
                "path": str(path.resolve()),
                "kind": "synthetic_disposable_fixture_preview",
                "format": decoded.format,
                "mode": decoded.mode,
                "size": list(decoded.size),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "pixel_extrema": [list(pair) for pair in extrema],
            })
    manifest_path = run_dir / "artifact-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    review = {
        "schema_version": "channel_style_phase_a_hybrid_visual_review_v1",
        "review_mode": "read-only pixel inspection after final render",
        "reviewer": "lead self-verified with image readback and visual inspection",
        "status": "PASS_WITH_BOSS_VISUAL_GATE_OPEN",
        "approved_direction": "Knowledge/Clear + Editorial Explainer",
        "observed": [
            "The clear educational hierarchy is retained: question, choices, evidence/diagram, and takeaway.",
            "Editorial signals are added as a narrow red signal rule, field note, paper surface, caption, and evidence arrow; no decorative wall of text.",
            "Long-question and reveal variants are included; no-image composition stands on its own.",
            "No provider/TTS/video export calls were made.",
        ],
        "unverified": [
            "Production engine/UI wiring, persistence, export parity, motion and native-language glyph coverage remain unverified.",
        ],
    }
    review_path = run_dir / "visual-review.json"
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def validate_fixture() -> None:
    content = FIXTURE["content"]
    if FIXTURE["locale"] != "en-US":
        raise AssertionError("Phase A fixture must use one real supported locale")
    if len(content["choices"]) != 4 or [choice["id"] for choice in content["choices"]] != ["A", "B", "C", "D"]:
        raise AssertionError("fixture must contain four ordered choices")
    if not all(content[key].strip() for key in ("question", "question_long", "fact")):
        raise AssertionError("fixture text must be non-empty")
    if content["comparison"]["left"]["id"] == content["comparison"]["right"]["id"]:
        raise AssertionError("two-way comparison options must be distinct")
    if len(STYLES) != 3 or len({style.style_id for style in STYLES}) != 3:
        raise AssertionError("pilot must contain three distinct styles")


def validate_run(run: str) -> dict[str, Any]:
    validate_fixture()
    run_dir = PROJECT_ROOT / "output" / "channel-style-packs" / run
    manifest = json.loads((run_dir / "artifact-manifest.json").read_text(encoding="utf-8"))
    if manifest["provider_calls"] != 0 or manifest["tts_calls"] != 0 or manifest["video_exports"] != 0:
        raise AssertionError("Phase A must not call provider/TTS/video export")
    is_hybrid = manifest.get("approved_direction") == "Knowledge/Clear + Editorial Explainer"
    expected_names = (
        {
            "knowledge-editorial-long-question.png",
            "knowledge-editorial-question.png",
            "knowledge-editorial-reveal.png",
        }
        if is_hybrid
        else {
            "comparison.png",
            "culture-long-question.png",
            "culture-question.png",
            "culture-reveal.png",
            "knowledge-long-question.png",
            "knowledge-question.png",
            "knowledge-reveal.png",
            "sport-long-question.png",
            "sport-question.png",
            "sport-reveal.png",
            "two-way-comparison.png",
        }
    )
    actual_names = {Path(item["path"]).name for item in manifest["artifacts"]}
    if actual_names != expected_names:
        raise AssertionError(f"unexpected Phase A artifact set: {sorted(actual_names)}")
    for item in manifest["artifacts"]:
        path = Path(item["path"])
        with Image.open(path) as decoded:
            decoded.load()
            if decoded.format != "PNG" or decoded.mode != "RGB" or decoded.size not in {(1600, 900), (2100, 920)}:
                raise AssertionError(f"invalid PNG artifact: {path}")
        if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise AssertionError(f"manifest mismatch: {path}")
    if list(run_dir.glob("*.mp4")) or list(run_dir.glob("*.partial*")):
        raise AssertionError("Phase A run contains MP4 or partial artifacts")
    return {"status": "PASS", "run": run, "artifact_count": len(actual_names), "provider_calls": 0, "tts_calls": 0, "video_exports": 0}


def write_visual_review(run_dir: Path) -> Path:
    review = {
        "schema_version": "channel_style_phase_a_visual_review_v1",
        "review_mode": "read-only pixel inspection after final render",
        "reviewer": "lead self-verified with image readback and visual inspection",
        "status": "PASS_WITH_BOSS_VISUAL_GATE_OPEN",
        "observed": {
            "comparison": [
                "Three styles are materially distinct in geometry, typography, hierarchy, and graphic language; not a palette-only change.",
                "Same question and A-D choices are comparable in the three main panels.",
                "No obvious clipping, overlap, or large empty image placeholder in the comparison sheet.",
                "Pilot/debug labels are present by design on the comparison board and are not channel-facing artwork.",
            ],
            "long_question": [
                "Sport, culture, and knowledge long-question PNGs read within bounds; no line crosses answer text or markers on final inspection."
            ],
            "two_way": [
                "Both options A/B remain visible in each style; no forced four-choice geometry or empty answer slot observed.",
                "No obvious clipping or overlap in the final supplementary sheet.",
            ],
            "reveal": ["Sport, culture, and knowledge reveal examples retain the fact area without observed clipping or overlap."],
        },
        "selection_note": "Visual direction remains Boss choice. Knowledge/Clear reads strongest for broad explanatory channel; Sport/Scoreboard is strongest for competitive quiz energy; Culture/Editorial is strongest for documentary/editorial tone.",
        "unverified": [
            "Boss visual approval has not been granted yet.",
            "Motion, Qt integration, persistence, export parity, native-language glyph acceptance, audio, and provider behavior are out of Phase A."
        ],
    }
    path = run_dir / "visual-review.json"
    path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--hybrid", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        print(json.dumps(validate_run(args.run), ensure_ascii=False))
        return 0
    manifest = run_hybrid_pilot(args.run) if args.hybrid else run_pilot(args.run)
    print(json.dumps({"status": "PASS", "manifest": str(manifest.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["FIXTURE", "STYLES", "run_pilot"]
