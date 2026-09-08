"""
Quiz JSON Dialog: Allows users to paste custom JSON question sets with mode directives,
OR ask local AI (Gemini 3.6 Flash / GPT via CLIProxy) to generate valid JSON automatically!
"""

from __future__ import annotations

import json
import hashlib
from typing import Any
import threading
from PySide6.QtCore import Qt, QObject, Signal, Slot
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QMessageBox,
    QProgressBar,
)

from app.services.quiz_ai_generator import generate_quiz_json_with_ai


SAMPLE_4CARDS_JSON = '''[
  {
    "id": "q1",
    "question": "WHO IS PREGNANT?",
    "cards": [
      {"id": "1", "label": "DRINKING WINE", "image_path": "assets/quizmystra_4cards/p1_wine.jpg"},
      {"id": "2", "label": "ESPRESSO SHOTS", "image_path": "assets/quizmystra_4cards/p2_coffee.jpg"},
      {"id": "3", "label": "PICKLES & ICE CREAM", "image_path": "assets/quizmystra_4cards/p3_cravings.jpg"},
      {"id": "4", "label": "RAW SUSHIS", "image_path": "assets/quizmystra_4cards/p4_sushi.jpg"}
    ],
    "correct_option": "3",
    "explanation_text": "ANSWER: PERSON #3! SHE HAS STRANGE PREGNANCY CRAVINGS (PICKLES & SWEETS)!",
    "voice_q": "Look closely at these four women. Only one of them is pregnant! Can you spot who it is?",
    "voice_a": "Number 3 is pregnant! Pickles and ice cream is a classic pregnancy craving!",
    "countdown_seconds": 8.0
  },
  {
    "id": "q2",
    "question": "WHO IS THE DANGEROUS KILLER?",
    "cards": [
      {"id": "1", "label": "CHEF IN APRON", "image_path": "assets/quizmystra_4cards/killer_a_chef.jpg"},
      {"id": "2", "label": "DOCTOR IN SCRUBS", "image_path": "assets/quizmystra_4cards/killer_b_doctor.jpg"},
      {"id": "3", "label": "NERVOUS SUSPECT", "image_path": "assets/quizmystra_4cards/killer_c_suspect.jpg"},
      {"id": "4", "label": "OFFICE ASSISTANT", "image_path": "assets/quizmystra_4cards/killer_d_gardener.jpg"}
    ],
    "correct_option": "3",
    "explanation_text": "ANSWER: SUSPECT #3! HE GIVES A GUILTY LOOK AND HAS NO WORKING ALIBI!",
    "voice_q": "A crime occurred in the building! One of these four suspects is the killer! Who is it?",
    "voice_a": "Number 3 is the killer! Notice his intense guilty stare and nervous expression!",
    "countdown_seconds": 8.0
  }
]'''

SAMPLE_RIDDLE_JSON = '''[
  {
    "id": "riddle_01",
    "question": "WHO IS THE SLEEPWALKER?",
    "scene_image": "assets/riddles/riddle_01_study.jpg",
    "options": ["1", "2", "3", "4"],
    "option_coords": [[280, 240], [720, 240], [1200, 240], [1650, 240]],
    "correct_option": "3",
    "clue_highlight": {
      "coord": [1200, 840],
      "radius": 80,
      "arrow_from": [1200, 720]
    },
    "explanation_text": "ANSWER: PERSON 3! HE PUT ON TWO DIFFERENT SLIPPERS IN HIS SLEEP!",
    "voice_q": "Look closely at these four rooms late at night. One person is sleepwalking! Who is it?",
    "voice_a": "The sleepwalker is number 3! Look at his feet: he put on two different slippers in his sleep!",
    "countdown_seconds": 8.0
  }
]'''

SAMPLE_MULTICHOICE_JSON = '''[
  {
    "id": "q1",
    "question": "WHAT IS THE CAPITAL OF FRANCE?",
    "universe": "CAPITAL CITY",
    "choices": [
      {"id": "A", "text": "Lyon"},
      {"id": "B", "text": "Marseille"},
      {"id": "C", "text": "Paris"},
      {"id": "D", "text": "Nice"}
    ],
    "correct_id": "C",
    "answer_text": "PARIS",
    "reveal_image_path": "assets/landmarks/paris.jpg",
    "voice_q": "What is the official capital city of France?",
    "voice_a": "Of course, it's Paris, the City of Light!",
    "countdown_seconds": 4.0
  }
]'''


class _AiWorkerSignals(QObject):
    finished = Signal(list)
    failed = Signal(str)


class JsonHighlighter(QSyntaxHighlighter):
    """Clean JSON syntax highlighter for dark mode editor."""

    def __init__(self, parent=None):
        import re
        super().__init__(parent)
        self.rules = []

        # Keys (e.g. "question":, "cards":)
        key_fmt = QTextCharFormat()
        key_fmt.setForeground(QColor("#63B3ED"))  # Cyan / sky blue
        key_fmt.setFontWeight(QFont.Weight.Bold)
        self.rules.append((re.compile(r'("[^"\\]*(\\.[^"\\]*)*")\s*:'), key_fmt, 1))

        # String values (e.g. "WHO IS PREGNANT?")
        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#9AE6B4"))  # Soft mint green
        self.rules.append((re.compile(r':\s*("[^"\\]*(\\.[^"\\]*)*")'), str_fmt, 1))
        self.rules.append((re.compile(r'\[\s*("[^"\\]*(\\.[^"\\]*)*")'), str_fmt, 1))
        self.rules.append((re.compile(r',\s*("[^"\\]*(\\.[^"\\]*)*")'), str_fmt, 1))

        # Numbers
        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#F6AD55"))  # Amber / orange
        self.rules.append((re.compile(r'\b-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?\b'), num_fmt, 0))

        # Booleans and null
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#F687B3"))  # Coral pink
        kw_fmt.setFontWeight(QFont.Weight.Bold)
        self.rules.append((re.compile(r'\b(true|false|null)\b'), kw_fmt, 0))

    def highlightBlock(self, text: str) -> None:
        for item in self.rules:
            pattern, fmt, group = item[0], item[1], item[2]
            for match in pattern.finditer(text):
                start, end = match.span(group)
                self.setFormat(start, end - start, fmt)


class QuizJsonDialog(QDialog):
    """Dialog for pasting and validating custom quiz JSON, with built-in AI Generator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 Dán hoặc Nhờ AI Viết JSON Quiz (Tự động nhận diện Mode)")
        self.resize(920, 680)
        self.parsed_document: dict[str, Any] | None = None
        self._signals = _AiWorkerSignals()
        self._signals.finished.connect(self._on_ai_success)
        self._signals.failed.connect(self._on_ai_failure)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # 1. AI Assistant Generation Box (Top section)
        ai_box = QVBoxLayout()
        ai_header = QLabel("✦ AI Trợ lý: Yêu cầu AI viết bộ câu hỏi JSON theo ý bạn")
        ai_header.setStyleSheet("font-size: 14px; font-weight: 700; color: #9F7AEA;")
        ai_box.addWidget(ai_header)

        ai_row = QHBoxLayout()
        self.ai_prompt_input = QLineEdit()
        self.ai_prompt_input.setPlaceholderText("Nhập yêu cầu: ví dụ '5 câu đố phá án ai là triệu phú ngầm', 'câu đố mẹo logic'...")
        self.ai_prompt_input.setText("5 câu đố QuizMystra: Ai là triệu phú ngầm / Ai đang nói dối")
        self.ai_prompt_input.setStyleSheet(
            "background-color: #1A202C; color: #E2E8F0; border: 1px solid #4A5568; "
            "border-radius: 6px; padding: 6px 10px; font-size: 13px;"
        )

        self.ai_format_combo = QComboBox()
        self.ai_format_combo.addItems([
            "QuizMystra 4-Cards (So sánh 4 ảnh)",
            "QuizMystra Visual Riddle (Phá án toàn cảnh)",
            "Trắc nghiệm danh lam (Photo Reveal)",
        ])
        self.ai_format_combo.setStyleSheet(
            "background-color: #1A202C; color: #E2E8F0; border: 1px solid #4A5568; "
            "border-radius: 6px; padding: 5px 10px; font-size: 12px;"
        )

        self.ai_count_spin = QSpinBox()
        self.ai_count_spin.setRange(1, 30)
        self.ai_count_spin.setValue(3)
        self.ai_count_spin.setSuffix(" câu")
        self.ai_count_spin.setStyleSheet(
            "background-color: #1A202C; color: #E2E8F0; border: 1px solid #4A5568; "
            "border-radius: 6px; padding: 5px 8px; font-size: 12px;"
        )

        self.ai_generate_btn = QPushButton("✦ AI Viết JSON")
        self.ai_generate_btn.setStyleSheet("background-color: #6B46C1; color: white; font-weight: bold; padding: 6px 14px; border-radius: 6px;")
        self.ai_generate_btn.clicked.connect(self._on_ai_generate_clicked)

        ai_row.addWidget(self.ai_prompt_input, 3)
        ai_row.addWidget(self.ai_format_combo, 2)
        ai_row.addWidget(self.ai_count_spin, 1)
        ai_row.addWidget(self.ai_generate_btn)
        ai_box.addLayout(ai_row)
        context_row = QHBoxLayout()
        self.series_input = QLineEdit()
        self.series_input.setPlaceholderText('Series / chuyên mục')
        self.difficulty_input = QComboBox()
        self.difficulty_input.addItems(['progressive','easy','medium','hard'])
        self.minutes_input = QSpinBox()
        self.minutes_input.setRange(1,60)
        self.minutes_input.setValue(12)
        self.minutes_input.setSuffix(' phút mục tiêu')
        context_row.addWidget(self.series_input)
        context_row.addWidget(self.difficulty_input)
        context_row.addWidget(self.minutes_input)
        ai_box.addLayout(context_row)

        self.ai_progress = QProgressBar()
        self.ai_progress.setRange(0, 100)
        self.ai_progress.setValue(0)
        self.ai_progress.setFixedHeight(4)
        self.ai_progress.setTextVisible(False)
        self.ai_progress.setVisible(False)
        ai_box.addWidget(self.ai_progress)

        layout.addLayout(ai_box)

        # Divider
        div = QLabel("─" * 60)
        div.setStyleSheet("color: #4A5568;")
        layout.addWidget(div)

        # 2. Template Buttons Row
        btn_row = QHBoxLayout()
        lbl_temp = QLabel("Hoặc chọn mẫu nhanh:")
        lbl_temp.setStyleSheet("color: #CBD5E0; font-weight: 600;")
        btn_row.addWidget(lbl_temp)

        pill_style = (
            "background-color: #2D3748; color: #EDF2F7; border: 1px solid #4A5568; "
            "border-radius: 6px; padding: 6px 12px; font-weight: 500; font-size: 12px;"
        )

        btn_4cards = QPushButton("⚡ Mẫu 4-Cards (QuizMystra)")
        btn_4cards.setStyleSheet(pill_style)
        btn_4cards.clicked.connect(lambda: self.json_edit.setPlainText(SAMPLE_4CARDS_JSON))
        btn_row.addWidget(btn_4cards)

        btn_riddle = QPushButton("🕵️ Mẫu Visual Riddle (Phá án)")
        btn_riddle.setStyleSheet(pill_style)
        btn_riddle.clicked.connect(lambda: self.json_edit.setPlainText(SAMPLE_RIDDLE_JSON))
        btn_row.addWidget(btn_riddle)

        btn_mc = QPushButton("🎯 Mẫu Trắc nghiệm (Photo Reveal)")
        btn_mc.setStyleSheet(pill_style)
        btn_mc.clicked.connect(lambda: self.json_edit.setPlainText(SAMPLE_MULTICHOICE_JSON))
        btn_row.addWidget(btn_mc)

        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # 3. JSON Text Editor
        self.json_edit = QTextEdit()
        self.json_edit.setPlaceholderText("Nội dung JSON câu hỏi hiển thị tại đây. Bạn có thể tự do sửa đổi trước khi nạp...")
        self.json_edit.setFontFamily("Consolas, Courier New, monospace")
        self.json_edit.setStyleSheet(
            "background-color: #1A202C; color: #E2E8F0; border: 1px solid #4A5568; "
            "border-radius: 8px; padding: 10px; font-size: 13px;"
        )
        self.highlighter = JsonHighlighter(self.json_edit.document())
        self.json_edit.setPlainText(SAMPLE_4CARDS_JSON)
        layout.addWidget(self.json_edit, 1)

        # 4. Bottom Action buttons
        bottom_row = QHBoxLayout()
        self.cancel_btn = QPushButton("Hủy bỏ")
        self.cancel_btn.clicked.connect(self.reject)

        self.import_btn = QPushButton("⚡ Nạp vào Quiz Studio (Bản nháp)")
        self.import_btn.setStyleSheet(
            "background-color: #805AD5; color: white; font-weight: bold; padding: 9px 20px; border-radius: 6px;"
        )
        self.import_btn.clicked.connect(self._on_import_clicked)

        bottom_row.addStretch(1)
        bottom_row.addWidget(self.cancel_btn)
        bottom_row.addWidget(self.import_btn)
        layout.addLayout(bottom_row)

    def read_episode_context(self):
        if getattr(self, 'episode_context', None) is not None:
            return dict(self.episode_context)
        return {'series': self.series_input.text().strip(),
                'topic': self.ai_prompt_input.text().strip(),
                'difficulty_curve': self.difficulty_input.currentText(),
                'target_minutes': self.minutes_input.value()}

    def _on_ai_generate_clicked(self):
        prompt = self.ai_prompt_input.text().strip()
        if not prompt:
            QMessageBox.warning(self, "Thiếu chủ đề", "Vui lòng nhập chủ đề bạn muốn AI tạo câu hỏi!")
            return

        fmt_idx = self.ai_format_combo.currentIndex()
        fmt_type = "4cards" if fmt_idx == 0 else ("riddle" if fmt_idx == 1 else "photo_reveal")
        count = self.ai_count_spin.value()
        context = self.read_episode_context()
        profile_key = getattr(self, 'channel_profile', '')

        self.ai_generate_btn.setEnabled(False)
        self.ai_generate_btn.setText("Đang suy luận...")
        self.ai_progress.setVisible(True)
        self.ai_progress.setRange(0, 0)

        def _worker():
            try:
                res = generate_quiz_json_with_ai(prompt, count=count, format_type=fmt_type,
                    channel_profile=profile_key,
                    episode_context=context)
                self._signals.finished.emit(res)
            except Exception as e:
                self._signals.failed.emit(str(e))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _on_ai_success(self, questions: list):
        self.ai_generate_btn.setEnabled(True)
        self.ai_generate_btn.setText("✦ AI Viết JSON")
        self.ai_progress.setVisible(False)
        formatted_json = json.dumps(questions, indent=2, ensure_ascii=False)
        self.json_edit.setPlainText(formatted_json)
        QMessageBox.information(
            self,
            "AI Viết Xong!",
            f"Đã tạo thành công {len(questions)} câu hỏi theo yêu cầu! Bạn có thể xem trước hoặc sửa đổi bên dưới trước khi bấm Nạp.",
        )

    def _on_ai_failure(self, err_msg: str):
        self.ai_generate_btn.setEnabled(True)
        self.ai_generate_btn.setText("✦ AI Viết JSON")
        self.ai_progress.setVisible(False)
        QMessageBox.critical(self, "Lỗi gọi AI", f"Không thể tạo câu hỏi qua AI:\n{err_msg}\n\nHãy đảm bảo CLIProxy đang hoạt động.")

    def _on_import_clicked(self):
        raw_text = self.json_edit.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "Thiếu dữ liệu", "Vui lòng dán hoặc tạo nội dung JSON vào ô nhập liệu!")
            return

        try:
            parsed = json.loads(raw_text)
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi cú pháp JSON", f"Nội dung JSON không hợp lệ:\n{exc}")
            return

        questions = []
        if isinstance(parsed, list):
            questions = parsed
        elif isinstance(parsed, dict):
            if "questions" in parsed and isinstance(parsed["questions"], list):
                questions = parsed["questions"]
            elif "quiz" in parsed and isinstance(parsed["quiz"], list):
                questions = parsed["quiz"]
            else:
                questions = [parsed]

        if not questions:
            QMessageBox.warning(self, "Không tìm thấy câu hỏi", "JSON không chứa danh sách câu hỏi hợp lệ.")
            return

        try:
            from app.services.quiz_v2_contract import validate_questions
            validate_questions(questions, require_assets=False)
            fingerprint = hashlib.sha256(
                json.dumps(questions, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
            ).hexdigest()
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            QMessageBox.critical(self, "Dữ liệu Quiz không hợp lệ", str(exc))
            return

        self.parsed_document = {
            "schema_version": "quiz_v2_dynamic",
            "engine_v2": True,
            "title": (parsed.get("title") if isinstance(parsed, dict) else None) or "Custom Imported Quiz",
            "language": (parsed.get("language") if isinstance(parsed, dict) else None) or "auto",
            "archetype": "riddle_mystra" if any("cards" in q or "scene_image" in q for q in questions) else "classic",
            "input_mode": "preserve_script",
            "questions": questions,
            "approval": {"status": "draft", "content_fingerprint": fingerprint},
        }
        if getattr(self, "channel_profile", ""):
            from app.services.quiz_channel_profiles import bind_profile
            self.parsed_document = bind_profile(self.parsed_document, self.channel_profile)
        context = self.read_episode_context()
        for key in ('series','topic','difficulty_curve','target_minutes'):
            self.parsed_document[key] = context.get(key)
        self.accept()
