"""Locale text and font policy independent of installed speech models."""
from pathlib import Path
from PIL import ImageFont

LOCALES = {
'en-US': ('US','you','Test your knowledge!','Ready for the next challenge?'),
'en-GB': ('GB','you','Put your knowledge to the test!','Join us for the next round.'),
'vi-VN': ('VN','bạn','Cùng thử tài kiến thức!','Hẹn bạn ở thử thách tiếp theo.'),
'ko-KR': ('KR','해요체','퀴즈로 상식을 테스트해 보세요!','다음 퀴즈에서도 함께해요.'),
'ja-JP': ('JP','です・ます','クイズで知識を試してみましょう！','次のクイズもお楽しみに。'),
'es-ES': ('ES','tú','¡Pon a prueba tus conocimientos!','Nos vemos en el próximo reto.'),
'es-MX': ('MX','tú','¡Pon a prueba lo que sabes!','Te esperamos en el próximo reto.'),
}
TEXT = {
'en': ('QUESTION','ANSWER','CORRECT!','HINT','CHOOSE THE CORRECT ANSWER','YOUR SCORE','How many did you get right?', ['WARMUP','INTERMEDIATE','EXPERT','FINAL']),
'vi': ('CÂU','ĐÁP ÁN','CHÍNH XÁC!','GỢI Ý','CHỌN ĐÁP ÁN ĐÚNG','ĐIỂM CỦA BẠN','Bạn đúng bao nhiêu câu?', ['KHỞI ĐỘNG','TRUNG BÌNH','CHUYÊN GIA','VÒNG CUỐI']),
'ko': ('문제','정답','정답이에요!','힌트','정답을 골라 주세요','나의 점수','몇 문제를 맞혔나요?', ['몸풀기','중급','고급','마지막 도전']),
'ja': ('問題','正解','正解です！','ヒント','正しい答えを選んでください','あなたのスコア','何問正解できましたか？', ['ウォーミングアップ','中級','上級','最終問題']),
'es': ('PREGUNTA','RESPUESTA','¡CORRECTO!','PISTA','ELIGE LA RESPUESTA CORRECTA','TU PUNTUACIÓN','¿Cuántas respuestas acertaste?', ['CALENTAMIENTO','INTERMEDIO','EXPERTO','FINAL']),
}


def locale_labels(locale):
    return dict(zip(('question','answer','correct','hint','choose','score','comment','levels'),TEXT[locale.split('-')[0]]))


def font_factory(locale, fallback):
    filename = {'ja':'YuGothB.ttc','ko':'malgunbd.ttf'}.get(locale.split('-')[0])
    if not filename:
        return fallback
    path = Path('C:/Windows/Fonts') / filename
    if not path.exists():
        raise ValueError(f'Missing {locale} font: {path}; install a suitable font before preview')
    def load(size, bold=True):
        return ImageFont.truetype(str(path),size)
    return load


def wrap_lines(draw, text, font, width):
    # Character fallback handles Japanese and long unspaced tokens without loss.
    lines = []
    for paragraph in str(text).split('\n'):
        line = ''
        for char in paragraph:
            if line and draw.textlength(line+char,font=font)>width:
                # Prefer the latest word boundary for Latin and Korean text.
                split = line.rfind(' ')
                if split > 0:
                    lines.append(line[:split])
                    line = line[split+1:] + char
                else:
                    lines.append(line)
                    line = char
            else:
                line += char
        lines.append(line)
    return lines


QUIZ_UI_STRINGS = {
    'de': {
        'intro_title': "DIE ULTIMATIVE CHALLENGE",
        'intro_sub': "SCHAFFST DU 100% RICHTIG?",
        'intro_cta': "3 SEKUNDEN PRO FRAGE • BEREIT?",
        'intro_cta_916': "3S PRO FRAGE • BEREIT?",
        'outro_title': "DIE FINALE RANGLISTE",
        'outro_title_916': "FINALE RANGLISTE",
        'outro_tiers': [
            ("450+ PKT: QUIZ-LEGENDE", (46, 204, 113), "crown"),
            ("300–449 PKT: QUIZ-PROFI", (52, 152, 219), "star"),
            ("150–299 PKT: QUIZ-KENNER", (241, 196, 15), "star"),
            ("0–149 PKT: ANFÄNGER", (231, 76, 60), "fire"),
        ],
        'outro_tiers_916': [
            ("450+ PKT: QUIZ-LEGENDE", (46, 204, 113), "crown"),
            ("300–449 PKT: QUIZ-PROFI", (52, 152, 219), "star"),
            ("150–299 PKT: QUIZ-KENNER", (241, 196, 15), "star"),
            ("0–149 PKT: ANFÄNGER", (231, 76, 60), "fire"),
        ],
        'outro_cta1': "WIE VIELE PUNKTE HAST DU? JETZT KOMMENTIEREN!",
        'outro_cta2': "LIKEN & ABONNIEREN FÜR DIE NÄCHSTE RUNDE!",
        'outro_cta1_916': "WIE VIELE PUNKTE? JETZT KOMMENTIEREN!",
        'outro_cta2_916': "LIKE & FOLGEN FÜR DIE NÄCHSTE RUNDE!",
        'default_intro_tts': "Willkommen zur großen {archetype}-Challenge! Schaffst du alle {count} Fragen? Los geht's!",
        'default_outro_tts': "Die Zeit ist um! Wie viele Fragen hast du richtig beantwortet? Schreib es in die Kommentare und abonniere den Kanal für die nächste Runde!",
        'default_ans_tts': "Richtig! Die Antwort ist {answer}.",
        'question': "FRAGE",
        'correct': "RICHTIGE ANTWORT",
        'choose_answer': "[ WÄHLE DIE ANTWORT RECHTS ]",
        'choose_player': "[ WÄHLE DEN SPIELER RECHTS ]",
        'choose_correct_answer': "WÄHLE DIE RICHTIGE ANTWORT",
        'answer_prefix': "ANTWORT: ",
        'action_like': "LIKE DRÜCKEN",
        'action_comment': "KOMMENTIEREN",
        'hint': "HINWEIS",
        'unblur': "WER IST DAS? (WIRD SICHTBAR)",
    },
    'en': {
        'intro_title': "THE ULTIMATE CHALLENGE",
        'intro_sub': "CAN YOU SCORE 100%?",
        'intro_cta': "3 SECONDS PER QUESTION • READY?",
        'intro_cta_916': "3S PER QUESTION • READY?",
        'outro_title': "FINAL SCOREBOARD",
        'outro_title_916': "FINAL SCOREBOARD",
        'outro_tiers': [
            ("TOP 1 (450+ PTS): FOOTBALL GOAT", (46, 204, 113), "crown"),
            ("TOP 2 (300–440 PTS): PRO PLAYER", (52, 152, 219), "star"),
            ("TOP 3 (150–290 PTS): CASUAL FAN", (241, 196, 15), "star"),
            ("TOP 4 (0–140 PTS): FAKE FAN", (231, 76, 60), "fire"),
        ],
        'outro_tiers_916': [
            ("TOP 1: FOOTBALL GOAT", (46, 204, 113), "crown"),
            ("TOP 2: PRO PLAYER", (52, 152, 219), "star"),
            ("TOP 3: CASUAL FAN", (241, 196, 15), "star"),
            ("TOP 4: FAKE FAN", (231, 76, 60), "fire"),
        ],
        'outro_cta1': "COMMENT YOUR SCORE BELOW!",
        'outro_cta2': "LIKE & SUBSCRIBE FOR NEXT ROUND!",
        'outro_cta1_916': "COMMENT YOUR SCORE BELOW!",
        'outro_cta2_916': "LIKE & FOLLOW FOR NEXT ROUND!",
        'default_intro_tts': "Welcome to the {archetype} challenge! Can you get all {count} questions right? Let's go!",
        'default_outro_tts': "Time is up! How many questions did you answer correctly? Comment below, and make sure to like and subscribe!",
        'default_ans_tts': "The correct answer is {answer}!",
        'question': "QUESTION",
        'correct': "CORRECT ANSWER",
        'choose_answer': "[ CHOOSE THE ANSWER ON RIGHT ]",
        'choose_player': "[ CHOOSE THE PLAYER ON RIGHT ]",
        'choose_correct_answer': "CHOOSE THE CORRECT ANSWER",
        'answer_prefix': "ANSWER: ",
        'action_like': "HIT LIKE",
        'action_comment': "LEAVE COMMENT",
        'hint': "HINT",
        'unblur': "WHO IS THIS? (REVEALING)",
    },
    'vi': {
        'intro_title': "THỬ THÁCH TRÍ TUỆ",
        'intro_sub': "ĐỐ BẠN TRẢ LỜI ĐÚNG HẾT 100%!",
        'intro_cta': "3 GIÂY MỖI CÂU • BẠN ĐÃ SẴN SÀNG?",
        'intro_cta_916': "3 GIÂY / CÂU • BẮT ĐẦU NGAY!",
        'outro_title': "BẢNG TỔNG KẾT ĐIỂM SỐ",
        'outro_title_916': "BẢNG TỔNG KẾT ĐIỂM",
        'outro_tiers': [
            ("TOP 1 (450+ ĐIỂM): THIÊN TÀI BÓNG ĐÁ", (46, 204, 113), "crown"),
            ("TOP 2 (300–440 ĐIỂM): CAO THỦ XUẤT SẮC", (52, 152, 219), "star"),
            ("TOP 3 (150–290 ĐIỂM): FAN PHONG TRÀO", (241, 196, 15), "star"),
            ("TOP 4 (0–140 ĐIỂM): FAN GIẢ MẠO", (231, 76, 60), "fire"),
        ],
        'outro_tiers_916': [
            ("TOP 1: THIÊN TÀI", (46, 204, 113), "crown"),
            ("TOP 2: XUẤT SẮC", (52, 152, 219), "star"),
            ("TOP 3: PHONG TRÀO", (241, 196, 15), "star"),
            ("TOP 4: GIẢ MẠO", (231, 76, 60), "fire"),
        ],
        'outro_cta1': "BẠN ĐẠT MẤY ĐIỂM? BÌNH LUẬN NGAY!",
        'outro_cta2': "LIKE & ĐĂNG KÝ KÊNH ĐỂ ĐẤU TIẾP VÒNG SAU!",
        'outro_cta1_916': "BẠN ĐẠT MẤY ĐIỂM? BÌNH LUẬN NGAY!",
        'outro_cta2_916': "LIKE & FOLLOW ĐỂ XEM TIẾP!",
        'default_intro_tts': "Chào mừng các bạn đến với thử thách {archetype}! Cùng thử tài với {count} câu hỏi ngay nào!",
        'default_outro_tts': "Thời gian đã hết! Bạn đã trả lời đúng bao nhiêu câu? Hãy like và đăng ký kênh nhé!",
        'default_ans_tts': "Đáp án là {answer} nha!",
        'question': "CÂU",
        'correct': "ĐÁP ÁN ĐÚNG",
        'choose_answer': "[ CHỌN ĐÁP ÁN BÊN PHẢI ]",
        'choose_player': "[ CHỌN CẦU THỦ BÊN PHẢI ]",
        'choose_correct_answer': "CHỌN ĐÁP ÁN ĐÚNG",
        'answer_prefix': "ĐÁP ÁN: ",
        'action_like': "BẤM LIKE",
        'action_comment': "BÌNH LUẬN",
        'hint': "GỢI Ý",
        'unblur': "AI ĐÂY NHỈ? (ĐANG RÕ DẦN)",
    },
    'fr': {
        'intro_title': "LE DÉFI ULTIME",
        'intro_sub': "POUVEZ-VOUS OBTENIR 100% ?",
        'intro_cta': "3 SECONDES PAR QUESTION • PRÊT ?",
        'intro_cta_916': "3S PAR QUESTION • C'EST PARTI !",
        'outro_title': "TABLEAU DES SCORES",
        'outro_title_916': "SCORES FINAUX",
        'outro_tiers': [
            ("TOP 1: 100% — GÉNIE DU QUIZ", (46, 204, 113), "crown"),
            ("TOP 2: 70%+ — MAÎTRE EXPERT", (52, 152, 219), "star"),
            ("TOP 3: MOINS DE 50% — CONTINUEZ L'ENTRAÎNEMENT", (231, 76, 60), "fire"),
        ],
        'outro_tiers_916': [
            ("TOP 1: 100% — GÉNIE", (46, 204, 113), "crown"),
            ("TOP 2: 70%+ — EXPERT", (52, 152, 219), "star"),
            ("TOP 3: MOINS DE 50% — ENTRAÎNEMENT", (231, 76, 60), "fire"),
        ],
        'outro_cta1': "QUEL EST VOTRE SCORE ? COMMENTEZ CI-DESSOUS !",
        'outro_cta2': "AIMEZ & ABONNEZ-VOUS POUR LA SUITE !",
        'outro_cta1_916': "QUEL EST VOTRE SCORE ? COMMENTEZ !",
        'outro_cta2_916': "AIMEZ & SUIVEZ POUR LA SUITE !",
        'default_intro_tts': "Bienvenue au défi {archetype} ! Pouvez-vous répondre correctement aux {count} questions ? C'est parti !",
        'default_outro_tts': "Le temps est écoulé ! Combien de bonnes réponses avez-vous eues ? Écrivez-le en commentaire et abonnez-vous !",
        'default_ans_tts': "Exact ! La bonne réponse est {answer}.",
        'question': "QUESTION",
        'correct': "BONNE RÉPONSE",
        'choose_answer': "[ CHOISISSEZ LA RÉPONSE À DROITE ]",
        'choose_player': "[ CHOISISSEZ LE JOUEUR À DROITE ]",
        'choose_correct_answer': "CHOISISSEZ LA BONNE RÉPONSE",
        'answer_prefix': "RÉPONSE : ",
        'action_like': "CLIQUEZ SUR LIKE",
        'action_comment': "COMMENTEZ",
        'hint': "INDICE",
        'unblur': "QUI EST-CE ? (RÉVÉLATION)",
    },
    'es': {
        'intro_title': "EL DESAFÍO DEFINITIVO",
        'intro_sub': "¿PUEDES ACERTAR EL 100%?",
        'intro_cta': "3 SEGUNDOS POR PREGUNTA • ¿LISTO?",
        'intro_cta_916': "3S POR PREGUNTA • ¡EMPEZAMOS!",
        'outro_title': "TABLA DE PUNTUACIÓN FINAL",
        'outro_title_916': "TABLA FINAL",
        'outro_tiers': [
            ("TOP 1: 100% — GENIO DEL QUIZ", (46, 204, 113), "crown"),
            ("TOP 2: 70%+ — MAESTRO DESTACADO", (52, 152, 219), "star"),
            ("TOP 3: MENOS DE 50% — SIGUE PRACTICANDO", (231, 76, 60), "fire"),
        ],
        'outro_tiers_916': [
            ("TOP 1: 100% — GENIO", (46, 204, 113), "crown"),
            ("TOP 2: 70%+ — MAESTRO", (52, 152, 219), "star"),
            ("TOP 3: MENOS DE 50% — PRACTICAR", (231, 76, 60), "fire"),
        ],
        'outro_cta1': "¿CUÁNTOS PUNTOS SACASTE? ¡COMENTA ABAJO!",
        'outro_cta2': "¡DALE LIKE Y SUSCRÍBETE PARA LA PRÓXIMA RONDA!",
        'outro_cta1_916': "¿CUÁNTOS PUNTOS? ¡COMENTA ABAJO!",
        'outro_cta2_916': "¡DALE LIKE Y SÍGUENOS!",
        'default_intro_tts': "¡Bienvenidos al desafío de {archetype}! ¿Podrás acertar las {count} preguntas? ¡Vamos!",
        'default_outro_tts': "¡Se acabó el tiempo! ¿Cuántas preguntas acertaste? ¡Comenta abajo y no olvides suscribirte!",
        'default_ans_tts': "¡Correcto! La respuesta es {answer}.",
        'question': "PREGUNTA",
        'correct': "RESPUESTA CORRECTA",
        'choose_answer': "[ ELIGE LA RESPUESTA A LA DERECHA ]",
        'choose_player': "[ ELIGE AL JUGADOR A LA DERECHA ]",
        'choose_correct_answer': "ELIGE LA RESPUESTA CORRECTA",
        'answer_prefix': "RESPUESTA: ",
        'action_like': "DALE LIKE",
        'action_comment': "COMENTA",
        'hint': "PISTA",
        'unblur': "¿QUIÉN ES? (REVELANDO)",
    },
    'it': {
        'intro_title': "LA SFIDA DEFINITIVA",
        'intro_sub': "RIESCI A FARE IL 100%?",
        'intro_cta': "3 SECONDI PER DOMANDA • PRONTO?",
        'intro_cta_916': "3S PER DOMANDA • SI COMINCIA!",
        'outro_title': "CLASSIFICA FINALE",
        'outro_title_916': "CLASSIFICA",
        'outro_tiers': [
            ("TOP 1: 100% — GENIO DEL QUIZ", (46, 204, 113), "crown"),
            ("TOP 2: 70%+ — VERO CAMPIONE", (52, 152, 219), "star"),
            ("TOP 3: SOTTO IL 50% — CONTINUA AD ALLENARTI", (231, 76, 60), "fire"),
        ],
        'outro_tiers_916': [
            ("TOP 1: 100% — GENIO", (46, 204, 113), "crown"),
            ("TOP 2: 70%+ — CAMPIONE", (52, 152, 219), "star"),
            ("TOP 3: SOTTO IL 50% — ALLENATI", (231, 76, 60), "fire"),
        ],
        'outro_cta1': "QUANTI PUNTI HAI FATTO? COMMENTA QUI SOTTO!",
        'outro_cta2': "LASCIA UN LIKE E ISCRIVITI PER IL PROSSIMO TURNO!",
        'outro_cta1_916': "QUANTI PUNTI? COMMENTA QUI SOTTO!",
        'outro_cta2_916': "LASCIA UN LIKE E SEGUICI!",
        'default_intro_tts': "Benvenuti alla sfida di {archetype}! Riuscirai a rispondere a tutte le {count} domande? Si parte!",
        'default_outro_tts': "Tempo scaduto! Quante domande hai indovinato? Scrivilo nei commenti e iscriviti al canale!",
        'default_ans_tts': "Esatto! La risposta è {answer}.",
        'question': "DOMANDA",
        'correct': "RISPOSTA CORRETTA",
        'choose_answer': "[ SCEGLI LA RISPOSTA A DESTRA ]",
        'choose_player': "[ SCEGLI IL GIOCATORE A DESTRA ]",
        'choose_correct_answer': "SCEGLI LA RISPOSTA GIUSTA",
        'answer_prefix': "RISPOSTA: ",
        'action_like': "METTI LIKE",
        'action_comment': "COMMENTA",
        'hint': "INDIZIO",
        'unblur': "CHI È QUESTO? (IN ARRIVO)",
    },
    'ja': {
        'intro_title': "究極のクイズチャレンジ",
        'intro_sub': "全問正解できるかな？",
        'intro_cta': "1問3秒 • 準備はいい？",
        'intro_cta_916': "1問3秒 • スタート！",
        'outro_title': "最終スコアボード",
        'outro_title_916': "スコア発表",
        'outro_tiers': [
            ("TOP 1: 全問正解 — クイズ王", (46, 204, 113), "crown"),
            ("TOP 2: 正解率70%+ — 上級マスター", (52, 152, 219), "star"),
            ("TOP 3: 50%未満 — もう一度挑戦！", (231, 76, 60), "fire"),
        ],
        'outro_tiers_916': [
            ("TOP 1: 全問正解 — 天才", (46, 204, 113), "crown"),
            ("TOP 2: 70%+ — マスター", (52, 152, 219), "star"),
            ("TOP 3: 50%未満 — 練習中", (231, 76, 60), "fire"),
        ],
        'outro_cta1': "何問正解できた？コメントで教えてね！",
        'outro_cta2': "高評価＆チャンネル登録をお願いします！",
        'outro_cta1_916': "何問正解？コメントしてね！",
        'outro_cta2_916': "いいね＆フォローしてね！",
        'default_intro_tts': "クイズチャレンジへようこそ！全{count}問、正解できるかな？スタート！",
        'default_outro_tts': "タイムアップ！何問正解できましたか？コメント欄で教えてね。チャンネル登録もお忘れなく！",
        'default_ans_tts': "正解！答えは{answer}です！",
        'question': "問題",
        'correct': "正解",
        'choose_answer': "[ 右から答えを選んでね ]",
        'choose_player': "[ 右から選手を選んでね ]",
        'choose_correct_answer': "正しい答えを選んでね",
        'answer_prefix': "正解: ",
        'action_like': "いいね！",
        'action_comment': "コメント",
        'hint': "ヒント",
        'unblur': "誰かな？（拡大中）",
    },
    'ko': {
        'intro_title': "궁극의 퀴즈 챌린지",
        'intro_sub': "100% 정답에 도전해 보세요!",
        'intro_cta': "문제당 3초 • 준비되셨나요?",
        'intro_cta_916': "문제당 3초 • 시작!",
        'outro_title': "최종 점수판",
        'outro_title_916': "점수 확인",
        'outro_tiers': [
            ("TOP 1: 100% 정답 — 퀴즈 천재", (46, 204, 113), "crown"),
            ("TOP 2: 70%+ — 상식 마스터", (52, 152, 219), "star"),
            ("TOP 3: 50% 미만 — 다음 기회에!", (231, 76, 60), "fire"),
        ],
        'outro_tiers_916': [
            ("TOP 1: 만점 — 천재", (46, 204, 113), "crown"),
            ("TOP 2: 70%+ — 마스터", (52, 152, 219), "star"),
            ("TOP 3: 50% 미만 — 도전", (231, 76, 60), "fire"),
        ],
        'outro_cta1': "몇 점 맞히셨나요? 댓글로 남겨주세요!",
        'outro_cta2': "좋아요 & 구독 누르고 다음 라운드로!",
        'outro_cta1_916': "몇 점 맞히셨나요? 댓글 고고!",
        'outro_cta2_916': "좋아요 & 팔로우 부탁드려요!",
        'default_intro_tts': "퀴즈 챌린지에 오신 것을 환영합니다! 총 {count}문제, 모두 맞힐 수 있을까요? 출발!",
        'default_outro_tts': "시간 종료! 몇 문제나 맞히셨나요? 댓글로 점수를 공유하고 구독도 잊지 마세요!",
        'default_ans_tts': "정답입니다! 정답은 {answer}입니다.",
        'question': "문제",
        'correct': "정답",
        'choose_answer': "[ 오른쪽에서 정답을 골라주세요 ]",
        'choose_player': "[ 오른쪽에서 선수를 골라주세요 ]",
        'choose_correct_answer': "정답을 골라주세요",
        'answer_prefix': "정답: ",
        'action_like': "좋아요",
        'action_comment': "댓글 남기기",
        'hint': "힌트",
        'unblur': "누구일까요? (공개 중)",
    },
}


def get_quiz_ui_strings(lang: str) -> dict:
    code = (str(lang or "").lower().split("-")[0].split("_")[0]).strip()
    return QUIZ_UI_STRINGS.get(code, QUIZ_UI_STRINGS["en"])
