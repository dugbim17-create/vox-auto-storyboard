import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication, QMessageBox
from app.ui_qt.quiz_json_dialog import QuizJsonDialog, SAMPLE_MULTICHOICE_JSON


def test_import_is_not_automatic_approval(monkeypatch):
    app = QApplication.instance() or QApplication([])
    dialog = QuizJsonDialog()
    dialog.json_edit.setPlainText(SAMPLE_MULTICHOICE_JSON)
    dialog._on_import_clicked()
    assert dialog.parsed_document['approval']['status'] != 'approved'
    assert len(dialog.parsed_document['approval']['content_fingerprint']) == 64
    dialog.close()


def test_bad_answer_rejected(monkeypatch):
    app = QApplication.instance() or QApplication([])
    errors = []
    monkeypatch.setattr(QMessageBox, 'critical', lambda *args: errors.append(args[-1]))
    dialog = QuizJsonDialog()
    data = json.loads(SAMPLE_MULTICHOICE_JSON)
    data[0]['correct_id'] = 'Z'
    dialog.json_edit.setPlainText(json.dumps(data))
    dialog._on_import_clicked()
    assert dialog.parsed_document is None
    assert errors
    dialog.close()
