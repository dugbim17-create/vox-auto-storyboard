import pytest


def test_four_profiles_are_distinct_and_unknown_fails():
    from app.services.quiz_channel_profiles import PROFILES, get_profile, editorial_brief
    assert {'de-football', 'de-wissen', 'fr-culture', 'it-calcio'} <= set(PROFILES)
    assert get_profile('de-wissen')['timer'] > get_profile('de-football')['timer']
    assert len({editorial_brief(k) for k in PROFILES}) == len(PROFILES)
    with pytest.raises(ValueError):
        get_profile('unknown')


def test_profile_binding_preserves_content_and_invalidates_review():
    from app.services.quiz_channel_profiles import bind_profile
    doc = {'engine_v2': True, 'questions': [{'id':'q', 'question':'Original'}], 'approval':{'status':'approved'}}
    result = bind_profile(doc, 'fr-culture')
    assert result['language'] == 'fr-FR'
    assert result['questions'] == doc['questions']
    assert result['approval']['status'] == 'draft'
    assert 'channel_profile' not in doc


def test_voice_mismatch_fails_before_synthesis(tmp_path):
    from app.services.quiz_channel_profiles import require_voice
    with pytest.raises(ValueError, match='locale'):
        require_voice('de-football', 'manh_dung', tmp_path)


def test_analytics_unknown_is_not_zero_and_short_hours_not_ypp():
    from app.services.quiz_channel_analytics import summarize
    unknown = summarize([])
    assert unknown['subscribers_per_1k_views'] is None
    assert unknown['decision'] == 'INSUFFICIENT_DATA'
    report = summarize([{'video_id':'v', 'period':'28d', 'views':1000, 'subscribers_gained':8, 'watch_hours':80, 'format':'shorts'}])
    assert report['qualified_longform_hours_estimate'] == 0
    assert report['subscribers_per_1k_views'] == 8


def test_generator_receives_locale_and_persona(monkeypatch):
    import json
    from app.services import quiz_ai_generator as generator
    seen = []
    def call(messages):
        seen.extend(messages)
        return json.dumps([{'id':'q','question':'Quelle ville ?', 'choices':[
            {'id':'A','text':'Paris'},{'id':'B','text':'Lyon'}], 'correct_id':'A'}])
    monkeypatch.setattr(generator, '_call_cliproxy_llm', call)
    output = generator.generate_quiz_json_with_ai('capitales', count=1, format_type='photo_reveal', channel_profile='fr-culture')
    prompt = ' '.join(m['content'] for m in seen)
    assert 'Strictly fr-FR' in prompt
    assert 'culture_expert' in prompt
    assert output[0]['countdown_seconds'] == 7
    assert output[0]['intro_text']


def test_metrics_reject_overlapping_windows_and_channels():
    from app.services.quiz_channel_analytics import summarize
    with pytest.raises(ValueError, match='window'):
        summarize([{'period':'7d'}, {'period':'28d'}])
    with pytest.raises(ValueError, match='channel'):
        summarize([{'channel_profile':'de-football'}, {'channel_profile':'it-calcio'}])
