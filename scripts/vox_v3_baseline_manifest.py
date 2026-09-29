"""Phase 0 Baseline & Protected Inventory Manifest Tool.

Scans all protected decision-changing files, builds canonical SHA-256 inventory,
and verifies integrity before and after Phase 0 runs.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Protected roots / files
PROTECTED_PATTERNS = [
    "pyproject.toml",
    "uv.lock",
    "app/**/*.py",
    "app/**/*.json",
    "workers/**/*.py",
    "workers/**/*.json",
    ".hermes/plans/2026-08-22_105341-vox-10-of-10-deep-fix-plan.md",
    ".hermes/missions/2026-08-22_phase0_gemini-coder.md",
    "dist/vox-studio-v0.7.0/**/*",
    "dist/vox-studio-v0.7.0-pro/**/*",
    "projects/prj_1787139301_all_vox_styles_2min_master/**/*",
    "tests/unit/**/*.py",
    "tests/fixtures/sample_storyboard_3scenes.json",
    "tests/fixtures/sample_script.txt",
    "tests/fixtures/omnivoice_probe.wav",
    "tests/fixtures/antigravity_image_probe.jpg",
    "tests/fixtures/cliproxy_image_probe.png",
]


def sha256_file(path: Path) -> str:
    """Compute SHA-256 checksum of a file in 64KB blocks."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def collect_protected_files(root: Path = PROJECT_ROOT) -> list[Path]:
    """Find all matching files under protected patterns."""
    found: set[Path] = set()
    for pattern in PROTECTED_PATTERNS:
        for p in root.glob(pattern):
            if p.is_file():
                found.add(p.resolve())
    return sorted(found, key=lambda p: p.relative_to(root).as_posix())


def build_manifest(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Build canonical manifest for all protected files."""
    files = collect_protected_files(root)
    entries: list[dict[str, Any]] = []

    total_bytes = 0
    tree_hasher = hashlib.sha256()

    for file_path in files:
        rel_path = file_path.relative_to(root).as_posix()
        stat = file_path.stat()
        file_hash = sha256_file(file_path)
        mtime_iso = datetime.datetime.fromtimestamp(
            stat.st_mtime, tz=datetime.UTC
        ).isoformat()

        entry = {
            "path": rel_path,
            "size_bytes": stat.st_size,
            "mtime_iso": mtime_iso,
            "mtime_epoch": stat.st_mtime,
            "sha256": file_hash,
        }
        entries.append(entry)
        total_bytes += stat.st_size

        # Combine into tree digest
        tree_hasher.update(f"{rel_path}:{stat.st_size}:{file_hash}\n".encode())

    manifest = {
        "manifest_version": "1.0",
        "phase": "phase0",
        "created_at_iso": datetime.datetime.now(datetime.UTC).isoformat(),
        "hash_algorithm": "SHA-256 (64KB chunked buffer)",
        "sorting_convention": "POSIX relative path ascending alphabetical",
        "project_root": str(root),
        "total_files": len(entries),
        "total_bytes": total_bytes,
        "protected_tree_sha256": tree_hasher.hexdigest(),
        "entries": entries,
    }
    return manifest


def verify_manifest(
    manifest_path: Path, root: Path = PROJECT_ROOT
) -> tuple[bool, list[str]]:
    """Compare current filesystem state against manifest."""
    with open(manifest_path, encoding="utf-8") as f:
        saved = json.load(f)

    current = build_manifest(root)

    saved_entries = {e["path"]: e for e in saved["entries"]}
    current_entries = {e["path"]: e for e in current["entries"]}

    diffs: list[str] = []

    # Check removed or added
    for p in saved_entries:
        if p not in current_entries:
            diffs.append(f"MISSING: {p}")
        elif saved_entries[p]["sha256"] != current_entries[p]["sha256"]:
            diffs.append(
                f"MUTATED: {p} (saved={saved_entries[p]['sha256']} vs current={current_entries[p]['sha256']})"
            )

    for p in current_entries:
        if p not in saved_entries:
            diffs.append(f"UNEXPECTED_NEW: {p}")

    return (len(diffs) == 0, diffs)


def main() -> None:
    manifest_dir = PROJECT_ROOT / ".hermes" / "evidence" / "vox-v3" / "phase0"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "baseline_manifest.json"

    print(f"Collecting protected files from {PROJECT_ROOT}...")
    manifest = build_manifest(PROJECT_ROOT)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Manifest written to {manifest_path}")
    print(f"Total protected files: {manifest['total_files']}")
    print(f"Total protected bytes: {manifest['total_bytes']}")
    print(f"Protected tree SHA256: {manifest['protected_tree_sha256']}")

    # Verify readback
    ok, diffs = verify_manifest(manifest_path, PROJECT_ROOT)
    if ok:
        print("VERIFICATION: PASS (manifest is readable and matches current state)")
    else:
        print("VERIFICATION: FAIL", diffs)


if __name__ == "__main__":
    main()
