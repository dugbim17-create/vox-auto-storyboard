"""Small custom-quiz adapter: byte-bound human review and immutable JSON snapshots.

Schema validation is not semantic approval. Only an explicit review action creates
approval; model output must never be allowed to supply it at import.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import uuid

from app.services.quiz_v2_contract import validate_questions


def content_fingerprint(document: dict) -> str:
    questions = document.get("questions")
    validate_questions(questions, require_assets=True)
    assets = []
    for question in questions:
        paths = [c.get("image_path") for c in question.get("cards", [])]
        paths += [question.get("scene_image"), question.get("reveal_image_path")]
        for value in filter(None, paths):
            path = Path(value)
            assets.append({"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    payload = {"questions": questions, "assets": assets, "language": document.get("language", "auto")}
    if document.get("narration") is not None:
        payload["narration"] = document.get("narration")
    if document.get("speech_inputs") is not None:
        payload["speech_inputs"] = document.get("speech_inputs")
    if document.get("channel_profile"):
        payload["channel_profile"] = document["channel_profile"]
        payload["channel_profile_version"] = document.get("channel_profile_version")
    style = document.get("visual_style")
    if style is not None:
        if not isinstance(style, dict):
            raise ValueError("visual_style must be an object")
        from app.services.quiz_style_packs import resolve_style_snapshot
        payload["visual_style"] = resolve_style_snapshot(
            str(style.get("id") or ""),
            locale=str(style.get("locale") or payload["language"] or "en-US"),
            motion=str(style.get("motion") or "medium"),
            mascot=style.get("mascot", False),
            snapshot_override=style.get("snapshot"),
            version=style.get("version"),
        )
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def approve_document(document: dict) -> dict:
    approved = deepcopy(document)
    approved["approval"] = {"status": "approved", "reviewer": "human",
                            "content_fingerprint": content_fingerprint(document)}
    return approved


def require_review(document: dict) -> None:
    approval = document.get("approval") or {}
    if (approval.get("status") != "approved" or approval.get("reviewer") != "human"
            or approval.get("content_fingerprint") != content_fingerprint(document)):
        raise ValueError("Content/asset review required: hãy xem ảnh, kiểm tra manh mối và duyệt đúng bản hiện tại trước khi render.")


def save_document(document: dict, directory: Path) -> Path:
    validate_questions(document.get("questions"), require_assets=False)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    # Never replace an earlier draft, including one with a valid master.
    destination = directory / f"quiz-draft-{uuid.uuid4().hex}.json"
    payload = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False)
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(payload)
    if load_document(destination) != document:
        raise RuntimeError("Quiz draft readback mismatch")
    return destination


def load_document(path: Path) -> dict:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not document.get("engine_v2"):
        raise ValueError("Not a custom Quiz V2 document")
    validate_questions(document.get("questions"), require_assets=False)
    return document
