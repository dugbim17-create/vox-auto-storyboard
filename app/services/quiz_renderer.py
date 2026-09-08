from __future__ import annotations

import hashlib
import json
import math
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.schemas.quiz import validate_quiz_project
from app.services.quiz_timeline import QuizTimeline, QuizTimelineCompiler
from app.services.text_layout import resolve_font, wrap_text


class QuizRenderError(RuntimeError):
    """Raised when deterministic offline quiz rendering fails."""


@dataclass(frozen=True)
class QuizTheme:
    background_top: tuple[int, int, int] = (22, 28, 70)
    background_bottom: tuple[int, int, int] = (76, 31, 105)
    panel: tuple[int, int, int] = (250, 250, 255)
    panel_text: tuple[int, int, int] = (28, 31, 54)
    accent: tuple[int, int, int] = (255, 196, 48)
    choice_badge: tuple[int, int, int] = (204, 49, 128)
    success: tuple[int, int, int] = (33, 184, 110)
    wrong_dim: tuple[int, int, int] = (91, 78, 107)
    white: tuple[int, int, int] = (255, 255, 255)
    timer: tuple[int, int, int] = (52, 213, 235)


@dataclass(frozen=True)
class QuizRenderState:
    kind: str
    question: dict[str, Any] | None = None
    progress: float = 0.0


@dataclass(frozen=True)
class QuizRenderSegment:
    state: QuizRenderState
    start_ms: int
    duration_ms: int


@dataclass(frozen=True)
class QuizRenderResult:
    output_path: Path
    manifest_path: Path
    probe_path: Path
    timeline_path: Path
    sha256: str
    duration_ms: int


@dataclass(frozen=True)
class QuizFrameProbeResult:
    manifest_path: Path
    frame_paths: tuple[Path, ...]


class QuizOfflineRenderer:
    """Pillow graphics + one local FFmpeg encode; no provider or TTS dependency."""

    def __init__(
        self,
        *,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
        theme: QuizTheme | None = None,
        asset_root: str | Path | None = None,
    ) -> None:
        if width < 160 or height < 90 or fps < 1:
            raise ValueError("invalid render dimensions or fps")
        self.width = width
        self.height = height
        self.fps = fps
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin
        self.theme = theme or QuizTheme()
        self.asset_root = Path(asset_root).resolve() if asset_root is not None else None
        self.scale = min(width / 1280, height / 720)

    def choice_probe_point(self, index: int) -> tuple[int, int]:
        x0, y0, x1, y1 = self._choice_rect(index)
        return ((x0 + x1) // 2, (y0 + y1) // 2)

    def build_render_plan(
        self, quiz_document: dict[str, Any], timeline: QuizTimeline
    ) -> list[QuizRenderSegment]:
        quiz = validate_quiz_project(quiz_document)
        plan = [
            QuizRenderSegment(
                QuizRenderState("INTRO"), timeline.intro.start_ms, timeline.intro.duration_ms
            )
        ]
        for question_data, question_timeline in zip(
            quiz["questions"], timeline.questions, strict=True
        ):
            phases = {phase.kind: phase for phase in question_timeline.phases}
            question_start = phases["QUESTION_IN"].start_ms
            countdown_start = phases["COUNTDOWN"].start_ms
            reveal_start = phases["ANSWER_REVEAL"].start_ms
            plan.extend(
                [
                    QuizRenderSegment(
                        QuizRenderState("QUESTION", question_data, 0.0),
                        question_start,
                        countdown_start - question_start,
                    ),
                    QuizRenderSegment(
                        QuizRenderState("COUNTDOWN", question_data, 0.5),
                        countdown_start,
                        phases["COUNTDOWN"].duration_ms,
                    ),
                    QuizRenderSegment(
                        QuizRenderState("TIME_UP", question_data, 0.0),
                        phases["TIME_UP"].start_ms,
                        phases["TIME_UP"].duration_ms,
                    ),
                    QuizRenderSegment(
                        QuizRenderState("REVEAL", question_data, 1.0),
                        reveal_start,
                        question_timeline.end_ms - reveal_start,
                    ),
                ]
            )
        plan.append(
            QuizRenderSegment(
                QuizRenderState("OUTRO"), timeline.outro.start_ms, timeline.outro.duration_ms
            )
        )
        return plan

    def render_frame(
        self, quiz_document: dict[str, Any], state: QuizRenderState
    ) -> Image.Image:
        return self.render_frame_with_layout(quiz_document, state)[0]

    def render_frame_with_layout(
        self, quiz_document: dict[str, Any], state: QuizRenderState
    ) -> tuple[Image.Image, dict[str, Any]]:
        quiz = validate_quiz_project(quiz_document)
        image = self._background()
        draw = ImageDraw.Draw(image)
        if state.kind == "INTRO":
            return self._render_title_card(draw, image, quiz.get("intro") or {}, intro=True)
        if state.kind == "OUTRO":
            return self._render_title_card(draw, image, quiz.get("outro") or {}, intro=False)
        if state.kind not in {"QUESTION", "COUNTDOWN", "TIME_UP", "REVEAL"} or state.question is None:
            raise QuizRenderError(f"unsupported render state: {state.kind}")
        return self._render_question(draw, image, state, total_questions=len(quiz["questions"]))

    def render_frame_probes(
        self, quiz_document: dict[str, Any], output_dir: str | Path
    ) -> QuizFrameProbeResult:
        quiz = validate_quiz_project(quiz_document)
        output_dir = Path(output_dir)
        frames_dir = output_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        records: list[dict[str, Any]] = []
        frame_paths: list[Path] = []
        states = (
            QuizRenderState("QUESTION", progress=0.0),
            QuizRenderState("COUNTDOWN", progress=0.5),
            QuizRenderState("TIME_UP", progress=0.0),
            QuizRenderState("REVEAL", progress=1.0),
        )
        try:
            for question in quiz["questions"]:
                for state_template in states:
                    state = QuizRenderState(
                        state_template.kind,
                        question=question,
                        progress=state_template.progress,
                    )
                    frame, layout = self.render_frame_with_layout(quiz, state)
                    stem = f"{question['question_id']}_{state.kind.lower()}"
                    partial = frames_dir / f"{stem}.partial.png"
                    final = frames_dir / f"{stem}.png"
                    frame.save(partial, format="PNG")
                    with Image.open(partial) as decoded:
                        decoded.load()
                        if decoded.size != (self.width, self.height):
                            raise QuizRenderError("frame probe resolution mismatch")
                    partial.replace(final)
                    frame_paths.append(final)
                    records.append(
                        {
                            "question_id": question["question_id"],
                            "state": state.kind,
                            "relative_path": final.relative_to(output_dir).as_posix(),
                            "bytes": final.stat().st_size,
                            "sha256": self._sha256(final),
                            "layout": layout,
                        }
                    )
        except Exception:
            for partial in frames_dir.glob("*.partial.png"):
                partial.unlink(missing_ok=True)
            raise
        manifest = {
            "schema_version": "quiz_frame_probes_v1",
            "question_count": len(quiz["questions"]),
            "state_count": len(records),
            "resolution": [self.width, self.height],
            "provider_calls": 0,
            "tts_calls": 0,
            "render_calls": 0,
            "frames": records,
        }
        manifest_path = output_dir / "frame-probes.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return QuizFrameProbeResult(manifest_path, tuple(frame_paths))

    def render(
        self,
        quiz_document: dict[str, Any],
        output_dir: str | Path,
        *,
        compiler: QuizTimelineCompiler | None = None,
        audio_policy: str = "synthetic_sine",
    ) -> QuizRenderResult:
        if audio_policy not in {"synthetic_sine", "silent"}:
            raise QuizRenderError("audio_policy must be synthetic_sine or silent")
        quiz = validate_quiz_project(quiz_document)
        compiler = compiler or QuizTimelineCompiler(fps=self.fps)
        timeline = compiler.compile(quiz)
        if timeline.fps != self.fps:
            raise QuizRenderError("timeline fps must match renderer fps")
        output_dir = Path(output_dir)
        frames_dir = output_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        plan = self.build_render_plan(quiz, timeline)
        concat_path = output_dir / "quiz_frames.ffconcat"
        concat_lines = ["ffconcat version 1.0"]
        frame_paths: list[Path] = []
        for index, segment in enumerate(plan):
            frame_path = frames_dir / f"segment_{index:03d}_{segment.state.kind.lower()}.png"
            self.render_frame(quiz, segment.state).save(frame_path)
            frame_paths.append(frame_path)
            concat_lines.append(f"file '{frame_path.resolve().as_posix()}'")
            concat_lines.append(f"duration {segment.duration_ms / 1000:.6f}")
        concat_lines.append(f"file '{frame_paths[-1].resolve().as_posix()}'")
        concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")

        timeline_path = output_dir / "timeline.json"
        timeline_path.write_text(
            json.dumps(timeline.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        output_path = output_dir / "quiz_mode_30.mp4"
        partial = output_dir / "quiz_mode_30.partial.mp4"
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
        ]
        if audio_policy == "synthetic_sine":
            cmd += [
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=220:sample_rate=48000",
            ]
        else:
            cmd += [
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
            ]
        cmd += [
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            f"fps={self.fps},format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-t",
            f"{timeline.duration_ms / 1000:.3f}",
            "-movflags",
            "+faststart",
            str(partial),
        ]
        self._run(cmd, "ffmpeg")
        probe = self._probe(partial)
        self._verify_probe(probe, timeline.duration_ms)
        partial.replace(output_path)
        sha256 = self._sha256(output_path)
        probe_path = output_dir / "ffprobe.json"
        probe_path.write_text(json.dumps(probe, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest = {
            "schema_version": "quiz_render_manifest_v1",
            "created_at": datetime.now(UTC).isoformat(),
            "output": str(output_path.resolve()),
            "sha256": sha256,
            "bytes": output_path.stat().st_size,
            "question_count": len(quiz["questions"]),
            "duration_ms": probe["format"]["duration_ms"],
            "compiled_duration_ms": timeline.duration_ms,
            "resolution": [self.width, self.height],
            "fps": self.fps,
            "audio_policy": audio_policy,
            "provider_calls": 0,
            "tts_calls": 0,
            "frame_segment_count": len(plan),
            "timeline": str(timeline_path.resolve()),
            "probe": str(probe_path.resolve()),
        }
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return QuizRenderResult(
            output_path=output_path,
            manifest_path=manifest_path,
            probe_path=probe_path,
            timeline_path=timeline_path,
            sha256=sha256,
            duration_ms=probe["format"]["duration_ms"],
        )

    def _background(self) -> Image.Image:
        image = Image.new("RGB", (self.width, self.height))
        pixels = image.load()
        top = self.theme.background_top
        bottom = self.theme.background_bottom
        for y in range(self.height):
            ratio = y / max(1, self.height - 1)
            color = tuple(round(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
            for x in range(self.width):
                pixels[x, y] = color
        draw = ImageDraw.Draw(image)
        step = max(24, round(72 * self.scale))
        radius = max(2, round(4 * self.scale))
        for y in range(step // 2, self.height, step):
            for x in range(step // 2, self.width, step):
                draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(104, 76, 139))
        return image

    def _render_title_card(
        self, draw: ImageDraw.ImageDraw, image: Image.Image, data: dict[str, Any], *, intro: bool
    ) -> tuple[Image.Image, dict[str, Any]]:
        title = str(data.get("title") or ("QUIZ MODE" if intro else "HOÀN THÀNH"))
        subtitle = str(
            data.get("subtitle")
            or data.get("cta")
            or ("30 câu hỏi • Sẵn sàng chưa?" if intro else "Cảm ơn bạn đã tham gia")
        )
        title_layout = self._fit_text(title, int(80 * self.scale), int(38 * self.scale), int(self.width * 0.82), 3)
        subtitle_layout = self._fit_text(
            subtitle, int(42 * self.scale), int(24 * self.scale), int(self.width * 0.78), 3
        )
        self._draw_centered_lines(draw, title_layout, int(self.height * 0.34), self.theme.white)
        self._draw_centered_lines(draw, subtitle_layout, int(self.height * 0.62), self.theme.accent)
        return image, {"title": self._layout_dict(title_layout), "subtitle": self._layout_dict(subtitle_layout)}

    def _render_question(
        self,
        draw: ImageDraw.ImageDraw,
        image: Image.Image,
        state: QuizRenderState,
        *,
        total_questions: int,
    ) -> tuple[Image.Image, dict[str, Any]]:
        question = state.question or {}
        visual_box, visual_source_size = self._paste_visual(image, question)
        order = int(question["order"])
        content_left_base = 470 if visual_box else 180
        content_right_base = 1232 if visual_box else 1100
        content_center_x = round((content_left_base + content_right_base) * self.width / 2560)
        content_width = round((content_right_base - content_left_base) * self.width / 1280)
        badge_rect = self._box(48, 36, 210, 100)
        self._draw_rounded_rectangle(
            draw, badge_rect, radius=max(8, int(18 * self.scale)), fill=self.theme.accent
        )
        badge_text = f"CÂU {order}/{total_questions}"
        badge_font = self._font(max(14, int(28 * self.scale)), badge_text)
        draw.text(
            ((badge_rect[0] + badge_rect[2]) // 2, (badge_rect[1] + badge_rect[3]) // 2),
            badge_text,
            font=badge_font,
            fill=self.theme.panel_text,
            anchor="mm",
        )
        q_layout = self._fit_text(
            str(question["question"]),
            max(34, int(52 * self.scale)) if self.scale >= 1 else max(15, int(52 * self.scale)),
            max(30, int(34 * self.scale)) if self.scale >= 1 else max(11, int(22 * self.scale)),
            content_width,
            3,
        )
        question_top = max(badge_rect[3] + round(12 * self.scale), round(self.height * 0.15))
        question_box = self._draw_centered_lines_from_top(
            draw,
            q_layout,
            question_top,
            self.theme.white,
            center_x=content_center_x,
        )

        choices_layout = []
        question_bottom_base = round(question_box[3] * 720 / self.height)
        choices = list(question.get("choices") or [])
        num_choices = len(choices)
        if num_choices >= 4:
            choice_gap_base = 72
            choice_height_base = 56
            choices_top_base = max(260, question_bottom_base + 12)
        else:
            choice_gap_base = 92
            choice_height_base = 66
            choices_top_base = max(310, question_bottom_base + 18)

        if num_choices > 0:
            choice_rects = [
                self._choice_rect(
                    index,
                    top_base=choices_top_base,
                    gap_base=choice_gap_base,
                    height_base=choice_height_base,
                    left_base=content_left_base,
                    right_base=content_right_base,
                )
                for index in range(num_choices)
            ]
            correct_id = str(question.get("correct_choice_id") or "")
            for index, choice in enumerate(choices):
                rect = choice_rects[index]
                is_correct = str(choice.get("id")) == correct_id
                if state.kind == "REVEAL":
                    fill = self.theme.success if is_correct else self.theme.wrong_dim
                else:
                    fill = self.theme.panel
                self._draw_rounded_rectangle(draw, rect, radius=max(6, int(18 * self.scale)), fill=fill)
                badge_r = max(12, int(24 * self.scale))
                badge_center = (rect[0] + int(42 * self.scale), (rect[1] + rect[3]) // 2)
                draw.ellipse(
                    (
                        badge_center[0] - badge_r,
                        badge_center[1] - badge_r,
                        badge_center[0] + badge_r,
                        badge_center[1] + badge_r,
                    ),
                    fill=self.theme.success if state.kind == "REVEAL" and is_correct else self.theme.choice_badge,
                )
                badge_font = self._font(max(12, int(25 * self.scale)), str(choice.get("id") or ""))
                draw.text(badge_center, str(choice.get("id") or ""), font=badge_font, fill=self.theme.white, anchor="mm")
                choice_layout = self._fit_text(
                    str(choice.get("text") or ""),
                    max(30, int(40 * self.scale)) if self.scale >= 1 else max(11, int(34 * self.scale)),
                    max(30, int(30 * self.scale)) if self.scale >= 1 else max(9, int(20 * self.scale)),
                    rect[2] - rect[0] - int(115 * self.scale),
                    2,
                )
                text_color = self.theme.white if state.kind == "REVEAL" else self.theme.panel_text
                self._draw_lines_in_choice(draw, choice_layout, rect, text_color)
                choices_layout.append(self._layout_dict(choice_layout))

            choices_box = (
                choice_rects[0][0],
                choice_rects[0][1],
                choice_rects[-1][2],
                choice_rects[-1][3],
            )
        else:
            choices_box = self._box(
                content_left_base,
                choices_top_base,
                content_right_base,
                choices_top_base + choice_height_base,
            )
        answer_box = None
        time_up_text = None
        if state.kind == "REVEAL":
            answer = f"ĐÁP ÁN: {correct_id} — {question['answer_text']}"
            answer_layout = self._fit_text(
                answer,
                max(32, int(38 * self.scale)) if self.scale >= 1 else max(11, int(30 * self.scale)),
                max(32, int(32 * self.scale)) if self.scale >= 1 else max(9, int(18 * self.scale)),
                content_width,
                3,
            )
            answer_box = self._draw_centered_lines_from_top(
                draw,
                answer_layout,
                choices_box[3] + round(16 * self.scale),
                self.theme.accent,
                center_x=content_center_x,
            )
        elif state.kind == "TIME_UP":
            time_up_text = "HẾT GIỜ"
            time_up_font = self._font(max(34, int(52 * self.scale)), time_up_text)
            draw.text(
                (content_center_x, self._box(0, 645, 0, 645)[1]),
                time_up_text,
                font=time_up_font,
                fill=self.theme.accent,
                anchor="mm",
            )
        else:
            x0, y0, x1, y1 = self._box(content_left_base, 662, content_right_base, 684)
            self._draw_rounded_rectangle(
                draw, (x0, y0, x1, y1), radius=max(2, int(10 * self.scale)), fill=(70, 61, 103)
            )
            progress = max(0.0, min(1.0, state.progress))
            if progress > 0:
                self._draw_rounded_rectangle(
                    draw,
                    (x0, y0, x0 + round((x1 - x0) * progress), y1),
                    radius=max(2, int(10 * self.scale)),
                    fill=self.theme.timer,
                )
        if visual_box is not None and visual_box[2] > min(question_box[0], choices_box[0]):
            raise QuizRenderError("visual overlaps quiz content")
        return image, {
            "question": self._layout_dict(q_layout),
            "choices": choices_layout,
            "badge_box": list(badge_rect),
            "question_box": list(question_box),
            "choices_box": list(choices_box),
            "answer_box": list(answer_box) if answer_box else None,
            "badge_text": badge_text,
            "time_up_text": time_up_text,
            "visual_box": list(visual_box) if visual_box else None,
            "visual_source_size": visual_source_size,
        }

    def _paste_visual(
        self, image: Image.Image, question: dict[str, Any]
    ) -> tuple[tuple[int, int, int, int] | None, list[int] | None]:
        visual = question.get("visual")
        if not isinstance(visual, dict) or not visual.get("local_path"):
            return None, None
        if self.asset_root is None:
            raise QuizRenderError("visual asset_root is required")
        local_path = Path(str(visual["local_path"]))
        if local_path.is_absolute() or ".." in local_path.parts:
            raise QuizRenderError("visual local_path must be project-relative")
        path = (self.asset_root / local_path).resolve()
        try:
            path.relative_to(self.asset_root)
        except ValueError as exc:
            raise QuizRenderError("visual local_path must be project-relative") from exc
        if not path.is_file():
            raise QuizRenderError(f"visual missing: {path}")
        try:
            with Image.open(path) as source:
                source.load()
                visual_image = source.convert("RGB")
        except Exception as exc:  # noqa: BLE001
            raise QuizRenderError(f"visual decode failed: {path}: {exc}") from exc
        source_size = [visual_image.width, visual_image.height]
        box = self._box(48, 150, 420, 600)
        target_size = (box[2] - box[0], box[3] - box[1])
        crop = str(visual.get("crop") or "contain")
        if crop == "cover":
            from PIL import ImageOps

            fitted = ImageOps.fit(visual_image, target_size, method=Image.Resampling.LANCZOS)
            paste_at = (box[0], box[1])
        elif crop == "contain":
            fitted = visual_image.copy()
            fitted.thumbnail(target_size, Image.Resampling.LANCZOS)
            paste_at = (
                box[0] + (target_size[0] - fitted.width) // 2,
                box[1] + (target_size[1] - fitted.height) // 2,
            )
        else:
            raise QuizRenderError("visual crop must be contain or cover")
        panel = Image.new("RGB", target_size, self.theme.panel)
        image.paste(panel, (box[0], box[1]))
        image.paste(fitted, paste_at)
        return box, source_size

    def _choice_rect(
        self,
        index: int,
        *,
        top_base: int = 310,
        gap_base: int = 105,
        height_base: int = 78,
        left_base: int = 180,
        right_base: int = 1100,
    ) -> tuple[int, int, int, int]:
        top = top_base + index * gap_base
        return self._box(left_base, top, right_base, top + height_base)

    def _box(self, x0: int, y0: int, x1: int, y1: int) -> tuple[int, int, int, int]:
        return (
            round(x0 * self.width / 1280),
            round(y0 * self.height / 720),
            round(x1 * self.width / 1280),
            round(y1 * self.height / 720),
        )

    def _draw_rounded_rectangle(
        self,
        draw: ImageDraw.ImageDraw,
        xy: tuple[int, int, int, int],
        radius: int,
        fill: Any,
        outline: Any = None,
    ) -> None:
        x0, y0, x1, y1 = xy
        if x1 <= x0 or y1 <= y0:
            return
        h = y1 - y0
        w = x1 - x0
        r = radius
        if h == 2 * r + 1:
            r = (h + 1) // 2
        if w == 2 * r + 1:
            r = (w + 1) // 2
        try:
            draw.rounded_rectangle((x0, y0, x1, y1), radius=r, fill=fill, outline=outline)
        except Exception:
            draw.rectangle((x0, y0, x1, y1), fill=fill, outline=outline)

    def _fit_text(
        self, text: str, preferred_size: int, floor_size: int, max_width: int, max_lines: int
    ) -> dict[str, Any]:
        font_path = resolve_font(text)
        for size in range(preferred_size, floor_size - 1, -1):
            font = ImageFont.truetype(font_path, size)
            lines = wrap_text(text, font, max_width)
            if len(lines) <= max_lines:
                return {
                    "text": text,
                    "font_path": font_path,
                    "font": font,
                    "font_size": size,
                    "lines": lines,
                    "line_count": len(lines),
                    "overflow": False,
                }
        font = ImageFont.truetype(font_path, floor_size)
        lines = wrap_text(text, font, max_width)
        if len(lines) > max_lines:
            raise QuizRenderError(
                f"blocked_overflow: text requires {len(lines)} lines, maximum is {max_lines}: {text}"
            )
        return {
            "text": text,
            "font_path": font_path,
            "font": font,
            "font_size": floor_size,
            "lines": lines,
            "line_count": len(lines),
            "overflow": False,
        }

    @staticmethod
    def _layout_dict(layout: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in layout.items() if key != "font"}

    def _draw_centered_lines(
        self, draw: ImageDraw.ImageDraw, layout: dict[str, Any], center_y: int, fill: tuple[int, int, int]
    ) -> None:
        font = layout["font"]
        line_height = math.ceil(layout["font_size"] * 1.22)
        first_y = center_y - line_height * len(layout["lines"]) // 2
        for index, line in enumerate(layout["lines"]):
            draw.text(
                (self.width // 2, first_y + index * line_height),
                line,
                font=font,
                fill=fill,
                anchor="ma",
                stroke_width=max(0, round(2 * self.scale)),
                stroke_fill=(18, 18, 40),
            )

    def _draw_centered_lines_from_top(
        self,
        draw: ImageDraw.ImageDraw,
        layout: dict[str, Any],
        top_y: int,
        fill: tuple[int, int, int],
        *,
        center_x: int | None = None,
    ) -> tuple[int, int, int, int]:
        font = layout["font"]
        line_height = math.ceil(layout["font_size"] * 1.22)
        center = center_x if center_x is not None else self.width // 2
        for index, line in enumerate(layout["lines"]):
            draw.text(
                (center, top_y + index * line_height),
                line,
                font=font,
                fill=fill,
                anchor="ma",
                stroke_width=max(0, round(2 * self.scale)),
                stroke_fill=(18, 18, 40),
            )
        return (
            center - max((round(font.getlength(line)) for line in layout["lines"]), default=0) // 2,
            top_y,
            center + max((round(font.getlength(line)) for line in layout["lines"]), default=0) // 2,
            top_y + line_height * len(layout["lines"]),
        )

    def _draw_lines_in_choice(
        self,
        draw: ImageDraw.ImageDraw,
        layout: dict[str, Any],
        rect: tuple[int, int, int, int],
        fill: tuple[int, int, int],
    ) -> None:
        line_height = math.ceil(layout["font_size"] * 1.15)
        y = (rect[1] + rect[3] - line_height * len(layout["lines"])) // 2
        x = rect[0] + max(35, int(90 * self.scale))
        for index, line in enumerate(layout["lines"]):
            draw.text((x, y + index * line_height), line, font=layout["font"], fill=fill)

    def _font(self, size: int, sample: str) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(resolve_font(sample), size)

    def _run(self, cmd: list[str], label: str) -> None:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            raise QuizRenderError(f"{label} failed rc={proc.returncode}: {proc.stderr[-4000:]}")

    def _probe(self, path: Path) -> dict[str, Any]:
        proc = subprocess.run(
            [self.ffprobe_bin, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            raise QuizRenderError(f"ffprobe failed rc={proc.returncode}: {proc.stderr}")
        raw = json.loads(proc.stdout)
        streams = raw.get("streams") or []
        video = next((item for item in streams if item.get("codec_type") == "video"), {})
        audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
        rate = str(video.get("r_frame_rate", "0/1")).split("/")
        fps = float(rate[0]) / float(rate[1]) if len(rate) == 2 and float(rate[1]) else 0.0
        duration_ms = round(float((raw.get("format") or {}).get("duration", 0)) * 1000)
        return {
            "video": {
                "codec_name": video.get("codec_name"),
                "width": int(video.get("width", 0)),
                "height": int(video.get("height", 0)),
                "fps": fps,
                "pix_fmt": video.get("pix_fmt"),
            },
            "audio": {
                "present": audio is not None,
                "codec_name": audio.get("codec_name") if audio else None,
                "sample_rate": int(audio.get("sample_rate", 0)) if audio else 0,
                "channels": int(audio.get("channels", 0)) if audio else 0,
            },
            "format": {
                "format_name": (raw.get("format") or {}).get("format_name"),
                "duration_ms": duration_ms,
                "size": int((raw.get("format") or {}).get("size", 0)),
            },
        }

    def _verify_probe(self, probe: dict[str, Any], expected_duration_ms: int) -> None:
        video = probe["video"]
        if (video["width"], video["height"]) != (self.width, self.height):
            raise QuizRenderError("rendered resolution mismatch")
        if abs(video["fps"] - self.fps) > 0.01:
            raise QuizRenderError("rendered fps mismatch")
        if video["pix_fmt"] != "yuv420p":
            raise QuizRenderError("rendered pixel format must be yuv420p")
        if not probe["audio"]["present"]:
            raise QuizRenderError("offline audio stream is required")
        tolerance_ms = math.ceil(1000 / self.fps)
        if abs(probe["format"]["duration_ms"] - expected_duration_ms) > tolerance_ms:
            raise QuizRenderError("rendered duration differs from compiled timeline")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
