"""Vietnamese text normalization for TTS (P3-T04).

Reads ``config/pronunciation_vi.json`` (the pronunciation dictionary) and turns
raw narration into TTS-friendly Vietnamese. Applied before calling the OmniVoice
worker so the synthesized speech reads numbers, money, dates, URLs and
abbreviations correctly.

Transforms:

- whitespace normalization;
- money: ``50.000đ`` -> ``năm mươi nghìn đồng``;
- percentage: ``25%`` -> ``hai mươi lăm phần trăm``;
- dates: ``01/02/2024`` -> ``ngày một tháng hai năm 2024`` (spoken year);
- URLs: ``https://example.com`` -> ``example chấm com``;
- abbreviations: dictionary expansion (``VND`` -> ``đồng``);
- proper nouns: kept verbatim via the override list.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app import config as _discovery

REPO_ROOT = _discovery.REPO_ROOT
PRONUNCIATION_CONFIG = REPO_ROOT / "config" / "pronunciation_vi.json"

_TAG_RE = re.compile(r"<[a-zA-Z/][^>]*>")
# 12.5%, 25%, 3,5%
_PERCENT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
# 50.000đ / 50.000 đ / 1.200.000 đồng (thousands-separated integers)
_MONEY_RE = re.compile(r"(\d{1,3}(?:\.\d{3})+)\s*(đ|đồng)\b", re.IGNORECASE)
# dd/mm/yyyy or dd-mm-yyyy
_DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
# bare integers (thousands separated or plain) not preceded by digit
_NUMBER_RE = re.compile(r"(?<!\d)\d{1,3}(?:[.,]\d{3})+(?!\d)")
_URL_RE = re.compile(
    r"\b(?:https?://|www\.)?[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?:/[^\s.,!?;:)]*)?"
)

_DIGITS = {
    "0": "không", "1": "một", "2": "hai", "3": "ba", "4": "bốn",
    "5": "năm", "6": "sáu", "7": "bảy", "8": "tám", "9": "chín",
}
_UNITS = ["", "nghìn", "triệu", "tỷ"]
_TENS = {
    "2": "hai mươi", "3": "ba mươi", "4": "bốn mươi", "5": "năm mươi",
    "6": "sáu mươi", "7": "bảy mươi", "8": "tám mươi", "9": "chín mươi",
}


class ViNormalizer:
    """Normalizer holding the pronunciation dictionary."""

    def __init__(self, config_path: Path | None = None) -> None:
        path = config_path or PRONUNCIATION_CONFIG
        data = _load_json(path)
        self.abbreviations: dict[str, str] = data.get("abbreviations", {})
        self.proper_names: dict[str, str] = data.get("proper_names", {})
        self.currency_units: dict[str, str] = data.get("currency", {})

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #
    def normalize(self, text: str) -> str:
        """Apply all normalization passes in dependency order."""
        if not text:
            return text
        out = text
        out = _TAG_RE.sub(" ", out)
        out = self._expand_proper_names(out)
        out = self._expand_abbreviations(out)
        out = _PERCENT_RE.sub(lambda m: f"{_read_number(m.group(1))} phần trăm", out)
        out = self._money(out)
        out = _DATE_RE.sub(_replace_date, out)
        out = _NUMBER_RE.sub(_replace_number, out)
        out = _URL_RE.sub(_replace_url, out)
        return " ".join(out.split())

    # ------------------------------------------------------------------ #
    # Passes
    # ------------------------------------------------------------------ #
    def _expand_proper_names(self, text: str) -> str:
        for name, reading in self.proper_names.items():
            text = re.sub(rf"\b{re.escape(name)}\b", reading, text)
        return text

    def _expand_abbreviations(self, text: str) -> str:
        for abbr, reading in self.abbreviations.items():
            text = re.sub(rf"\b{re.escape(abbr)}\b", reading, text)
        return text

    def _money(self, text: str) -> str:
        def _m(m: re.Match) -> str:
            amount = m.group(1)
            unit = m.group(2)
            unit_word = self.currency_units.get(unit.lower(), unit)
            return f"{_read_number(amount)} {unit_word}"

        return _MONEY_RE.sub(_m, text)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_absolute():
        path = REPO_ROOT / path
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _read_number(value: str) -> str:
    """Read a number into Vietnamese words.

    Handles plain integers, thousands separators (``50.000``), and a single
    decimal (``12.5`` -> ``mười hai phẩy năm``).
    """
    value = value.strip().replace(" ", "")
    if "." in value or "," in value:
        sep = "." if "." in value else ","
        # thousands separators have exactly 3 digits after; a decimal has 1+.
        parts = value.split(sep)
        if len(parts) == 2 and len(parts[1]) <= 3 and len(parts[1]) != 3:
            int_part, dec_part = parts
            return f"{_read_int(int_part)} phẩy {_read_dec(dec_part)}"
        # otherwise treat separators as thousands group
        clean = value.replace(sep, "")
        return _read_int(clean)
    return _read_int(value)


def _read_dec(value: str) -> str:
    return " ".join(_DIGITS[ch] for ch in value if ch in _DIGITS)


def _read_int(value: str) -> str:
    """Read an integer into Vietnamese words (up to a few hundred trillion)."""
    value = value.lstrip("0") or "0"
    if value == "0":
        return "không"
    # group into triples from the right
    groups: list[str] = []
    while value:
        groups.append(value[-3:])
        value = value[:-3]
    words: list[str] = []
    order = len(groups)
    for idx, triple in enumerate(reversed(groups)):
        word = _read_triple(triple)
        scale = _UNITS[order - idx - 1]
        if word != "không" or scale == "":
            words.append(word)
            if scale:
                words.append(scale)
        elif idx < len(groups) - 1:
            words.append("không")
            if scale:
                words.append(scale)
    return _join_words(words)


def _read_triple(triple: str) -> str:
    triple = triple.zfill(3)
    h, t, o = triple[0], triple[1], triple[2]
    parts: list[str] = []
    if h != "0":
        parts.append(_DIGITS[h])
        parts.append("trăm")
    if t == "1":
        parts.append("mười")
        if o == "1":
            parts.append("một")
        elif o == "5":
            parts.append("lăm")
        elif o != "0":
            parts.append(_DIGITS[o])
    elif t != "0":
        parts.append(_TENS[t])
        if o == "1":
            parts.append("mốt")
        elif o == "5":
            parts.append("lăm")
        elif o != "0":
            parts.append(_DIGITS[o])
    elif o != "0":
        parts.append(_DIGITS[o])
    return _join_words(parts)


def _join_words(words: list[str]) -> str:
    return " ".join(w for w in words if w)


def _replace_date(m: re.Match) -> str:
    d, mo, y = m.group(1), m.group(2), m.group(3)
    return f"ngày {_read_number(d)} tháng {_read_number(mo)} năm {_read_year(y)}"


def _read_year(year: str) -> str:
    return " ".join(_DIGITS[ch] for ch in year if ch in _DIGITS)


def _replace_number(m: re.Match) -> str:
    return _read_number(m.group(0))


def _replace_url(m: re.Match) -> str:
    url = m.group(0)
    host = url
    for prefix in ("https://", "http://", "www."):
        if host.lower().startswith(prefix):
            host = host[len(prefix):]
    host = host.split("/")[0].split("?")[0]
    tokens = [t for t in re.split(r"[.\-]", host) if t]
    return " chấm ".join(tokens)


_default_normalizer: ViNormalizer | None = None


def get_normalizer() -> ViNormalizer:
    global _default_normalizer
    if _default_normalizer is None:
        _default_normalizer = ViNormalizer()
    return _default_normalizer


def normalize_vi(text: str) -> str:
    """Convenience wrapper using the shared normalizer."""
    return get_normalizer().normalize(text)
