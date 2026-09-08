import os,json
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from app.ui_qt.quiz_json_dialog import QuizJsonDialog


def test_new_episode_form_persists_context():
    app=QApplication.instance() or QApplication([])
    w=QuizJsonDialog()
    w.channel_profile='fr-culture'
    w.series_input.setText('proverbes')
    w.difficulty_input.setCurrentText('hard')
    w.minutes_input.setValue(14)
    w.json_edit.setPlainText(json.dumps([{'id':'q','question':'Quelle ville ?', 'choices':[{'id':'A','text':'Paris'},{'id':'B','text':'Lyon'}],'correct_id':'A'}]))
    w._on_import_clicked()
    assert w.parsed_document['series']=='proverbes'
    assert w.parsed_document['difficulty_curve']=='hard'
    assert w.parsed_document['target_minutes']==14
    w.close()
