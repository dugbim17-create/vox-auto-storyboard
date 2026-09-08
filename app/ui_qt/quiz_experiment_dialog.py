"""Explicit user-entered observations; no YouTube credentials or network."""
import json
from pathlib import Path
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QLineEdit,QComboBox,QPushButton,QTextEdit,QFileDialog,QMessageBox
from app.services.quiz_episode_editor import record_observation
from app.services.quiz_channel_analytics import summarize


class QuizExperimentDialog(QDialog):
    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.document=document
        self.setWindowTitle('Theo dõi tập · số liệu nhập từ YouTube Studio')
        self.resize(650,650)
        layout=QVBoxLayout(self)
        form=QFormLayout()
        self.fields={}
        for key,label in [('video_id','YouTube video ID'),('period','Mốc đo, ví dụ 7d'),('views','Views'),('subscribers_gained','Subscriber tăng'),('watch_hours','Giờ xem'),('ctr','CTR %'),('avg_percentage_viewed','Tỷ lệ xem %')]:
            field=QLineEdit()
            self.fields[key]=field
            form.addRow(label,field)
        self.fields['period'].setText('7d')
        self.format=QComboBox()
        self.format.addItems(['longform','shorts'])
        form.addRow('Loại video',self.format)
        layout.addLayout(form)
        button=QPushButton('Ghi vào sổ JSON · chọn file')
        button.clicked.connect(self.choose_save)
        layout.addWidget(button)
        self.report=QTextEdit()
        self.report.setReadOnly(True)
        layout.addWidget(self.report)

    def save_to(self,path):
        row={key:field.text().strip() for key,field in self.fields.items()}
        for key in ('views','subscribers_gained','watch_hours','ctr','avg_percentage_viewed'):
            row[key]=float(row[key]) if row[key] else None
        row.update(channel_profile=self.document.get('channel_profile',''),
                   series=self.document.get('series',''),format=self.format.currentText(),
                   episode_revision=self.document.get('episode_revision',0))
        record_observation(path,row)
        rows=json.loads(Path(path).read_text(encoding='utf-8'))
        selected=[r for r in rows if r['channel_profile']==row['channel_profile'] and r['period']==row['period']]
        self.report.setPlainText(json.dumps(summarize(selected),ensure_ascii=False,indent=2))
        return rows

    def choose_save(self):
        path,_=QFileDialog.getSaveFileName(self,'Chọn sổ mới hoặc sổ hiện có (ghi nối, không xóa dữ liệu)','', 'JSON (*.json)')
        if not path:
            return
        try:
            self.save_to(path)
        except (ValueError,OSError) as exc:
            QMessageBox.warning(self,'Không ghi số liệu',str(exc))
