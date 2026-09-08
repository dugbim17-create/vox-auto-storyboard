"""Form editor for existing V2 documents; changes only applied on Save."""
from copy import deepcopy
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QLineEdit,QComboBox,QTextEdit,QPushButton,QMessageBox
from app.services.quiz_episode_editor import update_question,validate_episode
from app.services.quiz_v2_contract import validate_questions


class QuizEpisodeDialog(QDialog):
    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.document=deepcopy(document)
        self.setWindowTitle('Biên tập tập · không gọi AI/TTS')
        self.resize(850,850)
        layout=QVBoxLayout(self)
        form=QFormLayout()
        self.title=QLineEdit(document.get('title',''))
        self.series=QLineEdit(document.get('series',''))
        self.thumbnail=QLineEdit(document.get('thumbnail_text',''))
        self.topic=QLineEdit(document.get('topic',''))
        self.difficulty=QComboBox()
        self.difficulty.addItems(['progressive','easy','medium','hard'])
        self.difficulty.setCurrentText(document.get('difficulty_curve','progressive'))
        self.duration=QLineEdit(str(document.get('target_minutes',12)))
        form.addRow('Tiêu đề',self.title)
        form.addRow('Series',self.series)
        form.addRow('Chữ thumbnail',self.thumbnail)
        form.addRow('Chủ đề',self.topic)
        form.addRow('Độ khó',self.difficulty)
        form.addRow('Phút mục tiêu (không kéo dài im lặng)',self.duration)
        self.selector=QComboBox()
        for q in document['questions']:
            self.selector.addItem(str(q['id']),str(q['id']))
        form.addRow('Câu đang sửa',self.selector)
        self.fields={}
        for key,label in [('question','Câu hỏi'),('voice_q','Lời đọc câu hỏi'),('voice_a','Lời đọc đáp án / fact'),('explanation_text','Lời giải'),('source_url','Nguồn'),('intro_text','Hook (câu đầu)'),('outro_text','CTA (câu cuối)')]:
            field=QLineEdit()
            self.fields[key]=field
            form.addRow(label,field)
        self.options={}
        for key in 'ABCD':
            field=QLineEdit()
            self.options[key]=field
            form.addRow(key,field)
        self.correct=QLineEdit()
        form.addRow('ID đáp án đúng',self.correct)
        layout.addLayout(form)
        self.notice=QTextEdit()
        self.notice.setReadOnly(True)
        layout.addWidget(self.notice)
        apply=QPushButton('Áp dụng câu đang sửa')
        apply.clicked.connect(self.apply_question)
        layout.addWidget(apply)
        regenerate=QPushButton('Sinh lại riêng câu · mở AI để xác nhận')
        regenerate.clicked.connect(self.regenerate_question)
        layout.addWidget(regenerate)
        save=QPushButton('Lưu thay đổi vào bản nháp')
        save.clicked.connect(self.save)
        layout.addWidget(save)
        tracking=QPushButton('Theo dõi tập · nhập số liệu thực')
        tracking.clicked.connect(self.open_tracking)
        layout.addWidget(tracking)
        self.selector.currentIndexChanged.connect(self.change_question)
        self.load_question()

    def change_question(self, index):
        previous = self._loaded_qid
        if not self.apply_question():
            self.selector.blockSignals(True)
            self.selector.setCurrentIndex(self.selector.findData(previous))
            self.selector.blockSignals(False)
            return
        self.load_question()

    def open_tracking(self):
        from app.ui_qt.quiz_experiment_dialog import QuizExperimentDialog
        snapshot=deepcopy(self.document)
        snapshot['series']=self.series.text()
        QuizExperimentDialog(snapshot,self).exec()

    def load_question(self,*args):
        q=next(q for q in self.document['questions'] if q['id']==self.selector.currentData())
        self._loaded_qid = q['id']
        for key,field in self.fields.items():
            field.setText(str(q.get(key,'')))
        choices={str(c['id']):str(c['text']) for c in q.get('choices',[])}
        for key,field in self.options.items():
            field.setText(choices.get(key,''))
            field.setEnabled('choices' in q)
        self.correct.setText(str(q.get('correct_id') or q.get('correct_option','')))

    def apply_question(self):
        qid=self._loaded_qid
        q=next(q for q in self.document['questions'] if q['id']==qid)
        changes={key:field.text() for key,field in self.fields.items()}
        if 'choices' in q:
            changes['choices']=[{'id':key,'text':field.text()} for key,field in self.options.items() if field.text().strip()]
            changes['correct_id']=self.correct.text().strip()
        else:
            changes['correct_option']=self.correct.text().strip()
        changes = {key:value for key,value in changes.items() if value != q.get(key, '')}
        if not changes:
            return True
        candidate=update_question(self.document,qid,changes)
        try:
            validate_questions(candidate['questions'],require_assets=False)
            validate_episode(candidate)
        except ValueError as exc:
            QMessageBox.warning(self,'Nội dung chưa hợp lệ',str(exc))
            return False
        self.document=candidate
        from app.services.quiz_channel_profiles import review_content
        self.notice.setPlainText(str(review_content(candidate)))
        return True

    def save(self):
        try:
            duration=float(self.duration.text())
            if not 1 <= duration <= 60:
                raise ValueError()
        except ValueError:
            QMessageBox.warning(self,'Thời lượng','Nhập số phút từ 1 đến 60.')
            return
        if not self.apply_question():
            return
        self.document.update(title=self.title.text(),series=self.series.text(),thumbnail_text=self.thumbnail.text(),
                             topic=self.topic.text(),difficulty_curve=self.difficulty.currentText(),target_minutes=duration)
        self.accept()

    def regenerate_question(self):
        if not self.apply_question():
            return
        from app.ui_qt.quiz_json_dialog import QuizJsonDialog
        qid=self.selector.currentData()
        old=next(q for q in self.document['questions'] if q['id']==qid)
        dialog=QuizJsonDialog(self)
        dialog.channel_profile=self.document.get('channel_profile','')
        try:
            duration=float(self.duration.text())
            if not 1 <= duration <= 60:
                raise ValueError()
        except ValueError:
            QMessageBox.warning(self,'Thời lượng','Nhập số phút từ 1 đến 60.')
            return
        dialog.episode_context={
            'series':self.series.text(), 'topic':self.topic.text(),
            'difficulty_curve':self.difficulty.currentText(), 'target_minutes':duration,
            'question_index':self.selector.currentIndex()+1,
            'question_total':len(self.document['questions']),
            'other_questions':[q['question'] for q in self.document['questions'] if q['id']!=qid]}
        dialog.ai_count_spin.setValue(1)
        dialog.ai_format_combo.setCurrentIndex(2 if 'choices' in old else 0 if 'cards' in old else 1)
        dialog.ai_prompt_input.setText('Create one alternative question for this topic: '+old['question'])
        dialog.json_edit.clear()
        if not dialog.exec() or not dialog.parsed_document:
            return
        questions=dialog.parsed_document['questions']
        if len(questions)!=1:
            QMessageBox.warning(self,'Chỉ một câu','Hãy tạo đúng một câu thay thế.')
            return
        candidate=deepcopy(self.document)
        replacement=deepcopy(questions[0])
        replacement['id']=qid
        candidate['questions']=[replacement if q['id']==qid else q for q in candidate['questions']]
        try:
            validate_questions(candidate['questions'],require_assets=False)
            validate_episode(candidate)
        except ValueError as exc:
            QMessageBox.warning(self,'Câu thay thế chưa hợp lệ',str(exc))
            return
        candidate['episode_revision']=candidate.get('episode_revision',0)+1
        candidate['approval']={'status':'draft'}
        self.document=candidate
        self.load_question()
