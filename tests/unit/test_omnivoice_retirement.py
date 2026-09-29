"""Retirement must not contact an old worker or load its model."""
import asyncio
import ast
from pathlib import Path
import runpy

import pytest

from app.providers.tts.omnivoice import OmniVoiceProvider, OmniVoiceUnavailable

ROOT = Path(__file__).resolve().parents[2]


def test_adapter_never_contacts_worker():
    # No constructor/client: any attempted network access fails this gate.
    provider = object.__new__(OmniVoiceProvider)

    async def check():
        health = await provider.health()
        assert health.status == 'unavailable'
        with pytest.raises(OmniVoiceUnavailable):
            await provider.synthesize(None)
        with pytest.raises(OmniVoiceUnavailable):
            await provider.warmup()

    asyncio.run(check())


def test_worker_refuses_before_importing_synth():
    path = ROOT / 'workers/omnivoice_worker/main.py'
    with pytest.raises(RuntimeError, match='OmniVoice retired'):
        runpy.run_path(str(path))


def test_launcher_blocks_before_starting_uvicorn():
    text = (ROOT / 'scripts/start_omnivoice_worker.ps1').read_text(encoding='utf-8')
    assert text.index('throw "OmniVoice retired.') < text.index('& $venvPython -m uvicorn')


def test_modified_modules_parse():
    for rel in ['app/providers/tts/omnivoice.py', 'workers/omnivoice_worker/main.py']:
        ast.parse((ROOT / rel).read_text(encoding='utf-8'))
