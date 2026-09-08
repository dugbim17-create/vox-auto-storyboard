from __future__ import annotations

from pathlib import Path


def test_release_spec_bundles_tcl_tk_and_native_entrypoint() -> None:
    text = Path("auto_storyboard.spec").read_text(encoding="utf-8-sig")
    assert "tcl8.6" in text
    assert "tk8.6" in text
    assert 'os.path.join(ROOT, "app", "launcher.py")' in text


def test_launcher_has_frozen_tk_resource_bootstrap() -> None:
    text = Path("app/launcher.py").read_text(encoding="utf-8-sig")
    assert "def _prepare_frozen_tk" in text
    assert "TCL_LIBRARY" in text
    assert "TK_LIBRARY" in text
    assert "_prepare_frozen_tk()" in text
