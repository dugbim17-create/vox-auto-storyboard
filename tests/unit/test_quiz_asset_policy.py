import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image
from app.services import quiz_asset_resolver as resolver


def question(path):
    return {'id': 'q1', 'question': 'Who?', 'choices': [{'id': 'A', 'text': 'Ronaldo'}, {'id': 'B', 'text': 'Messi'}], 'correct_id': 'A', 'answer_text': 'Cristiano Ronaldo', 'reveal_image_path': str(path)}


def test_unverified_photo_generates_then_reuses_audited_cache(tmp_path, monkeypatch):
    old = tmp_path / 'unknown.png'
    Image.new('RGB', (768, 512), 'red').save(old)
    calls = []
    async def generate(prompt, output_path, model):
        calls.append(prompt)
        Image.new('RGB', (768, 512), 'blue').save(output_path)
        return output_path
    monkeypatch.setattr(resolver, 'generate_ai_image_asset', generate)
    q = question(old)
    first = asyncio.run(resolver.resolve_quiz_assets([q], tmp_path / 'out', allow_generation=True, rights_policy='verified_or_generate'))
    assert first[0]['reveal_image_path'] != str(old)
    assert 'Cristiano Ronaldo' in calls[0]
    assert 'logo' in calls[0].lower()
    second = asyncio.run(resolver.resolve_quiz_assets(first, tmp_path / 'out', allow_generation=False, rights_policy='verified_or_generate'))
    assert first == second
    assert len(calls) == 1
    assert q['reveal_image_path'] == str(old)
    assert (tmp_path / 'out' / 'ASSET_CREDITS.txt').exists()


def test_verified_cc_by_photo_preserved_and_tamper_rejected(tmp_path):
    photo = tmp_path / 'photo.png'
    Image.new('RGB', (768, 512), 'red').save(photo)
    q = question(photo)
    q['reveal_image_rights'] = {'kind': 'licensed', 'license': 'CC-BY-4.0', 'author': 'Example Author', 'source_url': 'https://example.org/photo', 'license_url': 'https://creativecommons.org/licenses/by/4.0/', 'evidence_url': 'https://example.org/photo/license', 'reviewed': True, 'sha256': hashlib.sha256(photo.read_bytes()).hexdigest(), 'changes': 'none'}
    from app.services.quiz_source_review import register_review
    evidence = tmp_path / 'evidence.txt'
    evidence.write_text('Test-only source evidence for Example Author, CC BY 4.0.')
    q['reveal_image_rights'] = register_review(photo, q['reveal_image_rights'], evidence)
    result = asyncio.run(resolver.resolve_quiz_assets([q], tmp_path / 'out', rights_policy='verified_or_generate'))
    assert result[0]['reveal_image_path'] == str(photo.resolve())
    assert 'Example Author' in (tmp_path / 'out' / 'ASSET_CREDITS.txt').read_text()
    Image.new('RGB', (768, 512), 'green').save(photo)
    with pytest.raises(RuntimeError, match='generation'):
        asyncio.run(resolver.resolve_quiz_assets([q], tmp_path / 'out', rights_policy='verified_or_generate'))


def test_unverified_clue_is_not_bypassed(tmp_path):
    photo = tmp_path / 'photo.png'
    Image.new('RGB', (768, 512), 'red').save(photo)
    q = question(photo)
    q['clues'] = [{'image_path': str(photo)}]
    with pytest.raises(RuntimeError, match='generation'):
        asyncio.run(resolver.resolve_quiz_assets([q], tmp_path / 'out', rights_policy='verified_or_generate'))


def test_policy_model_allowlist_excludes_unusable_and_fallback_only_models():
    from app.services.quiz_asset_policy import MODELS

    assert {'gpt-image-2', 'gemini-3.1-flash-image'} <= MODELS
    # 2026-09-12: the CLIProxy route for gpt-image-1.5 ignores `size` (fixed 5:6
    # output), so it can never satisfy slot geometry; keep it out until fixed.
    assert 'gpt-image-1.5' not in MODELS
    # grok-imagine-image is provider-fallback-only; not selectable for quiz assets.
    assert 'grok-imagine-image' not in MODELS


def test_quota_failure_falls_back_to_gemini_and_records_lineage(tmp_path):
    from app.services.quiz_asset_policy import FALLBACK_MODEL, PRIMARY_MODEL, resolve_with_policy

    q = {'id': 'q1', 'question': 'Who?', 'answer_text': 'Cristiano Ronaldo', 'mode': 'photo_reveal',
         'reveal_image_prompt': 'Chibi portrait of a footballer'}
    calls = []

    async def generate(prompt, output_path, model):
        calls.append(model)
        if model == PRIMARY_MODEL:
            raise RuntimeError('All candidate models failed: CLIProxy image (gpt-image-2) HTTP 429: quota exceeded')
        Image.new('RGB', (1536, 1024), 'blue').save(output_path)
        return output_path

    out = tmp_path / 'out'
    first = asyncio.run(resolve_with_policy([q], out, PRIMARY_MODEL, True, generate))
    assert calls == [PRIMARY_MODEL, FALLBACK_MODEL]
    record = first[0]['reveal_image_rights']
    assert record['model'] == FALLBACK_MODEL
    assert record['fallback_from'] == PRIMARY_MODEL
    assert record['fallback_reason'] == 'quota'
    sidecar = Path(first[0]['reveal_image_path']).with_suffix('.rights.json')
    assert json.loads(sidecar.read_text(encoding='utf-8'))['fallback_from'] == PRIMARY_MODEL
    assert 'fallback from' in (out / 'ASSET_CREDITS.txt').read_text(encoding='utf-8')

    async def forbidden(prompt, output_path, model):
        raise AssertionError('a valid fallback asset must be reused, not regenerated')

    second = asyncio.run(resolve_with_policy([q], out, PRIMARY_MODEL, True, forbidden))
    assert second[0]['reveal_image_path'] == first[0]['reveal_image_path']
    assert calls == [PRIMARY_MODEL, FALLBACK_MODEL]


def test_moderation_failure_never_reroutes_to_fallback(tmp_path):
    from app.services.quiz_asset_policy import PRIMARY_MODEL, resolve_with_policy

    q = {'id': 'q1', 'question': 'Who?', 'answer_text': 'Cristiano Ronaldo', 'mode': 'photo_reveal',
         'reveal_image_prompt': 'Chibi portrait of a footballer'}
    calls = []

    async def generate(prompt, output_path, model):
        calls.append(model)
        raise RuntimeError('All candidate models failed: CLIProxy image (gpt-image-2) HTTP 400: moderation_blocked')

    with pytest.raises(RuntimeError, match='moderation'):
        asyncio.run(resolve_with_policy([q], tmp_path / 'out', PRIMARY_MODEL, True, generate))
    assert calls == [PRIMARY_MODEL]
