import json
from app.services import quiz_ai_generator as generator


def test_episode_context_reaches_generation(monkeypatch):
    seen=[]
    def call(messages):
        seen.extend(messages)
        return json.dumps([{'id':'q','question':'Quelle ville ?', 'choices':[{'id':'A','text':'Paris'},{'id':'B','text':'Lyon'}],'correct_id':'A'}])
    monkeypatch.setattr(generator,'_call_cliproxy_llm',call)
    result=generator.generate_quiz_json_with_ai('France',count=1,format_type='photo_reveal',channel_profile='fr-culture',episode_context={'series':'proverbes','difficulty_curve':'hard','target_minutes':14,'question_index':8,'question_total':30})
    prompt=' '.join(m['content'] for m in seen)
    assert 'proverbes' in prompt and '14' in prompt and 'hard' in prompt
    assert result[0]['difficulty']=='hard'
    assert result[0]['series']=='proverbes'
    assert 'intro_text' not in result[0]
    assert 'outro_text' not in result[0]
