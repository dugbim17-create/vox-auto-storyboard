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
