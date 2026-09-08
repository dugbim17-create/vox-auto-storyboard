"""Voice profile management (P3-T03).

Profiles reference a reference-audio file on disk (the OmniVoice samples dir or
a user path). We validate the file exists and is a known audio format, compute a
SHA-256 of the reference audio, and store it in the DB — we never copy the audio
into the project ("không copy đè"). Profiles are unique by
``voice_profile_id``.

A voice profile:

.. code-block:: json

    {
      "voice_profile_id": "voice_vi_01",
      "reference_audio_path": "voices/ref.wav",
      "language": "vi",
      "seed": 42,
      "speed": 1.0
    }
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from app.storage.repositories import VoiceProfileRepo

logger = logging.getLogger(__name__)

# Acceptable reference-audio extensions for OmniVoice cloning.
_AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}

# Discovery candidates for the OmniVoice reference-samples dir (P0-T06).
_SAMPLE_DIR_CANDIDATES = [
    Path(r"D:\ALL AI\VScode\voice-clone-tool\out\export\samples"),
]


class VoiceProfileError(Exception):
    """Raised on invalid profile input."""


def discover_reference_samples() -> list[Path]:
    """Return reference audio files from the OmniVoice samples dirs."""
    found: list[Path] = []
    for directory in _SAMPLE_DIR_CANDIDATES:
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.suffix.lower() in _AUDIO_EXTS:
                found.append(path)
    return found


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class VoiceProfileManager:
    """CRUD for voice profiles over the SQLite store."""

    def __init__(self, session: Any) -> None:
        self.session = session

    def create_profile(
        self,
        *,
        voice_profile_id: str,
        reference_audio_path: str,
        language: str = "vi",
        seed: int = 42,
        speed: float = 1.0,
    ) -> dict:
        """Create or update a voice profile (upsert by id).

        Validates the reference audio file exists and is a known format, then
        hashes it. The file is NOT copied (profile stores the reference path).
        """
        path = Path(reference_audio_path).expanduser()
        if not path.is_file():
            raise VoiceProfileError(f"reference audio not found: {reference_audio_path}")
        if path.suffix.lower() not in _AUDIO_EXTS:
            raise VoiceProfileError(
                f"unsupported audio format: {path.suffix or '(none)'} "
                f"(expected one of {sorted(_AUDIO_EXTS)})"
            )

        digest = sha256_file(path)
        profile = VoiceProfileRepo.upsert(
            self.session,
            voice_profile_id=voice_profile_id,
            reference_audio_path=str(path),
            reference_hash=digest,
            language=language,
            seed=seed,
            speed=speed,
        )
        self.session.commit()
        return _profile_dict(profile)

    def get_profile(self, voice_profile_id: str) -> dict:
        profile = VoiceProfileRepo.get(self.session, voice_profile_id)
        if profile is None:
            raise VoiceProfileError(f"voice profile not found: {voice_profile_id}")
        return _profile_dict(profile)

    def list_profiles(self) -> list[dict]:
        return [_profile_dict(p) for p in VoiceProfileRepo.list(self.session)]

    def sync_from_discovery(self, prefix: str = "voice_") -> int:
        """Create default profiles for every discovered reference sample.

        Profile ids are derived from the sample stem (slugified). To keep them
        unique even when two samples share a stem (e.g. ``ngochuyen (1).wav``
        and ``ngochuyen (1).mp3``), a short SHA-256 suffix is appended. The
        suffix depends only on the file content, so re-running is idempotent.
        Returns the number of profiles created.
        """
        created = 0
        for sample in discover_reference_samples():
            digest = sha256_file(sample)
            stem = _slugify(sample.stem)
            profile_id = f"{prefix}{stem}_{digest[:8]}"
            try:
                existing = VoiceProfileRepo.get(self.session, profile_id)
                if existing is None:
                    VoiceProfileRepo.upsert(
                        self.session,
                        voice_profile_id=profile_id,
                        reference_audio_path=str(sample),
                        reference_hash=digest,
                        language="vi",
                        seed=42,
                        speed=1.0,
                    )
                    created += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("skip profile %s: %s", profile_id, exc)
        self.session.commit()
        return created


def _profile_dict(profile: Any) -> dict:
    return {
        "voice_profile_id": profile.voice_profile_id,
        "reference_audio_path": profile.reference_audio_path,
        "reference_hash": profile.reference_hash,
        "language": profile.language,
        "seed": profile.seed,
        "speed": profile.speed,
    }


def _slugify(value: str) -> str:
    """Lowercase, replace non-alphanumerics with underscores, trim."""
    out = []
    for ch in value.lower():
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    slug = "".join(out)
    slug = "_".join(slug.split("_"))
    return slug.strip("_") or "sample"


def load_voice_presets_json() -> list[dict]:
    """Load ``voice_presets.json`` from the tool if present (best-effort)."""
    for candidate in _SAMPLE_DIR_CANDIDATES:
        presets = candidate.parent / "voice_presets.json"
        if presets.is_file():
            try:
                data = json.loads(presets.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                logger.warning("voice_presets.json unparseable: %s", presets)
    return []
