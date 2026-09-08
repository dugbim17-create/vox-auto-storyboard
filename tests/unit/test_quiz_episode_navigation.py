import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
from PySide6.QtWidgets import QApplication
from app.ui_qt.quiz_episode_dialog import QuizEpisodeDialog


def test_switch_preserves_edits_and_cancel_leaves_source_untouched():
    app=QApplication.instance() or QApplication([])
    doc={'engine_v2':True,'questions':[
        {'id':'q1','question':'First?', 'choices':[{'id':'A','text':'One'},{'id':'B','text':'Two'}],'correct_id':'A'},
        {'id':'q2','question':'Second?', 'choices':[{'id':'A','text':'Three'},{'id':'B','text':'Four'}],'correct_id':'B'}]}
    original=deepcopy(doc)
    dialog=QuizEpisodeDialog(doc)
    dialog.fields['question'].setText('Edited first?')
    dialog.selector.setCurrentIndex(1)
    dialog.selector.setCurrentIndex(0)
    assert dialog.fields['question'].text()=='Edited first?'
    assert dialog.document['questions'][1]==original['questions'][1]
    dialog.reject()
    assert doc==original


def test_regeneration_replaces_only_selected_question(monkeypatch):
    app=QApplication.instance() or QApplication([])
    from app.ui_qt import quiz_json_dialog
    doc={'engine_v2':True,'questions':[
        {'id':'q1','question':'First?', 'choices':[{'id':'A','text':'One'},{'id':'B','text':'Two'}],'correct_id':'A'},
        {'id':'q2','question':'Second?', 'choices':[{'id':'A','text':'Three'},{'id':'B','text':'Four'}],'correct_id':'B'}]}
    replacement=deepcopy(doc['questions'][0])
    replacement['question']='Replacement?'
    def simulated_accept(dialog):
        dialog.parsed_document={'questions':[replacement]}
        return 1
    monkeypatch.setattr(quiz_json_dialog.QuizJsonDialog,'exec',simulated_accept)
    editor=QuizEpisodeDialog(doc)
    editor.regenerate_question()
    assert editor.document['questions'][0]['question']=='Replacement?'
    assert editor.document['questions'][1]==doc['questions'][1]
    assert editor.document['approval']['status']=='draft'
    editor.close()
