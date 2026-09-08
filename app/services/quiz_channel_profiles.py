"""Opt-in channel products. Legacy VI/EN documents remain untouched."""
from copy import deepcopy
import json
from pathlib import Path

VERSION = 1
PROFILES = {
    'de-football': dict(name='DE · Football Fan Battle', locale='de-DE', market='DE', audience='14–34', persona='football_fan_battle', timer=5, speed=1.08, theme='blue', energy='competitive, youthful, not childish', address='du', pillars=['career_path', 'Bundesliga', 'Champions League', 'stats_battle'], hook='Wie gut kennst du den Fußball?', cta='In der nächsten Runde wartet die Champions League auf dich.', fact=False, minutes=[10,15]),
    'de-wissen': dict(name='DE · Wissen & Rechtschreibung', locale='de-DE', market='DE', audience='35–65', persona='knowledge_trainer', timer=8, speed=0.98, theme='dark_gold', energy='calm, clear, mature, encouraging', address='du', pillars=['Rechtschreibung', 'Sprichwörter', 'Geografie', 'Geschichte'], hook='Teste dein Wissen – eine Frage nach der anderen.', cta='In der nächsten Runde testen wir deine Rechtschreibung.', fact=True, minutes=[12,18]),
    'fr-culture': dict(name='FR · Culture française', locale='fr-FR', market='FR', audience='25–54', persona='culture_expert', timer=7, speed=1.0, theme='purple', energy='elegant, warm, curious, not sensational', address='vous', pillars=['proverbes', 'géographie', 'histoire', 'cuisine', 'littérature'], hook='Connaissez-vous vraiment la culture française ?', cta='Retrouvez-nous pour un prochain défi consacré aux expressions françaises.', fact=True, minutes=[10,14]),
    'it-calcio': dict(name='IT · Calcio Fan Challenge', locale='it-IT', market='IT', audience='14–34', persona='calcio_fan_challenge', timer=5, speed=1.08, theme='forest', energy='passionate, lively, friendly competition', address='tu', pillars=['Serie A', 'leggende', 'carriera', 'statistiche'], hook='Quanto ne sai davvero di calcio?', cta='Nella prossima sfida ti aspettano le leggende della Serie A.', fact=False, minutes=[10,15]),
}
LABELS = {
    'de': dict(question='FRAGE', answer='ANTWORT', correct='RICHTIG!', hint='HINWEIS', choose='WÄHLE DIE RICHTIGE ANTWORT', score='DEIN ERGEBNIS', comment='Wie viele Antworten waren richtig?', levels=['AUFWÄRMEN','FORTGESCHRITTEN','EXPERTE','FINALE']),
    'fr': dict(question='QUESTION', answer='RÉPONSE', correct='EXACT !', hint='INDICE', choose='CHOISISSEZ LA BONNE RÉPONSE', score='VOTRE RÉSULTAT', comment='Combien de bonnes réponses avez-vous trouvées ?', levels=['ÉCHAUFFEMENT','INTERMÉDIAIRE','EXPERT','FINALE']),
    'it': dict(question='DOMANDA', answer='RISPOSTA', correct='ESATTO!', hint='INDIZIO', choose='SCEGLI LA RISPOSTA GIUSTA', score='IL TUO RISULTATO', comment='Quante risposte hai indovinato?', levels=['RISCALDAMENTO','INTERMEDIO','ESPERTO','FINALE']),
}


from app.services.quiz_locales import LOCALES, locale_labels

for _locale, (_market, _address, _hook, _cta) in LOCALES.items():
    PROFILES['locale-' + _locale] = dict(name=f'{_locale} · Knowledge', locale=_locale,
        market=_market, audience='adult/general', persona='knowledge_trainer', timer=7,
        speed=1.0, theme='blue', energy='natural, clear, friendly', address=_address,
        pillars=['knowledge', 'culture', 'logic'], hook=_hook, cta=_cta, fact=True, minutes=[10,15])


def get_profile(key):
    if key not in PROFILES:
        raise ValueError(f'Unknown channel profile: {key}')
    return deepcopy(PROFILES[key])


def labels(key):
    locale = get_profile(key)['locale']
    return deepcopy(LABELS[locale.split('-')[0]]) if locale.split('-')[0] in LABELS else locale_labels(locale)


def editorial_brief(key):
    p = get_profile(key)
    return ('CHANNEL PRODUCT (not a translation template):\n' + json.dumps(p, ensure_ascii=False) +
        '\nWrite natively for this country and audience. Keep the specified form of address consistent. '
        'Visual prompts may be English, all audience-facing text must use the locale. '
        'Use a warmup-to-final difficulty curve. Every question needs voice_q and voice_a. '
        'Supply series, difficulty, source_url and fact_checked_at for factual claims; never invent sources. '
        'Time-sensitive football stats require an explicit season/as-of date. '
        'Use original text/stat graphics; no unlicensed player photos, club logos, film stills or footage. '
        'Add title_candidate and thumbnail_text to the first question. '
        'Include a short verified fact in voice_a where fact=true. Never claim native review passed. '
        'Do not promise a publishing date unless supplied by the user. Do not pad duration with silence.')


def bind_profile(document, key):
    p = get_profile(key)
    doc = deepcopy(document)
    doc.update(channel_profile=key, channel_profile_version=VERSION, language=p['locale'])
    doc.setdefault('settings', {}).update(piper_speed=p['speed'])
    doc['approval'] = {'status':'draft'}
    doc['editorial_qa'] = review_content(doc)
    return doc


def review_content(doc):
    key = doc.get('channel_profile')
    if not key:
        return {'status':'legacy', 'issues':[]}
    p = get_profile(key)
    issues = []
    if doc.get('language') != p['locale']:
        issues.append('LOCALE_MISMATCH')
    seen = set()
    for q in doc.get('questions', []):
        text = str(q.get('question','')).strip().casefold()
        if text in seen:
            issues.append(f"DUPLICATE:{q.get('id')}")
        seen.add(text)
        spoken = ' '.join(str(q.get(k,'')) for k in ('question','voice_q','voice_a','intro_text','outro_text'))
        forbidden = []
        if not p['locale'].startswith('vi'):
            forbidden += ['đáp án','câu hỏi','chào mừng']
        if not p['locale'].startswith('en'):
            forbidden += ['correct answer','like and subscribe']
        if any(token in spoken.casefold() for token in forbidden):
            issues.append(f"LANGUAGE_LEAK:{q.get('id')}")
        if not q.get('source_url'):
            issues.append(f"FACT_SOURCE_REQUIRED:{q.get('id')}")
        if not q.get('voice_a'):
            issues.append(f"ANSWER_NARRATION_REQUIRED:{q.get('id')}")
    return {'status':'NATIVE_REVIEW_REQUIRED', 'issues':issues,
            'note':'Rule-based screening only; fluency, facts and pronunciation are not certified.'}


def require_voice(key, voice, model_dir):
    locale = get_profile(key)['locale'].replace('-', '_')
    if not voice.startswith(locale + '-'):
        raise ValueError(f'Voice locale mismatch: {voice}; requires {locale}')
    path = Path(model_dir) / f'{voice}.onnx'
    config = path.with_suffix('.onnx.json')
    if not path.is_file() or not config.is_file():
        raise ValueError(f'Voice model/config missing: {path}')
    data = json.loads(config.read_text(encoding='utf-8'))
    if data.get('language', {}).get('code') != locale:
        raise ValueError(f'Voice config locale mismatch: expected {locale}')
    return path
