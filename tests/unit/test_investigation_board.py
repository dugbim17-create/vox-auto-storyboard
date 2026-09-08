"""Unit tests for InvestigationBoardService (corkboard, pinned photo, red string, sticky note, checklist)."""

from __future__ import annotations

from pathlib import Path
import numpy as np
from PIL import Image

from app.services.investigation_board import (
    EvidenceChecklist,
    InvestigationBoardService,
    PinnedEvidence,
    StickyNote,
)


def test_generate_corkboard_texture_creates_rgba_surface() -> None:
    cork = InvestigationBoardService.generate_corkboard_texture(640, 360)
    assert cork.size == (640, 360)
    assert cork.mode == "RGBA"
    arr = np.array(cork)
    assert arr[:, :, 0].mean() > 70  # Warm tan tone


def test_render_pinned_photo_creates_framed_evidence(tmp_path: Path) -> None:
    dummy_img = tmp_path / "dummy_suspect.png"
    Image.new("RGB", (300, 200), (80, 100, 120)).save(dummy_img)

    evidence = PinnedEvidence(
        img_path=str(dummy_img),
        center=(400, 300),
        size=(360, 260),
        caption="SUSPECT #01",
        has_censor_bar=True,
    )
    rendered, pin_anchor = InvestigationBoardService.render_pinned_photo(evidence)
    assert rendered.mode == "RGBA"
    assert rendered.width >= 360
    assert rendered.height >= 260
    assert pin_anchor[0] > 0


def test_render_sticky_note_and_checklist() -> None:
    note = StickyNote(text="FOLLOW THE MONEY", subtext="OFFSHORE ACCOUNTS")
    rendered_note = InvestigationBoardService.render_sticky_note(note)
    assert rendered_note.mode == "RGBA"

    checklist = EvidenceChecklist(
        title="CASE EVIDENCE",
        items=[("Flight Logs", True), ("Bank Records", True), ("Wiretaps", False)],
    )
    rendered_checklist = InvestigationBoardService.render_checklist_dossier(checklist)
    assert rendered_checklist.mode == "RGBA"


def test_draw_catenary_red_string() -> None:
    canvas = Image.new("RGBA", (800, 600), (0, 0, 0, 255))
    InvestigationBoardService.draw_catenary_red_string(
        canvas, (100, 100), (700, 500), sag=30.0, progress=1.0
    )
    arr = np.array(canvas)
    # Check that red pixels were drawn
    assert (arr[:, :, 0] > 180).sum() > 50
