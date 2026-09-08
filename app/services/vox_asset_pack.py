"""Benchmark-derived semantic asset packs for layered VOX scenes."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from app.storage.asset_store import AssetStore, sha256_file

_PLACEHOLDERS = {
    "HEADLINE",
    "LABEL",
    "MARKER",
    "BEFORE",
    "AFTER",
    "TIMELINE",
    "HIGHLIGHT",
    "STACK",
    "CUTOUT",
    "QUOTE",
    "OBJECT",
    "KẾT LUẬN",
}

_PURPOSE_KEYWORDS = {
    "opening": "CÂU CHUYỆN BẮT ĐẦU",
    "object_detail": "VẬT THỂ TRUNG TÂM",
    "evidence": "BẰNG CHỨNG",
    "arrival": "BƯỚC NGOẶT",
    "handoff": "KHOẢNH KHẮC TRAO LẠI",
    "conclusion": "KÝ ỨC THỨC GIẤC",
}

_PURPOSE_LABELS = {
    "opening": ("BỐI CẢNH", "NHÂN VẬT"),
    "object_detail": ("CHI TIẾT", "DẤU VẾT"),
    "evidence": ("QUAN SÁT", "XÁC MINH"),
    "arrival": ("THỜI ĐIỂM", "THAY ĐỔI"),
    "handoff": ("KỶ VẬT", "KẾT NỐI"),
    "conclusion": ("THỜI GIAN", "KÝ ỨC"),
}


@dataclass(frozen=True)
class VoxSemanticBeat:
    scene_id: str
    narration: str
    visual_function: str
    keyword: str
    accent_kind: str
    accent_labels: tuple[str, ...]
    order: int = 0

    def to_dict(self) -> dict:
        return {
            "scene_id": self.scene_id,
            "narration": self.narration,
            "visual_function": self.visual_function,
            "keyword": self.keyword,
            "accent_kind": self.accent_kind,
            "accent_labels": list(self.accent_labels),
            "order": self.order,
        }


@dataclass
class VoxAssetPackResult:
    scene_id: str
    ok: bool
    assets: dict[str, str] = field(default_factory=dict)
    sha256_by_role: dict[str, str] = field(default_factory=dict)
    manifest_path: str = ""
    error: str = ""


def derive_vox_beat(
    *,
    scene_id: str,
    narration: str,
    purpose: str,
    order: int = 0,
) -> VoxSemanticBeat:
    visual_function = purpose if purpose in _PURPOSE_LABELS else "evidence"
    normalized = " ".join(str(narration or "").split())
    keyword = _semantic_keyword(normalized, visual_function)
    labels = _semantic_labels(normalized, visual_function)
    return VoxSemanticBeat(
        scene_id=scene_id,
        narration=normalized,
        visual_function=visual_function,
        keyword=keyword,
        accent_kind=visual_function,
        accent_labels=labels,
        order=order,
    )


def _semantic_labels(narration: str, purpose: str) -> tuple[str, str]:
    lowered = narration.casefold()
    if purpose == "opening":
        return (
            "TIỆM CUỐI PHỐ" if "cuối phố" in lowered or "tiệm" in lowered else "MỞ ĐẦU",
            "NGƯỜI THỢ" if "thợ" in lowered else "NHÂN VẬT CHÍNH",
        )
    if purpose == "handoff":
        return (
            "KỶ VẬT" if "kỷ vật" in lowered else "TRAO LẠI",
            "CHA CỦA BÀ" if "cha" in lowered else "KẾT NỐI",
        )
    if purpose == "arrival":
        return (
            "TÍCH TẮC" if "tích tắc" in lowered else "THỜI ĐIỂM",
            "NGƯỜI PHỤ NỮ" if "phụ nữ" in lowered else "BƯỚC VÀO",
        )
    if purpose == "evidence":
        if "bánh răng" in lowered or "lò xo" in lowered:
            return (
                "BÁNH RĂNG" if "bánh răng" in lowered else "CHI TIẾT",
                "LÒ XO" if "lò xo" in lowered else "CƠ CẤU",
            )
        return ("QUAN SÁT", "XÁC MINH")
    if purpose == "object_detail" and "đồng hồ" in lowered:
        second = "30 NĂM" if "ba mươi" in lowered or "30" in lowered else "CHI TIẾT"
        return ("ĐỒNG HỒ", second)
    if purpose == "conclusion":
        return (
            "KHÔNG QUAY LẠI" if "không quay lại" in lowered else "THỜI GIAN",
            "ĐƯỢC ĐÁNH THỨC" if "đánh thức" in lowered else "KÝ ỨC",
        )
    return _PURPOSE_LABELS[purpose]


def _semantic_keyword(narration: str, purpose: str) -> str:
    lowered = narration.casefold()
    phrases = (
        ("bánh răng", "TỪNG BÁNH RĂNG"),
        ("ba mươi năm", "30 NĂM IM LẶNG"),
        ("30 năm", "30 NĂM IM LẶNG"),
        ("tích tắc", "TÍCH TẮC"),
        ("kỷ vật", "KỶ VẬT"),
        ("ký ức", "KÝ ỨC THỨC GIẤC"),
        ("thời gian", "THỜI GIAN"),
        ("đồng hồ", "CHIẾC ĐỒNG HỒ"),
    )
    for phrase, keyword in phrases:
        if phrase in lowered:
            return keyword
    words = [word.strip(".,!?;:()[]{}\"'") for word in narration.split()]
    content = [word for word in words if len(word) >= 4]
    if content:
        return " ".join(content[:3]).upper()
    return _PURPOSE_KEYWORDS[purpose]


class VoxAssetPackBuilder:
    """Build deterministic content-bearing editorial layers from approved imagery."""

    def __init__(
        self,
        *,
        canvas_size: tuple[int, int] = (1920, 1080),
        project_root: str | Path | None = None,
    ) -> None:
        self.width, self.height = canvas_size
        self.project_root = project_root

    def build(
        self,
        project_id: str,
        beat: VoxSemanticBeat,
        *,
        background_path: str | Path,
        subject_path: str | Path,
        store: AssetStore | None = None,
    ) -> VoxAssetPackResult:
        store = store or AssetStore(self.project_root)
        result = VoxAssetPackResult(scene_id=beat.scene_id, ok=True)
        try:
            editorial_dir = store.project_dir(project_id) / "editorial"
            editorial_dir.mkdir(parents=True, exist_ok=True)
            paths = {
                "background": editorial_dir / f"{beat.scene_id}_background.png",
                "subject": editorial_dir / f"{beat.scene_id}_subject.png",
                "foreground": editorial_dir / f"{beat.scene_id}_foreground.png",
                "texture": editorial_dir / f"{beat.scene_id}_texture.png",
            }
            background = self._background(background_path, beat)
            subject = self._subject(subject_path)
            foreground = self._foreground(beat)
            texture = self._texture(beat)
            for role, image in {
                "background": background,
                "subject": subject,
                "foreground": foreground,
                "texture": texture,
            }.items():
                image.save(paths[role], format="PNG", optimize=False)
            result.assets = {role: str(path) for role, path in paths.items()}
            result.sha256_by_role = {
                role: sha256_file(path) for role, path in paths.items()
            }
            payload = {
                "kind": "vox_asset_pack",
                "scene_id": beat.scene_id,
                "roles": list(paths),
                "beat": beat.to_dict(),
                "assets": {
                    role: {"path": str(path), "sha256": result.sha256_by_role[role]}
                    for role, path in paths.items()
                },
            }
            validate_vox_asset_pack(payload, expected_scene_id=beat.scene_id)
            manifest, _digest = store.write_manifest(
                project_id, f"vox_asset_pack_{beat.scene_id}.json", payload
            )
            result.manifest_path = str(manifest)
        except Exception as exc:  # noqa: BLE001
            result.ok = False
            result.error = str(exc)
        return result

    def _background(self, path: str | Path, beat: VoxSemanticBeat) -> Image.Image:
        with Image.open(path) as source:
            base = ImageOps.fit(
                source.convert("RGB"),
                (self.width, self.height),
                method=Image.Resampling.LANCZOS,
            )
        base = ImageEnhance.Color(base).enhance(0.28)
        base = ImageEnhance.Contrast(base).enhance(0.82).filter(ImageFilter.GaussianBlur(4))
        palette = {
            "opening": "#1d2b3a",
            "object_detail": "#bf9438",
            "evidence": "#9f3a31",
            "arrival": "#26344f",
            "handoff": "#c36b4e",
            "conclusion": "#202c3a",
        }
        tint = Image.new("RGB", base.size, palette.get(beat.visual_function, "#202c3a"))
        base = Image.blend(base, tint, 0.38)
        draw = ImageDraw.Draw(base)
        margin_x = int(self.width * 0.095)
        margin_y = int(self.height * 0.11)
        draw.rounded_rectangle(
            (margin_x, margin_y, self.width - margin_x, self.height - margin_y),
            radius=max(20, self.width // 45),
            outline="#d8ccb0",
            width=max(3, self.width // 360),
        )
        return base

    def _subject(self, path: str | Path) -> Image.Image:
        with Image.open(path) as source:
            subject = source.convert("RGBA")
        alpha = subject.getchannel("A")
        if alpha.getextrema()[0] == 255:
            raise ValueError("VOX subject requires real alpha")
        subject = ImageOps.contain(subject, (self.width, self.height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        x = (self.width - subject.width) // 2
        y = self.height - subject.height
        canvas.alpha_composite(subject, (x, y))
        return canvas

    def _foreground(self, beat: VoxSemanticBeat) -> Image.Image:
        canvas = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        scale = self.width / 1920.0
        red = "#cf2637"
        cream = "#eee4ce"
        amber = "#f2c84b"
        dark = "#181818"
        card_w = int(390 * scale)
        card_h = int(138 * scale)
        left = int(82 * scale)
        top = int(76 * scale)
        draw.rounded_rectangle(
            (left, top, left + card_w, top + card_h),
            radius=max(8, int(12 * scale)),
            fill=cream,
            outline=dark,
            width=max(2, int(5 * scale)),
        )
        font_label = _font(max(15, int(28 * scale)), bold=True)
        draw.rectangle(
            (left + int(22 * scale), top + int(22 * scale), left + card_w - int(22 * scale), top + int(59 * scale)),
            fill=red,
        )
        draw.text(
            (left + int(24 * scale), top + int(73 * scale)),
            beat.accent_labels[0],
            font=font_label,
            fill=dark,
        )
        right = self.width - int(440 * scale)
        bottom = self.height - int(236 * scale)
        draw.rounded_rectangle(
            (right, bottom, right + card_w, bottom + card_h),
            radius=max(8, int(12 * scale)),
            fill=cream,
            outline=dark,
            width=max(2, int(5 * scale)),
        )
        draw.rectangle(
            (right + int(24 * scale), bottom + int(22 * scale), right + card_w - int(24 * scale), bottom + int(59 * scale)),
            fill=amber,
        )
        draw.text(
            (right + int(24 * scale), bottom + int(73 * scale)),
            beat.accent_labels[-1],
            font=font_label,
            fill=dark,
        )
        start = (int(120 * scale), self.height - int(150 * scale))
        end = (int(520 * scale), self.height - int(375 * scale))
        width = max(5, int(18 * scale))
        draw.line((*start, *end), fill=red, width=width)
        draw.polygon(
            [
                end,
                (end[0] - int(58 * scale), end[1] + int(4 * scale)),
                (end[0] - int(18 * scale), end[1] + int(52 * scale)),
            ],
            fill=red,
        )
        return canvas

    def _texture(self, beat: VoxSemanticBeat) -> Image.Image:
        digest = hashlib.sha256(
            json.dumps(beat.to_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).digest()
        canvas = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        for index, y in enumerate(range(0, self.height, max(10, self.height // 48))):
            alpha = 8 + digest[index % len(digest)] % 11
            draw.line((0, y, self.width, y), fill=(25, 18, 12, alpha), width=1)
        for index in range(90):
            x = (digest[index % 32] * (index + 17) * 97) % self.width
            y = (digest[(index + 9) % 32] * (index + 11) * 53) % self.height
            radius = 1 + digest[(index + 5) % 32] % 3
            draw.ellipse((x, y, x + radius, y + radius), fill=(235, 224, 196, 18))
        return canvas


def validate_vox_asset_pack(payload: dict, *, expected_scene_id: str) -> dict:
    if payload.get("kind") != "vox_asset_pack":
        raise ValueError("invalid VOX asset-pack kind")
    if str(payload.get("scene_id") or "") != expected_scene_id:
        raise ValueError("VOX asset-pack scene mismatch")
    roles = payload.get("roles")
    required = {"background", "subject", "foreground", "texture"}
    if set(roles or ()) != required:
        raise ValueError("VOX asset pack requires four independent roles")
    beat = payload.get("beat") or {}
    keyword = str(beat.get("keyword") or "").strip()
    if keyword in _PLACEHOLDERS or not keyword:
        raise ValueError("VOX asset pack contains placeholder typography")
    labels = beat.get("accent_labels") or []
    accent_kind = str(beat.get("accent_kind") or "")
    if accent_kind == "decorative" or not labels:
        raise ValueError("VOX asset pack requires content-bearing accent labels")
    assets = payload.get("assets") or {}
    if assets and set(assets) != required:
        raise ValueError("VOX asset manifest role mismatch")
    return payload


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
    )
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def semantic_purpose(scene: dict, *, order: int, total: int) -> str:
    """Map storyboard meaning to the benchmark visual-function vocabulary."""
    declared_visual = str(scene.get("visual_function") or "")
    if declared_visual in _PURPOSE_LABELS:
        return declared_visual
    declared_purpose = str(scene.get("purpose") or "")
    # Only semantic opening/closing markers are authoritative. Generic
    # storyboard sections such as "body" must be classified from narration.
    if declared_purpose == "opening":
        return "opening"
    if declared_purpose in {"closing", "conclusion"}:
        return "conclusion"
    text = " ".join(
        str(scene.get(key) or "")
        for key in ("narration_text", "visual_summary", "image_prompt")
    ).casefold()
    if order == 1:
        return "opening"
    if order == total:
        return "conclusion"
    # Specific narrative events outrank generic object/evidence words that can
    # coexist in the same sentence (for example: a watch ticks as a woman enters).
    if any(token in text for token in ("nhận", "trao", "kỷ vật", "receive", "handoff")):
        return "handoff"
    if any(token in text for token in ("bước vào", "xuất hiện", "arrive", "doorway")):
        return "arrival"
    if any(token in text for token in ("bánh răng", "lò xo", "repair")):
        return "evidence"
    if any(token in text for token in ("đồng hồ", "object", "close-up", "cận cảnh")):
        return "object_detail"
    if any(token in text for token in ("evidence", "document")):
        return "evidence"
    return "evidence"


def manifest_path(store: AssetStore, project_id: str, scene_id: str) -> Path:
    return store.subdir(project_id, "manifests") / f"vox_asset_pack_{scene_id}.json"


def load_vox_asset_pack(store: AssetStore, project_id: str, scene_id: str) -> dict:
    path = manifest_path(store, project_id, scene_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return validate_vox_asset_pack(payload, expected_scene_id=scene_id)


def _safe_label(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).upper()
