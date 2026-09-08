"""Subtitle generator (P8-T01).

Generates SRT subtitle files from scene narrations + voice durations.

Strategy (MASTER_PLAN section 13.1 — fallback timing):

- split narration by punctuation chunks;
- allocate time proportionally by character weight;
- minimum subtitle duration: 700 ms;
- maximum 2 lines;
- maximum ~42 chars per line (for 16:9).

The generator does NOT require word-level timestamps from OmniVoice —
it uses the scene's ``actual_voice_duration_ms`` and distributes timing
across punctuation-split chunks.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from app.schemas.timeline import ProjectTimeline

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------- #
MIN_SUBTITLE_MS = 700
MAX_CHARS_PER_LINE = 42
MAX_LINES = 2
LEAD_IN_MS = 120   # match MASTER_PLAN section 12.2
LEAD_OUT_MS = 220

# Regex to split on sentence-ending punctuation, keeping the delimiter.
_PUNCT_SPLIT = re.compile(r'(?<=[.!?;:,，。！？；：、\n])\s*')


class SubtitleGeneratorError(Exception):
    """Raised when subtitle generation fails."""


@dataclass
class SubtitleEntry:
    """One SRT block."""
    index: int
    start_ms: int
    end_ms: int
    text: str


@dataclass
class SubtitleResult:
    """Result of generating subtitles for a project."""
    project_id: str
    srt_path: str
    entry_count: int
    total_duration_ms: int


# --------------------------------------------------------------------- #
# Core logic
# --------------------------------------------------------------------- #
def split_narration_chunks(narration: str) -> list[str]:
    """Split narration text into subtitle-sized chunks.

    Uses punctuation boundaries and enforces MAX_CHARS_PER_LINE * MAX_LINES
    as the max chunk size.
    """
    if not narration or not narration.strip():
        return []

    raw_chunks = _PUNCT_SPLIT.split(narration.strip())
    chunks: list[str] = []
    for raw in raw_chunks:
        raw = raw.strip()
        if not raw:
            continue
        max_chunk = MAX_CHARS_PER_LINE * MAX_LINES
        if len(raw) <= max_chunk:
            chunks.append(raw)
        else:
            # Hard-break long chunks at word boundaries.
            words = raw.split()
            current = ""
            for word in words:
                candidate = f"{current} {word}".strip() if current else word
                if len(candidate) > max_chunk:
                    if current:
                        chunks.append(current)
                    current = word
                else:
                    current = candidate
            if current:
                chunks.append(current)
    return chunks


def wrap_subtitle_lines(text: str, max_chars: int = MAX_CHARS_PER_LINE) -> str:
    """Wrap a subtitle chunk into at most MAX_LINES lines."""
    if len(text) <= max_chars:
        return text
    # Try to split at roughly the midpoint at a word boundary.
    words = text.split()
    mid = len(text) // 2
    best_split = len(words)
    best_diff = len(text)
    running = 0
    for i, w in enumerate(words):
        running += len(w) + (1 if i > 0 else 0)
        diff = abs(running - mid)
        if diff < best_diff:
            best_diff = diff
            best_split = i + 1
    line1 = " ".join(words[:best_split])
    line2 = " ".join(words[best_split:])
    if line2:
        return f"{line1}\n{line2}"
    return line1


def allocate_timing(
    chunks: list[str],
    total_ms: int,
    offset_ms: int = 0,
) -> list[SubtitleEntry]:
    """Allocate timing to chunks proportionally by character count.

    Each chunk gets at least MIN_SUBTITLE_MS.
    """
    if not chunks:
        return []

    max_entries = max(1, total_ms // MIN_SUBTITLE_MS)
    while len(chunks) > max_entries:
        merge_index = min(
            range(len(chunks) - 1),
            key=lambda index: len(chunks[index]) + len(chunks[index + 1]),
        )
        chunks = [
            *chunks[:merge_index],
            f"{chunks[merge_index]} {chunks[merge_index + 1]}".strip(),
            *chunks[merge_index + 2 :],
        ]

    char_counts = [max(len(c), 1) for c in chunks]
    total_chars = sum(char_counts)
    minimum_total = len(chunks) * MIN_SUBTITLE_MS
    remaining = max(0, total_ms - minimum_total)
    extras = [int(remaining * cc / total_chars) for cc in char_counts]
    raw_durations = [MIN_SUBTITLE_MS + extra for extra in extras]
    raw_durations[-1] += total_ms - sum(raw_durations)

    # Build entries.
    entries: list[SubtitleEntry] = []
    cursor = offset_ms
    for i, (chunk, dur) in enumerate(zip(chunks, raw_durations, strict=True)):
        text = wrap_subtitle_lines(chunk)
        end = cursor + dur
        entries.append(SubtitleEntry(
            index=i + 1,
            start_ms=cursor,
            end_ms=end,
            text=text,
        ))
        cursor = end

    return entries


def _format_srt_time(ms: int) -> str:
    """Format milliseconds as SRT timestamp ``HH:MM:SS,mmm``."""
    if ms < 0:
        ms = 0
    hours = ms // 3_600_000
    ms %= 3_600_000
    minutes = ms // 60_000
    ms %= 60_000
    seconds = ms // 1000
    millis = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def entries_to_srt(entries: list[SubtitleEntry]) -> str:
    """Render subtitle entries as an SRT string."""
    blocks: list[str] = []
    for e in entries:
        blocks.append(
            f"{e.index}\n"
            f"{_format_srt_time(e.start_ms)} --> {_format_srt_time(e.end_ms)}\n"
            f"{e.text}\n"
        )
    return "\n".join(blocks)


# --------------------------------------------------------------------- #
# High-level API
# --------------------------------------------------------------------- #
@dataclass
class SceneNarration:
    """Input for subtitle generation: one scene's text + timing."""
    scene_id: str
    narration: str
    voice_duration_ms: int
    order: int = 0


class SubtitleGenerator:
    """Generate an SRT file for a whole project from scene narrations."""

    def generate(
        self,
        project_id: str,
        scenes: list[SceneNarration],
        output_path: str | Path,
        *,
        timeline: ProjectTimeline | None = None,
    ) -> SubtitleResult:
        """Build SRT from narrations and write to ``output_path``."""
        if not scenes:
            raise SubtitleGeneratorError("no scenes provided")

        # Sort by order.
        sorted_scenes = sorted(scenes, key=lambda s: s.order)

        all_entries: list[SubtitleEntry] = []
        cursor_ms = 0
        global_index = 1

        for scene in sorted_scenes:
            canonical_scene = timeline.scene(scene.scene_id) if timeline else None
            if not scene.narration or not scene.narration.strip():
                cursor_ms = (
                    canonical_scene.end_ms
                    if canonical_scene is not None
                    else cursor_ms + scene.voice_duration_ms + LEAD_IN_MS + LEAD_OUT_MS
                )
                continue

            scene_start = (
                canonical_scene.voice_start_ms
                if canonical_scene is not None
                else cursor_ms + LEAD_IN_MS
            )
            scene_dur = (
                canonical_scene.voice_duration_ms
                if canonical_scene is not None
                else scene.voice_duration_ms
            )

            chunks = split_narration_chunks(scene.narration)
            entries = allocate_timing(chunks, scene_dur, offset_ms=scene_start)

            for entry in entries:
                entry.index = global_index
                global_index += 1
                all_entries.append(entry)

            cursor_ms = (
                canonical_scene.end_ms
                if canonical_scene is not None
                else scene_start + scene_dur + LEAD_OUT_MS
            )

        srt_text = entries_to_srt(all_entries)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(srt_text, encoding="utf-8")

        total_dur = all_entries[-1].end_ms if all_entries else 0
        return SubtitleResult(
            project_id=project_id,
            srt_path=str(out),
            entry_count=len(all_entries),
            total_duration_ms=total_dur,
        )
