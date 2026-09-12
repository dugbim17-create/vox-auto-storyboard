"""Explicit source review UI. No automatic legal claims or imported approvals."""
from copy import deepcopy
from pathlib import Path
import shutil
import uuid

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox,
    QLineEdit, QLabel, QPushButton, QFileDialog, QCheckBox, QDialogButtonBox)
from app.services.quiz_source_review import register_review
from app.services.quiz_asset_policy import LICENSES


class QuizSourceDialog(QDialog):
    def __init__(self, document, directory, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Quiz · Nguồn ảnh và bằng chứng')
        self.resize(720, 760)
        self.document = deepcopy(document)
        self.directory = Path(directory)
        self.slots = []
        layout = QVBoxLayout(self)
        note = QLabel('Chỉ xác nhận khi đã kiểm tra quyền sử dụng. Biên nhận này không phải bảo đảm pháp lý.\nKhông có bằng chứng: Hủy và dùng nút sinh ảnh AI.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.assets = QComboBox()
        for q in self.document.get('questions', []):
            for field, rights in [('reveal_image_path', 'reveal_image_rights'), ('scene_image', 'scene_image_rights')]:
                if q.get(field):
                    self.slots.append((q, field, rights))
                    self.assets.addItem(f"{q.get('id')} · {field}")
            for group in ('cards', 'clues'):
                for index, owner in enumerate(q.get(group, [])):
                    if owner.get('image_path'):
                        self.slots.append((owner, 'image_path', 'image_rights'))
                        self.assets.addItem(f"{q.get('id')} · {group} {index + 1}")
        layout.addWidget(self.assets)
        self.preview = QLabel()
        self.preview.setMinimumHeight(160)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.preview)
        form = QFormLayout()
        self.fields = {}
        for key, label in [('author', 'Tác giả / chủ sở hữu'), ('source_url', 'URL nguồn'), ('license_url', 'URL giấy phép'), ('evidence_url', 'URL bằng chứng'), ('changes', 'Chỉnh sửa đã thực hiện')]:
            edit = QLineEdit()
            edit.setObjectName(key)
            self.fields[key] = edit
            form.addRow(label, edit)
        self.license = QComboBox()
        self.license.addItems(sorted(LICENSES))
        form.addRow('Giấy phép đã kiểm tra', self.license)
        self.evidence = QLineEdit()
        self.evidence.setObjectName('EvidenceFile')
        form.addRow('File bằng chứng lưu cục bộ', self.evidence)
        browse = QPushButton('Chọn file bằng chứng…')
        browse.clicked.connect(self.browse)
        form.addRow(browse)
        layout.addLayout(form)
        self.confirm = QCheckBox('Tôi đã xem nguồn và bằng chứng, xác nhận quyền sử dụng phù hợp.')
        layout.addWidget(self.confirm)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save_review)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.assets.currentIndexChanged.connect(self.select_asset)
        self.select_asset(0)

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Chọn bằng chứng đã lưu', '', 'Evidence (*.txt *.html *.pdf *.png *.jpg);;All files (*)')
        if path:
            self.evidence.setText(path)

    def select_asset(self, index):
        self.confirm.setChecked(False)
        self.evidence.clear()
        if not 0 <= index < len(self.slots):
            self.status.setText('Chưa có ảnh. Sinh asset trước khi quản lý nguồn.')
            return
        owner, field, rights = self.slots[index]
        pixmap = QPixmap(owner[field])
        self.preview.setPixmap(pixmap.scaled(600, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        record = owner.get(rights) or {}
        for key, edit in self.fields.items():
            edit.setText(str(record.get(key, '')))
        self.status.setText('Ảnh AI: không cần chuyển thành ảnh có giấy phép bên ngoài.' if record.get('kind') == 'ai_generated' else str(owner[field]))

    def save_review(self):
        try:
            if not self.confirm.isChecked():
                raise ValueError('Cần xác nhận đã kiểm tra nguồn trước khi lưu.')
            if not self.slots:
                raise ValueError('Không có asset để duyệt.')
            record = {key: edit.text().strip() for key, edit in self.fields.items()}
            if not all(record.values()):
                raise ValueError('Điền đầy đủ tác giả, nguồn, giấy phép, bằng chứng và chỉnh sửa.')
            evidence = Path(self.evidence.text().strip())
            if not evidence.is_file() or not evidence.stat().st_size:
                raise ValueError('File bằng chứng không tồn tại hoặc rỗng.')
            owner, field, rights = self.slots[self.assets.currentIndex()]
            source = Path(owner[field])
            # Copy into a new reviewed bundle. Never overwrite the original/earlier receipt.
            bundle = self.directory / 'reviewed' / uuid.uuid4().hex
            bundle.mkdir(parents=True)
            target = bundle / ('image' + source.suffix)
            proof = bundle / ('evidence' + evidence.suffix)
            shutil.copy2(source, target)
            shutil.copy2(evidence, proof)
            record.update(kind='licensed', license=self.license.currentText())
            record = register_review(target, record, proof)
            owner[field] = str(target.resolve())
            owner[rights] = record
            self.document['approval'] = {'status': 'draft'}
            self.accept()
        except (OSError, ValueError) as exc:
            self.status.setText(str(exc))
