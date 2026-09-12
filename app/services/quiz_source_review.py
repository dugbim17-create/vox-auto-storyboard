"""Explicit local source review, kept separate from imported quiz JSON.

A receipt proves a local review action and unchanged evidence, not legal truth.
Do not call register_review from an LLM/script import path.
"""
import hashlib
import json
from pathlib import Path


def register_review(image_path, record, evidence_path):
    image = Path(image_path).resolve()
    evidence = Path(evidence_path).resolve()
    raw = evidence.read_bytes()
    if not raw:
        raise ValueError('Source evidence file is empty')
    reviewed = dict(record)
    reviewed['sha256'] = hashlib.sha256(image.read_bytes()).hexdigest()
    reviewed['reviewed'] = True
    receipt = {'record': reviewed, 'evidence_path': str(evidence),
               'evidence_sha256': hashlib.sha256(raw).hexdigest(), 'review_action': 'explicit_local_review'}
    destination = image.with_suffix(image.suffix + '.license-review.json')
    # Preserve earlier evidence rather than silently replacing an approval.
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
    return reviewed


def has_review_receipt(image_path, record):
    try:
        image = Path(image_path)
        receipt = json.loads(image.with_suffix(image.suffix + '.license-review.json').read_text(encoding='utf-8'))
        return (receipt['review_action'] == 'explicit_local_review' and receipt['record'] == record
                and hashlib.sha256(Path(receipt['evidence_path']).read_bytes()).hexdigest() == receipt['evidence_sha256'])
    except (OSError, ValueError, KeyError, TypeError):
        return False
