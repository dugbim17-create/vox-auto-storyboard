"""Conservative image reuse policy, not a legal clearance or identity verifier.

External evidence must be reviewed outside the generator. Never trust a license
invented by the script LLM. Generated images still require visual approval.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from PIL import Image
from app.services.quiz_image_layout import layout_prompt, inspect_layout
from app.services.quiz_source_review import has_review_receipt

VERSION = 'quiz-rights-v1'
MODELS = {'gpt-image-2', 'gpt-image-1.5', 'gemini-3.1-flash-image'}
LICENSES = {'CC0-1.0', 'CC-BY-3.0', 'CC-BY-4.0', 'PUBLIC-DOMAIN', 'OWNED'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def valid_record(path, record, *, prompt=None, model=None):
    try:
        with Image.open(path) as image:
            image.load()
        if not isinstance(record, dict) or record.get('sha256') != digest(path):
            return False
        if record.get('kind') == 'ai_generated':
            return (record.get('policy') == VERSION and record.get('model') == model
                    and record.get('prompt') == prompt and bool(prompt))
        return (record.get('kind') == 'licensed' and record.get('reviewed') is True
                and has_review_receipt(path, record)
                and record.get('license') in LICENSES
                and all(record.get(k) for k in ('author', 'source_url', 'license_url', 'evidence_url', 'changes')))
    except (OSError, ValueError, TypeError):
        return False


async def resolve_with_policy(questions, output_dir, model, allow_generation, generate):
    if model not in MODELS:
        raise ValueError('Image model not approved for Quiz rights policy')
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = deepcopy(questions)
    records = []

    async def resolve(owner, field, prompt_field, rights_field, kind, fallback):
        if not owner.get(field) and not owner.get(prompt_field) and not fallback:
            return
        subject = owner.get(prompt_field) or fallback
        if not subject:
            raise RuntimeError('Asset unresolved; generation needs a meaningful subject prompt')
        prompt = layout_prompt(
            f'{subject}\nCreate an original editorial illustration, not an archival photograph. '
            'Do not copy a specific photograph, artwork or artist style. No sponsor logo, '
            'watermark, trademark graphics or implied endorsement. No embedded answer text.', kind)
        existing = owner.get(field)
        record = owner.get(rights_field)
        if existing and valid_record(existing, record, prompt=prompt, model=model):
            target = Path(existing).resolve()
        else:
            identity = hashlib.sha256(f'{VERSION}|{model}|{prompt}'.encode()).hexdigest()
            target = output_dir / f'{identity}.png'
            sidecar = target.with_suffix('.rights.json')
            try:
                record = json.loads(sidecar.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                record = None
            if not valid_record(target, record, prompt=prompt, model=model):
                if not allow_generation:
                    raise RuntimeError('Unverified asset; generation permission required. Use Generate Quiz Assets first.')
                # Never overwrite an existing candidate with absent or mismatched provenance.
                if target.exists():
                    target = output_dir / f'{identity}-{uuid4().hex[:8]}.png'
                    sidecar = target.with_suffix('.rights.json')
                await generate(prompt, target, model=model)
                inspect_layout(target, kind, generated=True)
                with Image.open(target) as image:
                    image.load()
                record = {'kind': 'ai_generated', 'policy': VERSION, 'model': model,
                          'prompt': prompt, 'sha256': digest(target),
                          'legal_clearance': False, 'visual_review': 'required'}
                sidecar.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        owner[field] = str(target.resolve())
        owner[rights_field] = record
        layout_field = 'image_layout' if field == 'image_path' else field.replace('_path', '') + '_layout'
        owner[layout_field] = inspect_layout(target, kind, generated=record.get('kind') == 'ai_generated')
        records.append({'path': str(target.resolve()), **record})

    for q in result:
        answer = q.get('answer_text') or next((c.get('text') for c in q.get('choices', []) if c.get('id') == q.get('correct_id')), '')
        for c in q.get('cards', []):
            await resolve(c, 'image_path', 'image_prompt', 'image_rights', 'card', c.get('text') or c.get('label'))
        for c in q.get('clues', []):
            if c.get('image_path') or c.get('image_prompt'):
                await resolve(c, 'image_path', 'image_prompt', 'image_rights', 'card', c.get('word') or c.get('prompt'))
        if q.get('scene_image') or q.get('scene_prompt'):
            await resolve(q, 'scene_image', 'scene_prompt', 'scene_image_rights', 'scene', q.get('question'))
        if q.get('reveal_image_path') or q.get('reveal_image_prompt') or q.get('mode') == 'photo_reveal':
            await resolve(q, 'reveal_image_path', 'reveal_image_prompt', 'reveal_image_rights', 'reveal', f'Clearly recognizable illustration of {answer}' if answer else None)
        for side in ('side_a', 'side_b'):
            if isinstance(q.get(side), dict) and q[side].get('image_path'):
                await resolve(q[side], 'image_path', 'image_prompt', 'image_rights', 'card', q[side].get('text') or q[side].get('name'))
    (output_dir / 'asset_provenance.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    credits = ['Image source records; not a guarantee against copyright claims. AI illustrations are not archival photos.']
    for r in records:
        if r['kind'] == 'licensed':
            credits.append(f"{r['path']}\n{r['author']} | {r['source_url']} | {r['license']} | {r['license_url']} | Changes: {r['changes']}")
        else:
            credits.append(f"{r['path']}\nAI illustration | {r['model']} | visual review required")
    (output_dir / 'ASSET_CREDITS.txt').write_text('\n\n'.join(credits), encoding='utf-8')
    return result
