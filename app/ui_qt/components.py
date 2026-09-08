"""Reusable PySide6 components for the Vox Studio shell."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class Card(QFrame):
    def __init__(self, title: str = "", *, object_name: str = "Card", raised: bool = False) -> None:
        super().__init__()
        self.setObjectName(object_name)
        self.setProperty("elevation", "raised" if raised else "flat")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 16, 18, 16)
        self.layout.setSpacing(11)
        self.title_label: QLabel | None = None
        if title:
            self.title_label = QLabel(title.upper())
            self.title_label.setObjectName("SectionTitle")
            self.layout.addWidget(self.title_label)


class NavButton(QPushButton):
    def __init__(self, text: str, *, active: bool = False) -> None:
        super().__init__(text)
        self.setObjectName("NavButton")
        self.setProperty("active", active)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(38)

    def set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)


class SceneRow(QFrame):
    def __init__(
        self,
        number: int,
        title: str,
        description: str,
        time_range: str,
        duration: str,
        *,
        selected: bool = False,
    ) -> None:
        super().__init__()
        self.setObjectName("SceneRow")
        self.setProperty("selected", selected)
        self.setMinimumHeight(76)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(12)

        badge = QFrame()
        badge.setObjectName("NumberBadge")
        badge.setFixedSize(38, 38)
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        number_label = QLabel(f"{number:02d}")
        number_label.setObjectName("NumberLabel")
        number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_layout.addWidget(number_label)
        row.addWidget(badge)

        content = QVBoxLayout()
        content.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("BodyStrong")
        description_label = QLabel(description)
        description_label.setObjectName("Muted")
        description_label.setWordWrap(True)
        metadata = QLabel(time_range)
        metadata.setObjectName("Muted")
        content.addWidget(title_label)
        content.addWidget(description_label)
        content.addWidget(metadata)
        row.addLayout(content, 1)

        duration_label = QLabel(duration)
        duration_label.setObjectName("BodyStrong")
        duration_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(duration_label)


class AnalysisRow(QWidget):
    def __init__(self, label: str, value: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        label_widget = QLabel(label)
        label_widget.setObjectName("Muted")
        value_widget = QLabel(value)
        value_widget.setObjectName("BodyStrong")
        layout.addWidget(label_widget)
        layout.addWidget(value_widget)


class StatPill(QFrame):
    def __init__(self, value: str, label: str) -> None:
        super().__init__()
        self.setStyleSheet("QFrame { background:#0E0F14; border:1px solid #242630; border-radius:8px; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(1)
        self.value = QLabel(value)
        self.value.setObjectName("BodyStrong")
        self.caption = QLabel(label)
        self.caption.setObjectName("Muted")
        layout.addWidget(self.value)
        layout.addWidget(self.caption)


def add_spacer(layout: QVBoxLayout, height: int = 8) -> None:
    spacer = QWidget()
    spacer.setFixedHeight(height)
    layout.addWidget(spacer)
