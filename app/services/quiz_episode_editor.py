"""Non-destructive episode editing; no provider or audio side effects."""
from copy import deepcopy
import json
from pathlib import Path
from app.services.quiz_channel_profiles import get_profile


def episode_spec(doc):
    key = doc.get('channel_profile', '')
    p = get_profile(key) if key else {}
    return {'channel_profile': key, 'series': doc.get('series', ''),
            'duration_target_minutes': doc.get('duration_target_minutes', p.get('minutes', [10,15]))}


def validate_episode(doc):
    seen = set()
    for q in doc.get('questions', []):
        text = str(q.get('question','')).strip().casefold()
        if not text or text in seen:
            raise ValueError('Empty or duplicate question')
        seen.add(text)


def update_question(doc, qid, changes):
    result = deepcopy(doc)
    target = next((q for q in result['questions'] if q['id']==qid), None)
    if target is None:
        raise ValueError('Question not found')
    target.update(deepcopy(changes))
    target['id'] = qid
    result['episode_revision'] = result.get('episode_revision',0)+1
    result['approval'] = {'status':'draft'}
    return result


def next_question_variant(question, changes):
    out = deepcopy(question)
    out.update(changes)
    out['id'] = question['id']
    out['revision_reason'] = 'targeted_variant'
    return out


def record_observation(path, row):
    import math
    for key in ('channel_profile','video_id','period'):
        if not str(row.get(key) or '').strip():
            raise ValueError(f'Missing {key}')
    get_profile(row['channel_profile'])
    for key in ('views','subscribers_gained','watch_hours','ctr','avg_percentage_viewed'):
        value = row.get(key)
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f'Invalid {key}')
            if key in ('ctr','avg_percentage_viewed') and value > 100:
                raise ValueError(f'Invalid percent: {key}')
    path = Path(path)
    rows = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    row = deepcopy(row)
    for key in ('watch_hours','ctr','avg_percentage_viewed'):
        row.setdefault(key,None)
    identity = tuple(row.get(k) for k in ('channel_profile','video_id','period'))
    if any(tuple(r.get(k) for k in ('channel_profile','video_id','period'))==identity for r in rows):
        raise ValueError('Duplicate observation; preserve previous measurement')
    rows.append(row)
    temporary = path.with_suffix('.pending.json')
    temporary.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)
