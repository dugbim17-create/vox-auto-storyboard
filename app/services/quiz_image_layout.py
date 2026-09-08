"""Shared quiz image contract: provider geometry, cache identity and safe rendering.

A dual-aspect document reuses one asset. Never crop puzzle evidence or a hero;
legacy assets adapt the visible frame instead of stretching to fill it.
"""
from dataclasses import dataclass

from PIL import Image

VERSION = 'quiz-image-v1'


@dataclass(frozen=True)
class ImageSlot:
    box: tuple[int, int, int, int]
    provider_size: str
    aspect_ratio: str
    fit: str = 'contain-adaptive'

    @property
    def size(self):
        x0, y0, x1, y1 = self.box
        return x1 - x0, y1 - y0


def image_slot(kind: str, aspect: str = '16:9') -> ImageSlot:
    if kind == 'reveal':
        box = (120, 500, 960, 980) if aspect == '9:16' else (215, 300, 835, 700)
        return ImageSlot(box, '1536x1024', '3:2')
    if kind == 'card':
        size = (430, 440) if aspect == '9:16' else (390, 480)
        return ImageSlot((0, 0, *size), '1024x1024', '1:1', 'contain')
    if kind == 'scene':
        return ImageSlot((0, 0, 1080, 1740) if aspect == '9:16' else (0, 0, 1920, 940),
                         '1536x1024', '3:2', 'contain')
    raise ValueError(f'Unknown quiz image kind: {kind}')


def fitted_size(source, bounds, scale=1.0):
    if min(*source, *bounds) <= 0:
        raise ValueError('Image dimensions must be positive')
    factor = min(bounds[0] / source[0], bounds[1] / source[1]) * min(1.0, max(0.01, scale))
    return max(1, int(source[0] * factor)), max(1, int(source[1] * factor))


def layout_prompt(prompt: str, kind: str) -> str:
    slot = image_slot(kind)
    return (f'{prompt}\n\n[{VERSION}:{kind}] Output aspect ratio {slot.aspect_ratio}, '
            f'canvas {slot.provider_size}. Compose for the image slot, not the video orientation. '
            'Show the complete subject and every clue, large and readable, with 5% safe margins. '
            'No embedded borders, labels or text. Never crop evidence. '
            'For a wide scene keep all comparison objects visible side by side.')


def prompt_kind(prompt: str) -> str:
    for kind in ('card', 'scene', 'reveal'):
        if f'[{VERSION}:{kind}]' in prompt:
            return kind
    return 'reveal'


def inspect_layout(path, kind: str, *, generated=False):
    slot = image_slot(kind)
    with Image.open(path) as im:
        width, height = im.size
    expected_w, expected_h = map(int, slot.provider_size.split('x'))
    ratio_error = abs((width / height) / (expected_w / expected_h) - 1)
    if generated and ratio_error > 0.12:
        raise ValueError(f'Quiz image ratio mismatch for {kind}: {width}x{height}; expected {slot.aspect_ratio}')
    if generated and min(width, height) < 512:
        raise ValueError(f'Quiz image resolution too small: {width}x{height}')
    return {'version': VERSION, 'kind': kind, 'fit': slot.fit,
            'source_size': [width, height], 'provider_size': slot.provider_size,
            'ratio_match': ratio_error <= 0.12}
