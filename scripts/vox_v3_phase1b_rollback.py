"""Phase 1B Pre-Write Rollback Creator and Verifier.

Creates an immutable rollback directory under .hermes/rollback/pre_vox_semantic_v3_phase1b_<timestamp>/
containing copies of all Phase 1 files scheduled for modification in Phase 1B,
along with a SHA-256 manifest.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CANDIDATE_FILES_TO_BACKUP = [
    "app/schemas/story_evidence.py",
    "app/services/claim_asset_validator.py",
    "app/services/script_analysis.py",
    "app/schemas/__init__.py",
    "app/services/__init__.py",
    "tests/unit/test_story_evidence.py",
    "tests/unit/test_claim_asset_validator.py",
    "tests/unit/test_storyboard_evidence_contract.py",
    "tests/acceptance/test_vox_v3_baseline_red.py",
    "scripts/vox_v3_phase1_evidence.py",
]


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def create_rollback() -> Path:
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d_%H%M%S")
    rollback_dir = PROJECT_ROOT / ".hermes" / "rollback" / f"pre_vox_semantic_v3_phase1b_{timestamp}"
    rollback_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, Any]] = []

    for rel_path in CANDIDATE_FILES_TO_BACKUP:
        src = PROJECT_ROOT / rel_path
        if not src.is_file():
            continue
        dst = rollback_dir / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

        src_hash = sha256_file(src)
        dst_hash = sha256_file(dst)
        assert src_hash == dst_hash, f"Backup hash mismatch for {rel_path}"

        stat = src.stat()
        entries.append({
            "path": rel_path,
            "size_bytes": stat.st_size,
            "sha256": src_hash,
            "mtime_epoch": stat.st_mtime,
        })

    manifest = {
        "manifest_version": "1.0",
        "phase": "phase1b",
        "created_at_iso": datetime.datetime.now(datetime.UTC).isoformat(),
        "rollback_dir": str(rollback_dir.relative_to(PROJECT_ROOT).as_posix()),
        "total_files": len(entries),
        "entries": entries,
    }

    manifest_path = rollback_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Created Phase 1B rollback directory: {rollback_dir}")
    print(f"Backed up {len(entries)} files. Manifest SHA-256: {sha256_file(manifest_path)}")
    return rollback_dir


def verify_rollback(rollback_dir: Path) -> bool:
    manifest_path = rollback_dir / "manifest.json"
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    for entry in manifest["entries"]:
        backup_file = rollback_dir / entry["path"]
        if not backup_file.is_file():
            print(f"FAILED: missing backup file {backup_file}")
            return False
        h = sha256_file(backup_file)
        if h != entry["sha256"]:
            print(f"FAILED: hash mismatch for {backup_file}")
            return False

    print("VERIFICATION: PASS (Phase 1B Rollback is readable and all backup hashes match)")
    return True


if __name__ == "__main__":
    rb_dir = create_rollback()
    ok = verify_rollback(rb_dir)
    assert ok, "Phase 1B Rollback verification failed!"
