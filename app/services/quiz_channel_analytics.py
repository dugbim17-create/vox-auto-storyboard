"""User-owned CSV measurements. Unknown is not zero; no scraped proxy as analytics."""
import csv
import math
from pathlib import Path

FIELDS = ['channel_profile','video_id','series','period','format','views','subscribers_gained','watch_hours','ctr','avg_percentage_viewed']


def read_metrics(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    seen = set()
    for row in rows:
        identity = (row.get('channel_profile'), row.get('video_id'), row.get('period'))
        if identity in seen:
            raise ValueError(f'Duplicate measurement: {identity}')
        seen.add(identity)
        if not row.get('video_id') or row.get('format') not in ('longform','shorts'):
            raise ValueError('video_id and format longform/shorts required')
        for field in FIELDS[5:]:
            raw = row.get(field)
            row[field] = None if raw in ('', None) else float(raw)
            if row[field] is not None and (not math.isfinite(row[field]) or row[field] < 0):
                raise ValueError(f'Invalid {field}')
        for field in ('ctr','avg_percentage_viewed'):
            if row[field] is not None and row[field] > 100:
                raise ValueError(f'{field} must be percent 0..100')
    return rows


def summarize(rows):
    if len({r.get('channel_profile') for r in rows}) > 1:
        raise ValueError('Select one channel; do not mix channel experiments')
    if len({r.get('period') for r in rows}) > 1:
        raise ValueError('Compare one observation window at a time; do not sum overlapping snapshots')
    views = sum(r.get('views') or 0 for r in rows)
    paired = [r for r in rows if r.get('views') is not None and r.get('subscribers_gained') is not None]
    paired_views = sum(r['views'] for r in paired)
    subs_rate = sum(r['subscribers_gained'] for r in paired)*1000/paired_views if paired_views else None
    long = [r for r in rows if r.get('format') == 'longform']
    hours = sum(r.get('watch_hours') or 0 for r in long)
    decision = 'INSUFFICIENT_DATA'
    if len(rows) >= 10 and paired_views >= 10000 and subs_rate is not None:
        decision = 'REVIEW_CTA_OR_PILLAR' if subs_rate < 2 else 'CONTINUE_TEST'
        if subs_rate >= 6:
            decision = 'PROMISING_CHECK_RETENTION'
    return {'videos':len(rows), 'views':views, 'subscribers_per_1k_views':subs_rate,
            'qualified_longform_hours_estimate':hours,
            'hours_missing':sum(r.get('watch_hours') is None for r in long),
            'decision':decision, 'note':'Operational heuristics, not YouTube benchmarks. Studio Earn is authoritative for qualified hours. No automatic kill/scale.'}


def write_template(path):
    with Path(path).open('x', encoding='utf-8', newline='') as stream:
        csv.writer(stream).writerow(FIELDS)
