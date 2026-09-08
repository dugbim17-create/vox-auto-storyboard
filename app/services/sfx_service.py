"""Automated sound effects (Auto-SFX) and Foley design engine for Vox editorial videos."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Built-in procedural synthesis expressions via FFmpeg lavfi
PROCEDURAL_SYNTH_PRESETS: dict[str, str] = {
    "pop": "aevalsrc=sin(2*PI*800*exp(-t*35)*t):d=0.08:s=48000",
    "whoosh": "anoisesrc=d=0.25:c=pink:r=48000,lowpass=f=1200,afade=t=in:d=0.08,afade=t=out:st=0.15:d=0.1",
    "paper_slide": "anoisesrc=d=0.3:c=white:r=48000,bandpass=f=2500:w=1200,afade=t=in:d=0.05,afade=t=out:st=0.18:d=0.12",
    "marker_sweep": "anoisesrc=d=0.4:c=pink:r=48000,bandpass=f=1800:w=800,afade=t=in:d=0.05,afade=t=out:st=0.3:d=0.1",
    "typewriter": "aevalsrc=sin(2*PI*1200*t)*exp(-t*80):d=0.05:s=48000",
    "camera_click": "aevalsrc=sin(2*PI*2200*t)*exp(-t*60):d=0.06:s=48000",
    "card_shuffle": "anoisesrc=d=0.35:c=brown:r=48000,bandpass=f=3000:w=1500,afade=t=in:d=0.04,afade=t=out:st=0.2:d=0.15",
}

TEMPLATE_SFX_DEFAULTS: dict[str, list[tuple[str, float, float]]] = {
    # template_name -> [(sfx_type, time_fraction, volume_db)]
    "01_subject_slide_headline_pop": [("whoosh", 0.0, -8.0), ("pop", 0.35, -4.0)],
    "02_subject_float_label_reveal": [("pop", 0.4, -6.0)],
    "03_map_pan_marker_pulse": [("whoosh", 0.0, -10.0), ("pop", 0.3, -5.0)],
    "04_before_after_split": [("camera_click", 0.5, -4.0)],
    "05_stat_number_count": [("whoosh", 0.0, -9.0), ("typewriter", 0.25, -6.0), ("typewriter", 0.35, -6.0)],
    "06_timeline_cards": [("card_shuffle", 0.1, -6.0), ("pop", 0.45, -5.0)],
    "07_document_highlight": [("paper_slide", 0.0, -6.0), ("marker_sweep", 0.25, -4.0)],
    "08_photo_stack_shuffle": [("card_shuffle", 0.0, -5.0), ("paper_slide", 0.4, -6.0)],
    "09_cutout_parallax": [("whoosh", 0.0, -11.0)],
    "10_quote_card": [("typewriter", 0.15, -6.0)],
    "11_object_zoom_texture_wipe": [("paper_slide", 0.0, -6.0)],
    "12_conclusion_lockup": [("whoosh", 0.0, -8.0), ("pop", 0.3, -4.0)],
}


@dataclass(frozen=True)
class SFXEvent:
    """A scheduled sound effect event."""

    sfx_type: str
    start_ms: int
    volume_db: float = -6.0


class SFXServiceError(Exception):
    """Raised when SFX track generation or mixing fails."""


class AutoSFXService:
    """Automated SFX and Foley design generator for video timeline beats."""

    def __init__(
        self,
        *,
        ffmpeg_bin: str = "ffmpeg",
        runner: Callable[..., Any] | None = None,
    ) -> None:
        self.ffmpeg_bin = ffmpeg_bin
        self._runner = runner

    @staticmethod
    def derive_scene_sfx_events(
        template_name: str,
        duration_ms: int,
        visual_events: list[dict] | None = None,
        transition_out: str = "none",
    ) -> list[SFXEvent]:
        """Derive timed sound effects based on the motion template and visual triggers."""
        events: list[SFXEvent] = []

        # 1. Template defaults
        template_rules = TEMPLATE_SFX_DEFAULTS.get(template_name, [("whoosh", 0.0, -10.0)])
        for sfx_type, frac, vol in template_rules:
            t_ms = min(duration_ms, max(0, int(duration_ms * frac)))
            events.append(SFXEvent(sfx_type=sfx_type, start_ms=t_ms, volume_db=vol))

        # 2. Visual events triggers
        for ve in visual_events or []:
            start = int(ve.get("start_ms", 0))
            enter = str(ve.get("enter", "popup")).lower()
            if enter in ("popup", "pop"):
                events.append(SFXEvent(sfx_type="pop", start_ms=start, volume_db=-5.0))
            elif enter in ("slide_left", "slide_right", "wipe"):
                events.append(SFXEvent(sfx_type="paper_slide", start_ms=start, volume_db=-6.0))

        # 3. Transition out sound
        if transition_out in ("paper_tear", "tear"):
            events.append(SFXEvent(sfx_type="paper_slide", start_ms=max(0, duration_ms - 250), volume_db=-5.0))
        elif transition_out in ("wipe_left", "wipe_right", "paper_wipe"):
            events.append(SFXEvent(sfx_type="whoosh", start_ms=max(0, duration_ms - 200), volume_db=-8.0))

        return sorted(events, key=lambda e: e.start_ms)

    def render_scene_sfx_track(
        self,
        events: list[SFXEvent],
        duration_ms: int,
        output_path: str | Path,
        *,
        sfx_bank_dir: str | Path | None = None,
    ) -> Path:
        """Render a multichannel mixed audio track containing all timed SFX events."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        dur_s = max(0.1, duration_ms / 1000.0)

        if not events:
            # Generate silent audio track matching duration
            cmd = [
                self.ffmpeg_bin, "-y",
                "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={dur_s:.3f}",
                "-c:a", "pcm_s16le",
                str(out),
            ]
            self._run(cmd)
            return out

        inputs: list[str] = []
        filter_complex: list[str] = []

        # Base silent channel
        inputs.extend(["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={dur_s:.3f}"])
        filter_complex.append("[0:a]volume=0dB[a0]")
        mix_inputs = ["[a0]"]

        for idx, ev in enumerate(events, start=1):
            sfx_file = None
            if sfx_bank_dir:
                candidate = Path(sfx_bank_dir) / f"{ev.sfx_type}.wav"
                if candidate.is_file():
                    sfx_file = candidate

            if sfx_file:
                inputs.extend(["-i", str(sfx_file)])
            else:
                synth_expr = PROCEDURAL_SYNTH_PRESETS.get(ev.sfx_type, PROCEDURAL_SYNTH_PRESETS["pop"])
                inputs.extend(["-f", "lavfi", "-i", synth_expr])

            delay_ms = max(0, ev.start_ms)
            filter_complex.append(
                f"[{idx}:a]aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo,"
                f"volume={ev.volume_db}dB,adelay={delay_ms}|{delay_ms}[sfx{idx}]"
            )
            mix_inputs.append(f"[sfx{idx}]")

        filter_complex.append(f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:normalize=0[final_sfx]")

        cmd = [
            self.ffmpeg_bin, "-y",
            *inputs,
            "-filter_complex", ";".join(filter_complex),
            "-map", "[final_sfx]",
            "-c:a", "pcm_s16le",
            str(out),
        ]
        self._run(cmd)
        return out

    def mix_sfx_with_voice(
        self,
        voice_path: str | Path,
        sfx_path: str | Path,
        output_path: str | Path,
        *,
        voice_gain_db: float = 0.0,
        sfx_gain_db: float = -3.0,
    ) -> Path:
        """Mix voice and SFX tracks into one cohesive narrative audio file."""
        voice = Path(voice_path)
        sfx = Path(sfx_path)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        if not sfx.is_file():
            import shutil
            shutil.copy2(str(voice), str(out))
            return out

        cmd = [
            self.ffmpeg_bin, "-y",
            "-i", str(voice),
            "-i", str(sfx),
            "-filter_complex",
            f"[0:a]volume={voice_gain_db}dB[v];[1:a]volume={sfx_gain_db}dB[s];[v][s]amix=inputs=2:duration=first:normalize=0[mixed]",
            "-map", "[mixed]",
            "-c:a", "pcm_s16le",
            str(out),
        ]
        self._run(cmd)
        return out

    def _run(self, cmd: list[str]) -> None:
        runner = self._runner or subprocess.run
        proc = runner(cmd, capture_output=True, text=True)
        if getattr(proc, "returncode", 0) != 0:
            err = getattr(proc, "stderr", "")
            raise SFXServiceError(f"FFmpeg SFX execution failed: {err[-1500:]}")
