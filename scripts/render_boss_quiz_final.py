"""Render a fresh finished candidate from preserved real CLIProxy canary data."""
import sys,json,time,shutil,subprocess,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.services.quiz_engine_v2 import QuizVideoEngineV2,QuizRenderOptions
from app.services.quiz_voice_registry import resolve_voice_assets
run=ROOT/'output/quiz-live-acceptance/20260909T111519Z-country-mode'
source=run/'canary/de-football-photo-reveal'
doc=json.loads((source/'document.json').read_text(encoding='utf-8'))
out=run/('BOSS-FINAL-'+str(time.time_ns())); out.mkdir()
shutil.copytree(source/'audio_cache',out/'audio_cache')
voice=resolve_voice_assets(ROOT/'assets/models/piper',locale='de-DE',voice_id=None,strict=True)
manifest={'source':str(source/'canary-manifest.json'),'provenance':'Reuses real CLIProxy LLM + generated image and real Piper voice from source; no new provider requests','outputs':[]}
for aspect in ['16:9','9:16']:
 target=out/('Quiz-Bundesliga-'+aspect.replace(':','x')+'.mp4')
 options=QuizRenderOptions(aspect_ratio=aspect,fps=30,language='de-DE',channel_profile='de-football',visual_style=deepcopy(doc['visual_style']),output_path=target,tts_engine='piper',piper_voice=voice['voice_id'],piper_model_dir=Path(voice['model_path']).parent,piper_config_path=Path(voice['config_path']),piper_exe=Path('D:/ALL AI/Hermes-argent-runtime/hermes-agent/venv/Scripts/piper.exe'),piper_speed=1.08)
 engine=QuizVideoEngineV2(options)
 actual=engine.render_quiz_video(deepcopy(doc['questions']),title='Bundesliga · Die erste Meisterschaft')
 subprocess.run(['ffmpeg','-v','error','-i',str(actual),'-f','null','-'],check=True,timeout=180)
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(actual)]))
 assert {s['codec_type'] for s in probe['streams']} >= {'audio','video'}
 manifest['outputs'].append({'path':str(actual),'aspect':aspect,'sha256':hashlib.sha256(actual.read_bytes()).hexdigest(),'duration':probe['format']['duration'],'tts_calls':engine.tts_calls})
 subprocess.run(['ffmpeg','-v','error','-ss','18','-i',str(actual),'-frames:v','1','-y',str(out/('reveal-'+aspect.replace(':','x')+'.png'))],check=True)
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'XEM-VIDEO.html').write_text('<meta charset=utf-8><title>Quiz Bundesliga — video nghiệm thu</title><style>body{background:#111827;color:white;font:18px Segoe UI;margin:30px}video{max-width:100%;max-height:75vh}a{color:#ffd95a}</style><h1>Bundesliga — Quiz thành phẩm ứng viên</h1><p>Nội dung và ảnh từ CLIProxy thật; giọng Piper Đức. Ảnh AI là minh họa, không phải tư liệu lịch sử. Chưa Boss duyệt.</p>'+''.join('<h2>'+x['aspect']+'</h2><video controls preload=metadata src="'+Path(x['path']).name+'"></video>' for x in manifest['outputs']),encoding='utf-8')
print('FINAL_ARTIFACT',out,flush=True)
