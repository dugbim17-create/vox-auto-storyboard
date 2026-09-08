"""Tests for P3-T03 Voice profiles.

Covers the acceptance criteria:

- validate file (exists + audio format);
- hash reference (SHA-256);
- không copy đè (profile references the file; the source file is untouched and
  not duplicated into the project);
- list profile.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.services.voice_profiles import (
    VoiceProfileError,
    VoiceProfileManager,
    discover_reference_samples,
    sha256_file,
)
from app.storage import database


def write_minimal_wav(path: Path, *, payload: bytes = b"\x00\x00" * 100) -> None:
    """Write a tiny valid 24kHz mono 16-bit WAV."""
    sample_rate = 24000
    bits = 16
    channels = 1
    block_align = channels * bits // 8
    byte_rate = sample_rate * block_align
    data_size = len(payload)
    header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVE" + b"fmt "
    header += struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, bits)
    header += b"data" + struct.pack("<I", data_size)
    path.write_bytes(header + payload)


@pytest.fixture()
def session(tmp_path: Path):
    database.reset_engine()
    engine = database.get_engine(f"sqlite:///{tmp_path}/test.db")
    database.init_schema(engine)
    factory = database.get_session_factory(engine)
    with factory() as s:
        yield s
    database.reset_engine()


@pytest.fixture()
def ref_wav(tmp_path: Path) -> Path:
    path = tmp_path / "ref.wav"
    write_minimal_wav(path)
    return path


def test_create_profile_validates_and_hashes(session, ref_wav) -> None:
    manager = VoiceProfileManager(session)
    profile = manager.create_profile(
        voice_profile_id="voice_vi_01",
        reference_audio_path=str(ref_wav),
        language="vi",
        seed=42,
        speed=1.0,
    )
    assert profile["voice_profile_id"] == "voice_vi_01"
    assert profile["reference_audio_path"] == str(ref_wav)
    assert profile["reference_hash"] == sha256_file(ref_wav)
    assert profile["language"] == "vi"
    assert profile["seed"] == 42


def test_create_profile_missing_file_raises(session, tmp_path) -> None:
    manager = VoiceProfileManager(session)
    with pytest.raises(VoiceProfileError):
        manager.create_profile(
            voice_profile_id="voice_x",
            reference_audio_path=str(tmp_path / "nope.wav"),
        )


def test_create_profile_unsupported_format_raises(session, tmp_path) -> None:
    bad = tmp_path / "ref.txt"
    bad.write_text("not audio", encoding="utf-8")
    manager = VoiceProfileManager(session)
    with pytest.raises(VoiceProfileError):
        manager.create_profile(
            voice_profile_id="voice_x",
            reference_audio_path=str(bad),
        )


def test_create_profile_does_not_copy_source(session, ref_wav, tmp_path) -> None:
    """'Không copy đè': the source file is referenced, not duplicated."""
    before = ref_wav.read_bytes()
    manager = VoiceProfileManager(session)
    manager.create_profile(
        voice_profile_id="voice_vi_01",
        reference_audio_path=str(ref_wav),
    )
    # Source untouched, no copy created anywhere under tmp_path except the original.
    assert ref_wav.read_bytes() == before
    assert len(list(tmp_path.rglob("ref*.wav"))) == 1


def test_upsert_updates_not_duplicates(session, ref_wav) -> None:
    manager = VoiceProfileManager(session)
    manager.create_profile(
        voice_profile_id="voice_vi_01",
        reference_audio_path=str(ref_wav),
        speed=1.0,
    )
    manager.create_profile(
        voice_profile_id="voice_vi_01",
        reference_audio_path=str(ref_wav),
        speed=1.2,
    )
    profiles = manager.list_profiles()
    assert len(profiles) == 1  # upsert, not duplicate
    assert profiles[0]["speed"] == 1.2


def test_list_profiles(session, ref_wav, tmp_path) -> None:
    manager = VoiceProfileManager(session)
    second = tmp_path / "ref2.wav"
    write_minimal_wav(second)
    manager.create_profile(voice_profile_id="voice_a", reference_audio_path=str(ref_wav))
    manager.create_profile(voice_profile_id="voice_b", reference_audio_path=str(second))

    ids = [p["voice_profile_id"] for p in manager.list_profiles()]
    assert sorted(ids) == ["voice_a", "voice_b"]


def test_get_profile(session, ref_wav) -> None:
    manager = VoiceProfileManager(session)
    manager.create_profile(voice_profile_id="voice_vi_01", reference_audio_path=str(ref_wav))
    profile = manager.get_profile("voice_vi_01")
    assert profile["voice_profile_id"] == "voice_vi_01"


def test_get_profile_missing_raises(session) -> None:
    manager = VoiceProfileManager(session)
    with pytest.raises(VoiceProfileError):
        manager.get_profile("voice_none")


def test_discover_reference_samples_returns_wavs() -> None:
    # Real discovery may or may not find samples on this machine; just assert
    # the function returns a list of .wav/.mp3 Paths when the dir exists.
    samples = discover_reference_samples()
    assert isinstance(samples, list)
    for s in samples:
        assert s.suffix.lower() in {".wav", ".mp3", ".flac", ".ogg", ".m4a"}


def test_sync_from_discovery_creates_profiles(session, monkeypatch) -> None:
    import tempfile
    from pathlib import Path as P

    samples_dir = P(tempfile.mkdtemp())
    s1 = samples_dir / "gioi_thieu_preview.wav"
    write_minimal_wav(s1)

    from app.services import voice_profiles as vp

    monkeypatch.setattr(vp, "_SAMPLE_DIR_CANDIDATES", [samples_dir])
    manager = VoiceProfileManager(session)
    created = manager.sync_from_discovery(prefix="voice_")
    assert created >= 1
    ids = [p["voice_profile_id"] for p in manager.list_profiles()]
    assert any("gioi_thieu" in i for i in ids)

    # Second sync: idempotent (no new profiles).
    created2 = manager.sync_from_discovery(prefix="voice_")
    assert created2 == 0
