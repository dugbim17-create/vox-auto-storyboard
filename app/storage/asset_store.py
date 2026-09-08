"""Asset store — per-project filesystem layout with safe writes (P1-T03).

Layout (MASTER_PLAN section P1-T03):

    projects/{project_id}/
    ├─ input/        raw script
    ├─ manifests/    storyboard, asset_manifest, render_manifest...
    ├─ audio/        TTS WAVs
    ├─ images/       generated images per scene
    ├─ layers/       prepared layered PNGs
    ├─ scenes/       rendered scene MP4s
    ├─ final/        final MP4 + SRT
    └─ logs/         run logs

Safety guarantees:
- project_id is validated against a safe charset, so path traversal is
  impossible at the root boundary.
- All writes are atomic (temp file + rename).
- Files are written with SHA-256 recorded alongside.
- Regenerate never overwrites: assets get a versioned suffix.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import suppress
from pathlib import Path

from app import config as _discovery

# project_id must be a safe filesystem fragment.
PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")

# Allowed sub-directories under a project.
PROJECT_SUBDIRS = (
    "input",
    "manifests",
    "audio",
    "images",
    "layers",
    "event_assets",
    "scenes",
    "final",
    "logs",
)


class AssetStoreError(Exception):
    """Raised on invalid project_id or path escape attempts."""


class AssetStore:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.base = Path(project_root or _discovery.REPO_ROOT / "projects")

    # --- project layout ----------------------------------------------------
    def validate_project_id(self, project_id: str) -> str:
        if not PROJECT_ID_RE.match(project_id):
            raise AssetStoreError(f"invalid project_id: {project_id!r}")
        return project_id

    def project_dir(self, project_id: str) -> Path:
        self.validate_project_id(project_id)
        return self.base / project_id

    def subdir(self, project_id: str, name: str) -> Path:
        """Return a sub-directory path, enforcing the allowlist."""
        if name not in PROJECT_SUBDIRS:
            raise AssetStoreError(f"unknown subdir: {name!r}")
        path = self.project_dir(project_id) / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def init_project(self, project_id: str) -> Path:
        """Create the full project directory skeleton."""
        root = self.project_dir(project_id)
        for sub in PROJECT_SUBDIRS:
            (root / sub).mkdir(parents=True, exist_ok=True)
        return root

    # --- safe paths --------------------------------------------------------
    def _resolve_inside(self, project_id: str, relative: str) -> Path:
        """Resolve a relative path and refuse any traversal outside the project."""
        self.validate_project_id(project_id)
        root = self.project_dir(project_id).resolve()
        candidate = (root / relative).resolve()
        if not (candidate == root or root in candidate.parents):
            raise AssetStoreError(f"path escape blocked: {relative!r}")
        return candidate

    # --- atomic writes -----------------------------------------------------
    def atomic_write_bytes(self, path: Path, data: bytes) -> str:
        """Write bytes atomically (temp + rename), return the file's SHA-256."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".part")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp_name, path)
        except BaseException:
            with suppress(OSError):
                os.unlink(tmp_name)
            raise
        return sha256_bytes(data)

    def atomic_write_text(self, path: Path, text: str) -> str:
        return self.atomic_write_bytes(path, text.encode("utf-8"))

    # --- project file helpers ----------------------------------------------
    def write_project_file(self, project_id: str, relative: str, data: bytes) -> tuple[Path, str]:
        """Write under the project root, return (absolute path, sha256)."""
        path = self._resolve_inside(project_id, relative)
        digest = self.atomic_write_bytes(path, data)
        return path, digest

    def read_project_file(self, project_id: str, relative: str) -> bytes:
        path = self._resolve_inside(project_id, relative)
        return path.read_bytes()

    # --- versioned assets --------------------------------------------------
    def versioned_path(self, project_id: str, subdir_name: str, stem: str, ext: str, version: int) -> Path:
        """Path like images/scene_001_art_v003.png (never overwrites)."""
        directory = self.subdir(project_id, subdir_name)
        return directory / f"{stem}_v{version:03d}{ext}"

    def write_versioned(
        self,
        project_id: str,
        subdir_name: str,
        stem: str,
        ext: str,
        version: int,
        data: bytes,
    ) -> tuple[Path, str]:
        path = self.versioned_path(project_id, subdir_name, stem, ext, version)
        digest = self.atomic_write_bytes(path, data)
        return path, digest

    # --- manifest helper ---------------------------------------------------
    def write_manifest(self, project_id: str, name: str, payload: dict) -> tuple[Path, str]:
        """Write JSON into manifests and attach a canonical payload digest.

        The digest is computed over the payload without its own ``sha256``
        field, avoiding the self-referential hash that the old implementation
        left as ``null``.
        """
        path = self._resolve_inside(project_id, f"manifests/{name}")
        body = dict(payload)
        body.pop("sha256", None)
        canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        body["sha256"] = sha256_bytes(canonical.encode("utf-8"))
        text = json.dumps(body, ensure_ascii=False, indent=2)
        digest = self.atomic_write_text(path, text)
        return path, digest


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
