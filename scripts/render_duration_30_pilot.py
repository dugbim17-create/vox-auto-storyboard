"""Local 30-question natural-duration render; no external generation."""
import ast
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.quiz_engine_v2 import QuizRenderOptions, QuizVideoEngineV2

source = ROOT / 'produce_us_flag_quiz_5min.py'
tree = ast.parse(source.read_text(encoding='utf-8'))
questions = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'US_FLAG_QUIZ_30' for t in n.targets))
assert len(questions) == 30
for q in questions:
    for clue in q.get('clues', []):
        assert (ROOT / clue['image_path']).is_file()
out = ROOT / 'output' / ('duration-30-pilot-' + str(time.time_ns()))
out.mkdir(parents=True)
shutil.copytree(ROOT / 'output/duration-30-pilot-1788964517571476300/audio_cache', out / 'audio_cache')
print('OUTPUT', out, flush=True)
(out / 'input.json').write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding='utf-8')
model = ROOT / 'assets/models/piper/en-US'
options = QuizRenderOptions(output_path=out / '30-questions-natural.mp4', target_duration_minutes=None, tts_engine='piper', language='en', piper_voice='en_US-ryan-high', piper_model_dir=model, piper_config_path=model / 'en_US-ryan-high.onnx.json', piper_exe=Path(shutil.which('piper')), piper_speed=1.05, fps=30)
engine = QuizVideoEngineV2(options)
actual = engine.render_quiz_video(questions, title='World Flag Challenge')
subprocess.run(['ffmpeg', '-v', 'error', '-i', str(actual), '-f', 'null', '-'], check=True)
probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(actual)]))
assert {'video', 'audio'} <= {s['codec_type'] for s in probe['streams']}
assert float(probe['format']['duration']) > 0
(out / 'verification.json').write_text(json.dumps({'source': str(source), 'question_count': len(questions), 'requested_seconds': None, 'piper_speed': 1.05, 'tts_calls': engine.tts_calls, 'probe': probe, 'decode_pass': True, 'provenance': 'Existing local question bank and flags; reused local Piper audio; no external AI generation'}, indent=2), encoding='utf-8')
print('VERIFIED', actual, probe['format']['duration'], flush=True)
