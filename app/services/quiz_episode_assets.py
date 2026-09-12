"""Stable per-episode asset directory and explicitly selected request ceiling."""
from pathlib import Path
import re
import uuid


def episode_asset_dir(document, output_dir, *, create=False):
    settings = document.get('asset_generation') or {}
    ident = settings.get('episode_id')
    if not ident and create:
        ident = uuid.uuid4().hex
        settings = dict(settings, episode_id=ident)
        document['asset_generation'] = settings
    if ident:
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', str(ident)):
            raise ValueError('Invalid episode asset identity')
        return Path(output_dir) / 'episodes' / ident / 'assets'
    # Existing drafts retain their existing cache location until explicit generation.
    return Path(output_dir) / 'assets'
