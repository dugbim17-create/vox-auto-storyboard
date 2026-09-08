"""Paper craft, torn paper cutout, 3D pushpins, and tape mount aesthetic generator for Vox editorial style."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaperCutoutOptions:
    """Configuration options for torn paper sticker cutout effect."""

    border_width: int = 12
    roughness: float = 0.35
    shadow: bool = True
    shadow_offset: tuple[int, int] = (4, 8)
    shadow_opacity: float = 0.45
    shadow_blur: int = 6
    paper_tint: tuple[int, int, int] = (252, 250, 245)  # Warm archival paper white


class PaperCraftService:
    """Generate authentic paper cutout stickers, torn edges, 3D pushpins, and tape textures."""

    @staticmethod
    def create_torn_cutout(
        image: Image.Image,
        options: PaperCutoutOptions | None = None,
    ) -> Image.Image:
        """Add an authentic multi-frequency torn-edge paper border and dual-layer drop shadow to an RGBA subject."""
        opts = options or PaperCutoutOptions()
        if image.mode != "RGBA":
            image = image.convert("RGBA")

        alpha = image.split()[-1]
        w, h = image.size

        # Clean & morphology on alpha mask to eliminate background specks and holes
        from scipy import ndimage
        arr_alpha = np.array(alpha)
        binary = arr_alpha > 25
        filled = ndimage.binary_fill_holes(binary)
        labeled, num_features = ndimage.label(filled)
        if num_features > 0:
            sizes = ndimage.sum(filled, labeled, range(num_features + 1))
            mask_size = sizes > max(300, int(w * h * 0.005))
            cleaned_binary = mask_size[labeled]
        else:
            cleaned_binary = filled

        clean_alpha_arr = (cleaned_binary * 255).astype(np.uint8)
        clean_alpha = Image.fromarray(clean_alpha_arr, mode="L").filter(ImageFilter.GaussianBlur(1.0))

        # 1. Dilate alpha mask to create the sticker border footprint
        radius = max(1, opts.border_width)
        dilated = clean_alpha.filter(ImageFilter.MaxFilter(radius * 2 + 1))

        # 2. Multi-frequency torn paper fiber mask (wave + micro-fibers)
        arr = np.array(dilated, dtype=np.float32)
        y_coords, x_coords = np.mgrid[0:h, 0:w]
        wave = np.sin(x_coords * 0.08) * np.cos(y_coords * 0.08) * 6.0 * opts.roughness
        fibers = np.random.normal(0, 10.0 * opts.roughness, size=(h, w))

        noisy_mask_arr = np.clip(arr + (arr > 15) * (wave + fibers), 0, 255).astype(np.uint8)
        torn_mask = Image.fromarray(noisy_mask_arr, mode="L").filter(ImageFilter.BoxBlur(1))
        torn_mask = torn_mask.point(lambda p: 255 if p > 90 else 0)

        # 3. Canvas with padding for shadow and border expansion
        pad = opts.border_width + opts.shadow_blur * 2 + 12
        canvas_w = w + pad * 2
        canvas_h = h + pad * 2
        result = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

        # 4. Dual-layer drop shadow (sharp contact shadow + soft diffuse ambient shadow)
        if opts.shadow:
            # Layer A: Sharp contact shadow
            s_layer_a = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            c_mask = torn_mask.filter(ImageFilter.GaussianBlur(3))
            s_fill_a = Image.new("RGBA", (w, h), (10, 12, 16, int(255 * opts.shadow_opacity * 0.7)))
            s_layer_a.paste(s_fill_a, (pad + 3, pad + 4), mask=c_mask)
            result = Image.alpha_composite(result, s_layer_a)

            # Layer B: Soft diffuse shadow
            s_layer_b = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            d_mask = torn_mask.filter(ImageFilter.GaussianBlur(opts.shadow_blur + 4))
            s_fill_b = Image.new("RGBA", (w, h), (10, 12, 16, int(255 * opts.shadow_opacity * 0.45)))
            sx, sy = opts.shadow_offset
            s_layer_b.paste(s_fill_b, (pad + sx, pad + sy), mask=d_mask)
            result = Image.alpha_composite(result, s_layer_b)

        # 5. Archival white paper border
        border_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        border_fill = Image.new("RGBA", (w, h), (*opts.paper_tint, 255))
        border_layer.paste(border_fill, (pad, pad), mask=torn_mask)
        result = Image.alpha_composite(result, border_layer)

        # 6. Paste original subject
        subject_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        subject_layer.paste(image, (pad, pad), mask=alpha)
        result = Image.alpha_composite(result, subject_layer)

        return result

    @staticmethod
    def draw_3d_pushpin(
        radius: int = 16,
        color: tuple[int, int, int] = (225, 30, 30),
    ) -> Image.Image:
        """Render a realistic glossy 3D plastic pushpin with metal pin shadow and highlight."""
        pad = radius + 8
        w, h = pad * 2, pad * 2
        pin_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(pin_img)
        cx, cy = w // 2, h // 2

        # 1. Cast drop shadow
        shadow_mask = Image.new("L", (w, h), 0)
        sdraw = ImageDraw.Draw(shadow_mask)
        sdraw.ellipse([(cx - radius + 4, cy - radius + 6), (cx + radius + 4, cy + radius + 6)], fill=160)
        shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(3))
        shadow_layer = Image.new("RGBA", (w, h), (10, 12, 16, 140))
        pin_img.paste(shadow_layer, (0, 0), mask=shadow_mask)

        # 2. Plastic base ring
        dark_rim = (max(0, color[0] - 50), max(0, color[1] - 50), max(0, color[2] - 50), 255)
        draw.ellipse([(cx - radius, cy - radius), (cx + radius, cy + radius)], fill=dark_rim)

        # 3. Inner dome gradient
        inner_r = radius - 2
        for r in range(inner_r, 0, -1):
            ratio = r / float(inner_r)
            cr = int(color[0] * (0.6 + 0.4 * (1 - ratio)))
            cg = int(color[1] * (0.6 + 0.4 * (1 - ratio)))
            cb = int(color[2] * (0.6 + 0.4 * (1 - ratio)))
            ox = int(-1.5 * (1 - ratio))
            oy = int(-1.5 * (1 - ratio))
            draw.ellipse([(cx + ox - r, cy + oy - r), (cx + ox + r, cy + oy + r)], fill=(cr, cg, cb, 255))

        # 4. Specular highlight
        hl_r = max(2, radius // 4)
        hl_x, hl_y = cx - radius // 3, cy - radius // 3
        draw.ellipse([(hl_x - hl_r, hl_y - hl_r), (hl_x + hl_r, hl_y + hl_r)], fill=(255, 255, 255, 210))

        return pin_img

    @staticmethod
    def apply_corner_tape_mounts(
        image: Image.Image,
        tape_size: tuple[int, int] = (70, 24),
        opacity: float = 0.65,
    ) -> Image.Image:
        """Apply 4 translucent corner adhesive tape strips to hold the document."""
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        w, h = image.size
        result = image.copy()

        tw, th = tape_size
        tape = Image.new("RGBA", (tw, th), (255, 248, 220, int(255 * opacity)))
        tdraw = ImageDraw.Draw(tape)
        tdraw.rectangle([(0, 0), (tw - 1, th - 1)], outline=(210, 200, 160, 140), width=1)

        t_tl = tape.rotate(45, resample=Image.Resampling.BICUBIC, expand=True)
        t_tr = tape.rotate(-45, resample=Image.Resampling.BICUBIC, expand=True)
        t_bl = tape.rotate(-45, resample=Image.Resampling.BICUBIC, expand=True)
        t_br = tape.rotate(45, resample=Image.Resampling.BICUBIC, expand=True)

        result.paste(t_tl, (-10, -10), mask=t_tl.split()[-1])
        result.paste(t_tr, (w - t_tr.width + 10, -10), mask=t_tr.split()[-1])
        result.paste(t_bl, (-10, h - t_bl.height + 10), mask=t_bl.split()[-1])
        result.paste(t_br, (w - t_br.width + 10, h - t_br.height + 10), mask=t_br.split()[-1])

        return result

    @staticmethod
    def generate_film_grain_texture(
        width: int,
        height: int,
        intensity: float = 0.06,
    ) -> Image.Image:
        """Generate a procedural low-opacity grain texture overlay."""
        noise = np.random.normal(128, 255 * intensity, size=(height, width)).astype(np.uint8)
        gray = Image.fromarray(noise, mode="L")
        alpha_val = int(255 * min(1.0, intensity * 2.5))
        alpha = Image.new("L", (width, height), alpha_val)
        return Image.merge("RGBA", (gray, gray, gray, alpha))
