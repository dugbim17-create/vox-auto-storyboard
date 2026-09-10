"""Exact-locale Piper voice registry and safe model/config resolution.

The registry is deliberately small and explicit: a country mode may use only a
voice whose Piper catalog locale matches the document locale. Missing models or
unknown custom voices fail closed instead of silently crossing countries.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

PIPER_ENGINE_SOURCE = "https://github.com/OHF-Voice/piper1-gpl"
PIPER_VOICES_SOURCE = "https://huggingface.co/rhasspy/piper-voices"
PIPER_CATALOG_SOURCE = "https://huggingface.co/rhasspy/piper-voices/raw/main/voices.json"


@dataclass(frozen=True)
class PiperVoiceSpec:
    voice_id: str
    locale: str
    piper_locale: str
    quality: str
    catalog_path: str
    model_card_url: str


# Exact-locale defaults selected for this finite acceptance matrix. The model
# cards and hashes are recorded in the live acceptance output, not guessed here.
VOICE_SPECS: dict[str, PiperVoiceSpec] = {
    "de-DE": PiperVoiceSpec(
        "de_DE-thorsten-high", "de-DE", "de_DE", "high",
        "de/de_DE/thorsten/high",
        f"{PIPER_VOICES_SOURCE}/resolve/main/de/de_DE/thorsten/high/MODEL_CARD",
    ),
    "fr-FR": PiperVoiceSpec(
        "fr_FR-siwis-medium", "fr-FR", "fr_FR", "medium",
        "fr/fr_FR/siwis/medium",
        f"{PIPER_VOICES_SOURCE}/resolve/main/fr/fr_FR/siwis/medium/MODEL_CARD",
    ),
    "it-IT": PiperVoiceSpec(
        "it_IT-serena-high", "it-IT", "it_IT", "high",
        "it/it_IT/serena/high",
        f"{PIPER_VOICES_SOURCE}/resolve/main/it/it_IT/serena/high/MODEL_CARD",
    ),
    "en-US": PiperVoiceSpec(
        "en_US-ryan-high", "en-US", "en_US", "high",
        "en/en_US/ryan/high",
        f"{PIPER_VOICES_SOURCE}/resolve/main/en/en_US/ryan/high/MODEL_CARD",
    ),
    "en-GB": PiperVoiceSpec(
        "en_GB-cori-high", "en-GB", "en_GB", "high",
        "en/en_GB/cori/high",
        f"{PIPER_VOICES_SOURCE}/resolve/main/en/en_GB/cori/high/MODEL_CARD",
    ),
    "vi-VN": PiperVoiceSpec(
        "vi_VN-vais1000-medium", "vi-VN", "vi_VN", "medium",
        "vi/vi_VN/vais1000/medium",
        f"{PIPER_VOICES_SOURCE}/resolve/main/vi/vi_VN/vais1000/medium/MODEL_CARD",
    ),
    "ko-KR": PiperVoiceSpec(
        "ko_KR-kss-medium", "ko-KR", "ko_KR", "medium",
        "ko/ko_KR/kss/medium",
        f"{PIPER_VOICES_SOURCE}/resolve/main/ko/ko_KR/kss/medium/MODEL_CARD",
    ),
    "es-ES": PiperVoiceSpec(
        "es_ES-davefx-medium", "es-ES", "es_ES", "medium",
        "es/es_ES/davefx/medium",
        f"{PIPER_VOICES_SOURCE}/resolve/main/es/es_ES/davefx/medium/MODEL_CARD",
    ),
    "es-MX": PiperVoiceSpec(
        "es_MX-claude-high", "es-MX", "es_MX", "high",
        "es/es_MX/claude/high",
        f"{PIPER_VOICES_SOURCE}/resolve/main/es/es_MX/claude/high/MODEL_CARD",
    ),
}

_PROFILE_DEFAULTS = {
    "de-football": "de-DE",
    "de-wissen": "de-DE",
    "fr-culture": "fr-FR",
    "it-calcio": "it-IT",
}


class PiperVoiceError(ValueError):
    """Raised when exact-locale Piper selection or assets are invalid."""


def canonical_locale(locale: str | None) -> str:
    value = str(locale or "").strip().replace("_", "-")
    aliases = {"en": "en-US", "vi": "vi-VN", "de": "de-DE", "fr": "fr-FR", "it": "it-IT"}
    return aliases.get(value, value)


def voice_spec_for_locale(locale: str | None) -> PiperVoiceSpec:
    key = canonical_locale(locale)
    try:
        return VOICE_SPECS[key]
    except KeyError as exc:
        raise PiperVoiceError(f"No Piper voice is registered for exact locale: {locale}") from exc


def voice_spec_for_id(voice_id: str) -> PiperVoiceSpec | None:
    return next((item for item in VOICE_SPECS.values() if item.voice_id == voice_id), None)


def default_voice_for_document(*, locale: str | None, channel_profile: str = "") -> str:
    if channel_profile in _PROFILE_DEFAULTS:
        locale = _PROFILE_DEFAULTS[channel_profile]
    return voice_spec_for_locale(locale).voice_id


def resolve_requested_voice(
    *, locale: str | None, requested_voice: str | None, strict: bool
) -> str:
    """Return an exact-locale voice, or raise rather than silently switching."""
    requested = str(requested_voice or "").strip()
    if not requested:
        return default_voice_for_document(locale=locale)
    spec = voice_spec_for_id(requested)
    if spec is None:
        if strict:
            raise PiperVoiceError(
                f"Voice '{requested}' is not an exact-locale catalog voice for {canonical_locale(locale)}"
            )
        return requested
    if canonical_locale(spec.locale) != canonical_locale(locale):
        raise PiperVoiceError(
            f"Voice locale mismatch: {requested} is {spec.locale}, document requires {canonical_locale(locale)}"
        )
    return requested


def _candidate_model_paths(model_root: Path, spec: PiperVoiceSpec) -> list[Path]:
    filename = f"{spec.voice_id}.onnx"
    candidates = [
        model_root / spec.locale / filename,
        model_root / spec.piper_locale / filename,
        model_root / filename,
    ]
    if model_root.is_dir():
        candidates.extend(sorted(model_root.rglob(filename)))
    return candidates


def resolve_voice_assets(
    model_root: Path | str, *, locale: str | None, voice_id: str | None = None, strict: bool = True
) -> dict[str, Any]:
    root = Path(model_root).expanduser()
    selected = resolve_requested_voice(locale=locale, requested_voice=voice_id, strict=strict)
    spec = voice_spec_for_id(selected)
    if spec is None:
        model = root / f"{selected}.onnx"
        config = model.with_suffix(".onnx.json")
    else:
        model = next((path for path in _candidate_model_paths(root, spec) if path.is_file()), root / f"{selected}.onnx")
        config = model.with_suffix(".onnx.json")
    if not model.is_file() or not config.is_file():
        raise PiperVoiceError(
            f"Piper model/config missing for locale {canonical_locale(locale)}: "
            f"model={model}; config={config}; no voice fallback allowed"
        )
    try:
        config_data = json.loads(config.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise PiperVoiceError(f"Piper config is not valid JSON: {config}") from exc
    expected = spec.piper_locale if spec is not None else None
    actual = str((config_data.get("language") or {}).get("code") or "")
    if expected and actual and actual != expected:
        raise PiperVoiceError(
            f"Piper config locale mismatch: {config} declares {actual}, expected {expected}"
        )
    return {
        "voice_id": selected,
        "locale": canonical_locale(locale),
        "model_path": model.resolve(),
        "config_path": config.resolve(),
        "config": config_data,
        "spec": spec,
    }


__all__ = [
    "PIPER_CATALOG_SOURCE",
    "PIPER_ENGINE_SOURCE",
    "PIPER_VOICES_SOURCE",
    "PiperVoiceError",
    "PiperVoiceSpec",
    "VOICE_SPECS",
    "canonical_locale",
    "default_voice_for_document",
    "resolve_requested_voice",
    "resolve_voice_assets",
    "voice_spec_for_id",
    "voice_spec_for_locale",
]
