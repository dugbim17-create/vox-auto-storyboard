"""Tests for subtitle_generator (P8-T01)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.subtitle_generator import (
    MIN_SUBTITLE_MS,
    SceneNarration,
    SubtitleEntry,
    SubtitleGenerator,
    SubtitleGeneratorError,
    _format_srt_time,
    allocate_timing,
    entries_to_srt,
    split_narration_chunks,
    wrap_subtitle_lines,
)


# ------------------------------------------------------------------ #
# split_narration_chunks
# ------------------------------------------------------------------ #
class TestSplitNarration:
    def test_empty(self):
        assert split_narration_chunks("") == []
        assert split_narration_chunks("   ") == []

    def test_single_sentence(self):
        chunks = split_narration_chunks("Xin chào tất cả.")
        assert len(chunks) >= 1
        assert "Xin chào" in chunks[0]

    def test_multi_sentence(self):
        text = "Câu một. Câu hai! Câu ba? Câu bốn."
        chunks = split_narration_chunks(text)
        assert len(chunks) == 4

    def test_long_chunk_broken(self):
        long = "a " * 100  # > MAX_CHARS_PER_LINE * MAX_LINES
        chunks = split_narration_chunks(long.strip())
        assert all(len(c) <= 84 + 10 for c in chunks)  # tolerance for word boundary


# ------------------------------------------------------------------ #
# wrap_subtitle_lines
# ------------------------------------------------------------------ #
class TestWrapLines:
    def test_short(self):
        assert wrap_subtitle_lines("Hello") == "Hello"

    def test_wrap_at_midpoint(self):
        text = "Đây là một câu dài cần được ngắt ra thành hai dòng riêng biệt"
        result = wrap_subtitle_lines(text)
        lines = result.split("\n")
        assert len(lines) <= 2


# ------------------------------------------------------------------ #
# allocate_timing
# ------------------------------------------------------------------ #
class TestAllocateTiming:
    def test_proportional(self):
        chunks = ["short", "a longer chunk here"]
        entries = allocate_timing(chunks, 5000)
        assert len(entries) == 2
        assert entries[0].start_ms == 0
        assert entries[-1].end_ms <= 5000 + 100  # rounding tolerance
        # Longer chunk should get more time.
        dur0 = entries[0].end_ms - entries[0].start_ms
        dur1 = entries[1].end_ms - entries[1].start_ms
        assert dur1 > dur0

    def test_minimum_duration(self):
        chunks = ["a", "b", "c"]
        entries = allocate_timing(chunks, 1500)
        for e in entries:
            dur = e.end_ms - e.start_ms
            # May be slightly less due to scaling, but not below ~500ms
            assert dur >= MIN_SUBTITLE_MS * 0.5

    def test_empty(self):
        assert allocate_timing([], 5000) == []

    def test_offset(self):
        entries = allocate_timing(["hello"], 3000, offset_ms=1000)
        assert entries[0].start_ms == 1000


# ------------------------------------------------------------------ #
# SRT formatting
# ------------------------------------------------------------------ #
class TestSRTFormat:
    def test_format_time_zero(self):
        assert _format_srt_time(0) == "00:00:00,000"

    def test_format_time_complex(self):
        # 1h 2m 3s 456ms = 3_723_456ms
        assert _format_srt_time(3_723_456) == "01:02:03,456"

    def test_entries_to_srt(self):
        entries = [
            SubtitleEntry(1, 0, 2000, "Xin chào"),
            SubtitleEntry(2, 2000, 5000, "Thế giới"),
        ]
        srt = entries_to_srt(entries)
        assert "1\n" in srt
        assert "00:00:00,000 --> 00:00:02,000" in srt
        assert "Xin chào" in srt
        assert "Thế giới" in srt

    def test_valid_srt_structure(self):
        entries = [SubtitleEntry(1, 0, 1000, "Test")]
        srt = entries_to_srt(entries)
        lines = srt.strip().split("\n")
        assert lines[0] == "1"
        assert "-->" in lines[1]
        assert lines[2] == "Test"


# ------------------------------------------------------------------ #
# SubtitleGenerator end-to-end
# ------------------------------------------------------------------ #
class TestSubtitleGenerator:
    def test_generate_basic(self, tmp_path: Path):
        gen = SubtitleGenerator()
        scenes = [
            SceneNarration("scene_001", "Xin chào. Đây là video.", 5000, order=1),
            SceneNarration("scene_002", "Cảm ơn đã xem!", 3000, order=2),
        ]
        result = gen.generate("prj_test", scenes, tmp_path / "subs.srt")
        assert result.entry_count >= 2
        assert result.total_duration_ms > 0
        srt = Path(result.srt_path).read_text(encoding="utf-8")
        assert "-->" in srt
        assert "Xin chào" in srt

    def test_empty_narration_skipped(self, tmp_path: Path):
        gen = SubtitleGenerator()
        scenes = [
            SceneNarration("scene_001", "", 3000, order=1),
            SceneNarration("scene_002", "Có text.", 2000, order=2),
        ]
        result = gen.generate("prj_test", scenes, tmp_path / "subs.srt")
        # Only scene_002 produces entries.
        assert result.entry_count >= 1

    def test_no_scenes_raises(self, tmp_path: Path):
        gen = SubtitleGenerator()
        with pytest.raises(SubtitleGeneratorError, match="no scenes"):
            gen.generate("prj_test", [], tmp_path / "subs.srt")

    def test_vietnamese_diacritics(self, tmp_path: Path):
        gen = SubtitleGenerator()
        scenes = [
            SceneNarration(
                "scene_001",
                "Việt Nam là đất nước tươi đẹp, với bờ biển dài và núi non hùng vĩ.",
                6000,
                order=1,
            ),
        ]
        result = gen.generate("prj_test", scenes, tmp_path / "subs.srt")
        srt = Path(result.srt_path).read_text(encoding="utf-8")
        assert "Việt Nam" in srt

    def test_full_narration_covered(self, tmp_path: Path):
        """All narration text appears somewhere in the SRT output."""
        gen = SubtitleGenerator()
        text = "Câu một. Câu hai. Câu ba."
        scenes = [SceneNarration("s1", text, 9000, order=1)]
        result = gen.generate("prj_test", scenes, tmp_path / "subs.srt")
        srt = Path(result.srt_path).read_text(encoding="utf-8")
        for word in ["Câu một", "Câu hai", "Câu ba"]:
            assert word in srt

    def test_no_overlap(self, tmp_path: Path):
        gen = SubtitleGenerator()
        scenes = [
            SceneNarration("s1", "A. B. C. D.", 4000, order=1),
            SceneNarration("s2", "E. F.", 3000, order=2),
        ]
        result = gen.generate("prj_test", scenes, tmp_path / "subs.srt")
        srt = Path(result.srt_path).read_text(encoding="utf-8")
        # Parse all timestamps and verify non-overlapping.
        import re
        times = re.findall(r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})", srt)
        prev_end = -1
        for start_s, end_s in times:
            start_ms = _parse_srt_ms(start_s)
            end_ms = _parse_srt_ms(end_s)
            assert start_ms >= prev_end, f"overlap: {start_s} starts before previous end"
            assert end_ms > start_ms
            prev_end = end_ms

    def test_valid_timestamps(self, tmp_path: Path):
        gen = SubtitleGenerator()
        scenes = [SceneNarration("s1", "Test subtitle.", 5000, order=1)]
        result = gen.generate("prj_test", scenes, tmp_path / "subs.srt")
        srt = Path(result.srt_path).read_text(encoding="utf-8")
        import re
        times = re.findall(r"(\d{2}:\d{2}:\d{2},\d{3})", srt)
        assert len(times) >= 2  # at least start + end


def _parse_srt_ms(ts: str) -> int:
    """Parse ``HH:MM:SS,mmm`` to ms."""
    parts = ts.replace(",", ":").split(":")
    h, m, s, ms = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
    return h * 3600000 + m * 60000 + s * 1000 + ms
