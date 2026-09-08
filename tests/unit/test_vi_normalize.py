"""Tests for P3-T04 Vietnamese normalization.

Covers the acceptance criteria:

- số tiền (money);
- phần trăm (percentage);
- ngày (dates);
- URL;
- từ viết tắt (abbreviations);
- dấu câu (punctuation/whitespace);
- tên riêng override (proper-noun override list).
"""

from __future__ import annotations

from pathlib import Path

from app.services.vi_normalize import ViNormalizer, get_normalizer, normalize_vi


def test_money() -> None:
    assert normalize_vi("giá 50.000đ") == "giá năm mươi nghìn đồng"
    assert normalize_vi("mua 1.200.000 đồng") == "mua một triệu hai trăm nghìn đồng"


def test_percent() -> None:
    assert normalize_vi("tăng 25%") == "tăng hai mươi lăm phần trăm"
    assert normalize_vi("giảm 12.5%") == "giảm mười hai phẩy năm phần trăm"


def test_date() -> None:
    assert normalize_vi("họp vào 01/02/2024") == (
        "họp vào ngày một tháng hai năm hai không hai bốn"
    )
    assert normalize_vi("deadline 15-03-2025").startswith("deadline ngày mười lăm tháng ba")


def test_url() -> None:
    assert normalize_vi("truy cập www.example.com") == "truy cập example chấm com"
    assert normalize_vi("xem https://vietnam.vn") == "xem vietnam chấm vn"


def test_abbreviations() -> None:
    assert normalize_vi("chi phí 100 VND") == "chi phí 100 đồng"
    assert normalize_vi("TP HCM") == "thành phố Hồ Chí Minh"


def test_proper_names_kept() -> None:
    text = "Thủ đô là Hà Nội, đất nước Việt Nam"
    assert normalize_vi(text) == text


def test_proper_name_override_pronunciation() -> None:
    # Custom normalizer with a pronunciation override for a name.
    normalizer = ViNormalizer(
        Path("config/pronunciation_vi.json").resolve()
    )
    # The built-in list keeps Hà Nội verbatim; test a custom mapping.
    normalizer.proper_names["Hà Nội"] = "Thủ đô Hà Nội"
    out = normalizer.normalize("Đến Hà Nội")
    assert out == "Đến Thủ đô Hà Nội"


def test_punctuation_whitespace_normalized() -> None:
    assert normalize_vi("  Xin    chào  ,  bạn  ") == "Xin chào , bạn"
    assert normalize_vi("") == ""


def test_empty_input() -> None:
    assert normalize_vi("   ") == ""


def test_html_tags_stripped() -> None:
    assert normalize_vi("<b>Giá</b> 50.000đ") == "Giá năm mươi nghìn đồng"


def test_normalizer_config_load() -> None:
    normalizer = get_normalizer()
    assert "VND" in normalizer.abbreviations
    assert "Hà Nội" in normalizer.proper_names
    assert normalizer.currency_units.get("đ") == "đồng"
