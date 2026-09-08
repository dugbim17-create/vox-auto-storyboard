def test_episode_spec_and_versioned_update():
    from app.services.quiz_episode_editor import episode_spec, update_question
    doc = {'engine_v2': True, 'channel_profile': 'fr-culture', 'title': 'Old', 'questions': [
        {'id': 'q1', 'question': 'Ancienne', 'choices': [{'id':'A','text':'Paris'}], 'correct_id':'A'},
    ]}
    spec = episode_spec(doc)
    assert spec['channel_profile'] == 'fr-culture'
    assert spec['duration_target_minutes'] == [10, 14]
    result = update_question(doc, 'q1', {'question': 'Nouvelle', 'voice_q': 'Nouvelle ?'})
    assert result['questions'][0]['question'] == 'Nouvelle'
    assert result['questions'][0]['voice_q'] == 'Nouvelle ?'
    assert result['episode_revision'] == 1
    assert result['approval']['status'] == 'draft'
    assert doc['questions'][0]['question'] == 'Ancienne'


def test_episode_guardrails_and_next_variant():
    import pytest
    from app.services.quiz_episode_editor import validate_episode, next_question_variant
    with pytest.raises(ValueError, match='duplicate'):
        validate_episode({'questions': [
            {'id':'q1','question':'Same','choices':[{'id':'A','text':'x'}],'correct_id':'A'},
            {'id':'q2','question':' same ','choices':[{'id':'A','text':'x'}],'correct_id':'A'}]})
    q = {'id':'q1','question':'Paris?','choices':[{'id':'A','text':'Paris'}],'correct_id':'A'}
    out = next_question_variant(q, {'question':'Quelle ville est la capitale de la France?'})
    assert out['id'] == 'q1'
    assert out['question'].startswith('Quelle')
    assert out['revision_reason'] == 'targeted_variant'


def test_analytics_ledger_records_observation_without_zero_fill(tmp_path):
    from app.services.quiz_episode_editor import record_observation
    path = tmp_path / 'ledger.json'
    record_observation(path, {'channel_profile':'de-football','video_id':'v1','period':'7d','views':100,'subscribers_gained':2})
    import json
    rows = json.loads(path.read_text())
    assert rows[0]['views'] == 100
    assert rows[0]['watch_hours'] is None
    assert rows[0]['video_id'] == 'v1'
