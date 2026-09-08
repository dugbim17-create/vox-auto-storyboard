"""Procedural Detective Investigation Board, Corkboard & Archival Dossier Engine for Vox videos.

Implements all core elements of true Vox / Johnny Harris / Magnates Media visual style:
- Textured Corkboard / Kraft Paper / Charcoal Dossier base surfaces
- Pinned Photographs with 3D glossy plastic pushpins & translucent scotch tape
- Catenary-curve Red Yarn / String connections between evidence pins
- Yellow Sticky Notes with handwritten/typewritten annotations
- Evidence Checklist Dossiers with checkmarks and case files
- Redacted black censorship bars over suspect eyes
- High-impact rubber stamps ("CONFIDENTIAL", "UNDER INVESTIGATION", "EXPOSED", "EVIDENCE")
- Torn newspaper clippings and halftone archival headlines
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.services.paper_craft import PaperCraftService, PaperCutoutOptions

logger = logging.getLogger(__name__)


@lru_cache(maxsize=32)
def _get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/tahomabd.ttf" if bold else "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/impact.ttf",
    ]
    for c in candidates:
        if Path(c).is_file():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


@dataclass(frozen=True)
class PinnedEvidence:
    """A physical evidence photo or document pinned to the board."""

    img_path: str
    center: tuple[int, int]
    size: tuple[int, int] = (420, 320)
    angle_deg: float = 0.0
    caption: str = ""
    pin_color: tuple[int, int, int] = (220, 30, 30)
    has_censor_bar: bool = False
    censor_box_rel: tuple[float, float, float, float] | None = None  # (x0, y0, x1, y1) relative to photo
    tape_corners: bool = True


@dataclass(frozen=True)
class StickyNote:
    """A yellow sticky memo pinned or taped to the evidence board."""

    text: str
    subtext: str = ""
    center: tuple[int, int] = (0, 0)
    size: tuple[int, int] = (260, 220)
    angle_deg: float = 4.0
    color: tuple[int, int, int] = (255, 235, 110)  # Classic post-it yellow


@dataclass(frozen=True)
class EvidenceChecklist:
    """A case file clipboard or checklist dossier."""

    title: str
    items: list[tuple[str, bool]]  # [(item_name, checked)]
    center: tuple[int, int] = (0, 0)
    size: tuple[int, int] = (340, 380)
    angle_deg: float = -3.0


class InvestigationBoardService:
    """Full-featured renderer for Vox investigative corkboards and case dossiers."""

    @staticmethod
    def generate_corkboard_texture(width: int, height: int) -> Image.Image:
        """Generate an authentic corkboard pinboard background texture."""
        # Base cork warm tan color
        base_color = np.array([184, 142, 102], dtype=np.float32)
        noise1 = np.random.normal(0, 18, size=(height, width, 1))
        noise2 = np.random.normal(0, 8, size=(height, width, 1))
        
        cork = np.clip(base_color + noise1 + noise2, 0, 255).astype(np.uint8)
        cork = np.repeat(cork, 3, axis=2) if cork.shape[2] == 1 else cork
        cork_img = Image.fromarray(cork, mode="RGB").convert("RGBA")

        # Vignette darkening towards edges
        vignette = Image.new("L", (width, height), 0)
        vdraw = ImageDraw.Draw(vignette)
        vdraw.rectangle([(0, 0), (width, height)], fill=255)
        vdraw.ellipse([(int(width * 0.1), int(height * 0.1)), (int(width * 0.9), int(height * 0.9))], fill=0)
        vignette = vignette.filter(ImageFilter.GaussianBlur(140))
        
        dark_layer = Image.new("RGBA", (width, height), (24, 18, 12, 160))
        cork_img.paste(dark_layer, (0, 0), mask=vignette)

        grain = PaperCraftService.generate_film_grain_texture(width, height, intensity=0.04)
        return Image.alpha_composite(cork_img, grain)

    @staticmethod
    def generate_dark_dossier_texture(width: int, height: int) -> Image.Image:
        """Generate a moody dark slate/charcoal dossier desk surface."""
        base = Image.new("RGBA", (width, height), (18, 20, 24, 255))
        draw = ImageDraw.Draw(base)

        # Subtle drafting grid lines
        for x in range(0, width, 80):
            draw.line([(x, 0), (x, height)], fill=(255, 255, 255, 10), width=1)
        for y in range(0, height, 80):
            draw.line([(0, y), (width, y)], fill=(255, 255, 255, 10), width=1)

        grain = PaperCraftService.generate_film_grain_texture(width, height, intensity=0.05)
        return Image.alpha_composite(base, grain)

    @staticmethod
    def render_pinned_photo(evidence: PinnedEvidence) -> tuple[Image.Image, tuple[int, int]]:
        """Render a photo print with border, censor bar, tape, and 3D pushpin.
        
        Returns (rendered_image, (pin_x_in_image, pin_y_in_image)).
        """
        w, h = evidence.size
        pad_border = 14
        pad_bottom = 44 if evidence.caption else 14
        photo_w = max(10, w - pad_border * 2)
        photo_h = max(10, h - pad_border - pad_bottom)

        im = Image.open(evidence.img_path).convert("RGB")
        im_fitted = im.resize((photo_w, photo_h), Image.Resampling.BICUBIC)

        # Apply black censor bar over eyes if requested
        if evidence.has_censor_bar:
            cdraw = ImageDraw.Draw(im_fitted)
            rel_box = evidence.censor_box_rel or (0.2, 0.25, 0.8, 0.42)
            bx0 = int(photo_w * rel_box[0])
            by0 = int(photo_h * rel_box[1])
            bx1 = int(photo_w * rel_box[2])
            by1 = int(photo_h * rel_box[3])
            cdraw.rectangle([(bx0, by0), (bx1, by1)], fill=(12, 12, 14))
            font_cen = _get_font(14, bold=True)
            cdraw.text(((bx0 + bx1) // 2, (by0 + by1) // 2), "REDACTED", font=font_cen, fill=(255, 255, 255, 240), anchor="mm")

        # Frame paper plate
        frame = Image.new("RGBA", (w, h), (248, 246, 238, 255))
        fdraw = ImageDraw.Draw(frame)
        fdraw.rectangle([(0, 0), (w - 1, h - 1)], outline=(200, 195, 180, 255), width=2)
        frame.paste(im_fitted, (pad_border, pad_border))

        if evidence.caption:
            font_cap = _get_font(16, bold=True)
            fdraw.text((w // 2, h - 22), evidence.caption.upper(), font=font_cap, fill=(45, 45, 50, 255), anchor="mm")

        if evidence.tape_corners:
            frame = PaperCraftService.apply_corner_tape_mounts(frame, tape_size=(55, 20), opacity=0.6)

        # 3D Pushpin on top center
        pin = PaperCraftService.draw_3d_pushpin(radius=16, color=evidence.pin_color)
        pin_x = (w - pin.width) // 2
        pin_y = -8
        frame.paste(pin, (pin_x, pin_y), mask=pin.split()[-1])
        pin_anchor = (w // 2, pin_y + pin.height // 2)

        # Torn cutout and drop shadow
        cutout = PaperCraftService.create_torn_cutout(
            frame, PaperCutoutOptions(border_width=6, roughness=0.2, shadow=True, shadow_opacity=0.5)
        )
        if evidence.angle_deg != 0.0:
            cutout = cutout.rotate(evidence.angle_deg, resample=Image.Resampling.BICUBIC, expand=True)

        return cutout, pin_anchor

    @staticmethod
    def render_sticky_note(note: StickyNote) -> Image.Image:
        """Render a yellow post-it memo note with drop shadow."""
        w, h = note.size
        memo = Image.new("RGBA", (w, h), (*note.color, 255))
        draw = ImageDraw.Draw(memo)
        draw.rectangle([(0, 0), (w - 1, h - 1)], outline=(210, 190, 80, 255), width=2)

        # Sticky adhesive band shadow at top
        draw.rectangle([(0, 0), (w, 24)], fill=(max(0, note.color[0] - 25), max(0, note.color[1] - 25), max(0, note.color[2] - 25), 180))

        font_text = _get_font(18, bold=True)
        draw.text((w // 2, h // 2 - 15), note.text, font=font_text, fill=(35, 30, 15, 255), anchor="mm")

        if note.subtext:
            font_sub = _get_font(14, bold=False)
            draw.text((w // 2, h // 2 + 25), note.subtext, font=font_sub, fill=(65, 55, 30, 255), anchor="mm")

        cutout = PaperCraftService.create_torn_cutout(
            memo, PaperCutoutOptions(border_width=4, roughness=0.15, shadow=True, shadow_opacity=0.4)
        )
        if note.angle_deg != 0.0:
            cutout = cutout.rotate(note.angle_deg, resample=Image.Resampling.BICUBIC, expand=True)
        return cutout

    @staticmethod
    def render_checklist_dossier(checklist: EvidenceChecklist) -> Image.Image:
        """Render an evidence clipboard / dossier checklist."""
        w, h = checklist.size
        dossier = Image.new("RGBA", (w, h), (242, 238, 228, 255))
        draw = ImageDraw.Draw(dossier)
        draw.rectangle([(0, 0), (w - 1, h - 1)], outline=(190, 180, 160, 255), width=2)

        # Header banner
        draw.rectangle([(0, 0), (w, 46)], fill=(35, 40, 48, 255))
        font_h = _get_font(20, bold=True)
        draw.text((w // 2, 23), checklist.title.upper(), font=font_h, fill=(255, 220, 20, 255), anchor="mm")

        font_item = _get_font(16, bold=True)
        for i, (item_text, checked) in enumerate(checklist.items):
            iy = 75 + i * 36
            # Checkbox
            box_rect = [(20, iy - 10), (38, iy + 8)]
            draw.rectangle(box_rect, outline=(60, 60, 65, 255), fill=(255, 255, 255, 255), width=2)
            if checked:
                # Green checkmark
                draw.line([(24, iy), (28, iy + 5)], fill=(30, 180, 60, 255), width=3)
                draw.line([(28, iy + 5), (36, iy - 6)], fill=(30, 180, 60, 255), width=3)
            draw.text((50, iy), item_text, font=font_item, fill=(40, 40, 45, 255), anchor="lm")

        # Pinned with 3D pin at top
        pin = PaperCraftService.draw_3d_pushpin(radius=15, color=(220, 30, 30))
        dossier.paste(pin, ((w - pin.width) // 2, -8), mask=pin.split()[-1])

        cutout = PaperCraftService.create_torn_cutout(
            dossier, PaperCutoutOptions(border_width=6, roughness=0.2, shadow=True, shadow_opacity=0.45)
        )
        if checklist.angle_deg != 0.0:
            cutout = cutout.rotate(checklist.angle_deg, resample=Image.Resampling.BICUBIC, expand=True)
        return cutout

    @staticmethod
    def draw_catenary_red_string(
        canvas: Image.Image,
        p0: tuple[int, int],
        p1: tuple[int, int],
        sag: float = 25.0,
        color: tuple[int, int, int] = (220, 35, 35),
        width: int = 4,
        progress: float = 1.0,
    ) -> None:
        """Draw an authentic red yarn / string connecting two evidence pushpins with natural gravity sag."""
        if progress <= 0.0:
            return
        draw = ImageDraw.Draw(canvas)
        p = max(0.0, min(1.0, progress))

        num_points = int(50 * p)
        if num_points < 2:
            return

        points: list[tuple[int, int]] = []
        for i in range(num_points):
            t = i / 49.0
            # Linear interpolation
            x = p0[0] + (p1[0] - p0[0]) * t
            y = p0[1] + (p1[1] - p0[1]) * t
            # Parabolic gravity sag
            sag_y = sag * 4.0 * t * (1.0 - t)
            points.append((int(x), int(y + sag_y)))

        # 1. Cast shadow of the string on the board
        for i in range(len(points) - 1):
            pt_a = (points[i][0] + 3, points[i][1] + 6)
            pt_b = (points[i + 1][0] + 3, points[i + 1][1] + 6)
            draw.line([pt_a, pt_b], fill=(20, 15, 10, 80), width=width + 2)

        # 2. Main red string
        for i in range(len(points) - 1):
            draw.line([points[i], points[i + 1]], fill=(*color, 245), width=width)

    @staticmethod
    def render_investigation_stamp(
        canvas: Image.Image,
        center: tuple[int, int],
        text: str,
        angle_deg: float = -12.0,
        color: tuple[int, int, int] = (210, 25, 25),
        scale: float = 1.0,
    ) -> None:
        """Render a grunge red rubber stamp ("CONFIDENTIAL", "UNDER INVESTIGATION", "EXPOSED")."""
        if scale <= 0.0:
            return
        sw = int(280 * scale)
        sh = int(72 * scale)
        if sw < 24 or sh < 24:
            return

        simg = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(simg)
        # Double border
        sdraw.rectangle([(0, 0), (sw - 1, sh - 1)], outline=(*color, 230), width=4)
        if sw > 20 and sh > 20:
            sdraw.rectangle([(6, 6), (sw - 7, sh - 7)], outline=(*color, 160), width=2)

        sfont = _get_font(int(24 * scale), bold=True)
        sdraw.text((sw // 2, sh // 2), text.upper(), font=sfont, fill=(*color, 240), anchor="mm")

        simg = simg.rotate(angle_deg, resample=Image.Resampling.BICUBIC, expand=True)
        canvas.paste(simg, (center[0] - simg.width // 2, center[1] - simg.height // 2), mask=simg.split()[-1])
