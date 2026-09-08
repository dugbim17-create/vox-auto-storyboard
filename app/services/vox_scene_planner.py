"""Semantic VOX collage scene planning with authored typography only."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.motion_templates import build_template

_PURPOSE_TEMPLATES = {
    "opening": "09_cutout_parallax",
    "object_detail": "11_object_zoom_texture_wipe",
    "evidence": "07_document_highlight",
    "arrival": "02_subject_float_label_reveal",
    "handoff": "01_subject_slide_headline_pop",
    "conclusion": "12_conclusion_lockup",
}


@dataclass(frozen=True)
class VoxScenePlan:
    scene_id: str
    template_name: str
    plan: dict


def plan_vox_scene(
    *,
    scene_id: str,
    narration: str,
    purpose: str,
    duration_ms: int,
    canvas_size: tuple[int, int],
    available_roles: frozenset[str],
    authored_text: str = "",
    seed: int = 42,
) -> VoxScenePlan:
    """Build a semantic layered plan; never publish template placeholders."""
    del narration
    template_name = _PURPOSE_TEMPLATES.get(purpose, "09_cutout_parallax")
    raw = build_template(
        template_name,
        scene_id,
        duration_ms,
        seed=seed,
        canvas_size=canvas_size,
    )
    raw["motion_fps"] = 12
    # Benchmark sequences cut on semantic beats. Scene-start fades create blank
    # frames and hide the first authored keyword/subject.
    raw["transition_in"] = "none"
    raw["transition_out"] = "hard_cut"
    layers = [
        layer
        for layer in raw.get("layers", [])
        if layer.get("asset_role") in available_roles
    ]
    existing_roles = {str(layer.get("asset_role") or "") for layer in layers}
    # A benchmark VOX pack always carries a low-opacity material layer. Some
    # legacy templates omit it, so inject a deterministic independent track.
    if "texture" in available_roles and "texture" not in existing_roles:
        layers.append(
            {
                "id": "texture",
                "asset_role": "texture",
                "z": 30,
                "transform": {
                    "opacity": {
                        "easing": "ease_in_out",
                        "keyframes": [[0, 0.15], [duration_ms // 2, 0.38], [duration_ms, 0.2]],
                    },
                    "x": {
                        "easing": "linear",
                        "keyframes": [[0, 0], [duration_ms, int(canvas_size[0] * 0.012)]],
                    },
                },
            }
        )
    # The first frame must remain a composed editorial state. Templates may
    # reveal layers progressively, but never begin with background only.
    for layer in layers:
        if layer.get("asset_role") not in {"subject", "foreground"}:
            continue
        opacity = (layer.get("transform") or {}).get("opacity")
        if isinstance(opacity, dict) and opacity.get("keyframes"):
            keys = [list(item) for item in opacity["keyframes"]]
            keys[0][1] = max(0.72, float(keys[0][1]))
            opacity["keyframes"] = keys
    if len({layer.get("asset_role") for layer in layers}) < 2:
        raise ValueError("VOX scene requires at least two independent visual layers")
    raw["layers"] = layers
    if authored_text.strip():
        text_item = (raw.get("text_animations") or [{}])[0]
        text_item = dict(text_item)
        text_item["text"] = authored_text.strip()
        # Benchmark typography is a short screen-space beat, not a scene-long subtitle.
        start_ms = min(max(300, int(duration_ms * 0.18)), max(0, duration_ms - 700))
        end_ms = min(duration_ms, start_ms + min(2200, max(700, int(duration_ms * 0.28))))
        text_item["start_ms"] = start_ms
        text_item["end_ms"] = end_ms
        text_item["font_size"] = max(56, int(canvas_size[0] * 0.043))
        text_item["fontcolor"] = "white"
        raw["text_animations"] = [text_item]
    else:
        raw["text_animations"] = []
    return VoxScenePlan(scene_id=scene_id, template_name=template_name, plan=raw)
