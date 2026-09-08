"""Vox Studio Qt design tokens and global QSS."""

TOKENS = {
    "canvas": "#08090A",
    "sidebar": "#0D0E12",
    "surface": "#121319",
    "surface_raised": "#171820",
    "surface_hover": "#1D1F28",
    "border": "#262832",
    "border_soft": "#1D1F26",
    "text": "#F5F6FA",
    "text_secondary": "#A7ADBC",
    "text_muted": "#707789",
    "accent": "#705CF6",
    "accent_hover": "#8978FF",
    "accent_soft": "#211B43",
    "success": "#35C48D",
    "warning": "#F2B84B",
    "danger": "#F05252",
}


def build_stylesheet() -> str:
    t = TOKENS
    return f"""
    * {{
        font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
        color: {t['text_secondary']};
        font-size: 13px;
    }}
    QMainWindow, QWidget#Root, QScrollArea, QScrollArea > QWidget > QWidget,
    QStackedWidget, QStackedWidget > QWidget {{ background: {t['canvas']}; }}
    QFrame#Sidebar {{
        background: {t['sidebar']};
        border-right: 1px solid {t['border_soft']};
    }}
    QLabel#Brand {{ color: {t['text']}; font-size: 20px; font-weight: 700; }}
    QLabel#ProBadge {{
        color: #C7BCFF; background: {t['accent_soft']};
        border: 1px solid #3B306C; border-radius: 7px;
        padding: 2px 6px; font-size: 10px; font-weight: 700;
    }}
    QLabel#Overline {{ color: {t['text_muted']}; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}
    QLabel#PageTitle {{ color: {t['text']}; font-size: 25px; font-weight: 650; }}
    QLabel#SectionTitle {{ color: {t['text']}; font-size: 12px; font-weight: 700; letter-spacing: .8px; }}
    QLabel#BodyStrong {{ color: {t['text']}; font-size: 13px; font-weight: 600; }}
    QLabel#Muted {{ color: {t['text_muted']}; font-size: 11px; }}
    QLabel#StatusSuccess {{ color: {t['success']}; font-size: 12px; font-weight: 600; }}
    QFrame#TopBar {{ background: {t['canvas']}; border-bottom: 1px solid {t['border_soft']}; }}
    QFrame#Card, QFrame#AnalysisCard {{
        background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 12px;
    }}
    QFrame#Card[elevation="raised"], QFrame#AnalysisCard[elevation="raised"] {{
        background: {t['surface_raised']}; border: 1px solid #2E303B;
    }}
    QFrame#SceneRow {{ background: #0F1015; border: 1px solid #22242C; border-radius: 9px; }}
    QFrame#SceneRow[selected="true"] {{ background: #17132A; border: 1px solid {t['accent']}; }}
    QFrame#NumberBadge {{ background: {t['accent_soft']}; border: 1px solid #403378; border-radius: 8px; }}
    QLabel#NumberLabel {{ color: #C7BCFF; font-size: 12px; font-weight: 700; }}
    QPushButton {{
        background: #171820; border: 1px solid {t['border']}; border-radius: 8px;
        padding: 8px 13px; color: {t['text_secondary']}; font-weight: 600;
    }}
    QPushButton:hover {{ background: {t['surface_hover']}; color: {t['text']}; border-color: #343746; }}
    QPushButton:disabled {{ background: #1A1C24; color: #696D7C; border-color: #292C36; }}
    QPushButton#PrimaryButton, QPushButton[kind="primary"] {{
        background: {t['accent']}; color: white; border: 1px solid #806EFF;
        border-radius: 9px; padding: 9px 16px; font-weight: 700;
    }}
    QPushButton#PrimaryButton:hover, QPushButton[kind="primary"]:hover {{ background: {t['accent_hover']}; }}
    QPushButton#NavButton {{
        background: transparent; border: 0; border-radius: 8px;
        text-align: left; padding: 9px 12px; color: #8C93A5; font-weight: 600;
    }}
    QPushButton#NavButton:hover {{ background: #14151B; color: {t['text']}; }}
    QPushButton#NavButton[active="true"] {{ background: #1C1733; color: white; border-left: 3px solid {t['accent']}; }}
    QLineEdit, QTextEdit, QComboBox, QDoubleSpinBox, QSpinBox,
    QTableWidget, QListWidget {{
        background: #0D0E12; border: 1px solid {t['border']}; border-radius: 8px;
        padding: 9px 11px; color: {t['text']}; selection-background-color: {t['accent']};
    }}
    QTextEdit QAbstractScrollArea::viewport, QTableWidget QAbstractScrollArea::viewport,
    QListWidget QAbstractScrollArea::viewport {{ background: #0D0E12; color: {t['text']}; }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus,
    QDoubleSpinBox:focus, QSpinBox:focus {{ border: 1px solid {t['accent']}; }}
    QHeaderView::section {{
        background: #171820; color: {t['text_secondary']}; border: 0;
        border-bottom: 1px solid {t['border']}; padding: 8px;
    }}
    QHeaderView, QHeaderView::viewport, QTableCornerButton::section {{
        background: #171820; color: {t['text_secondary']}; border: 0;
    }}
    QTableWidget {{ gridline-color: {t['border_soft']}; alternate-background-color: #111218; }}
    QListWidget#SceneList {{
        background: transparent; border: 0; outline: 0; padding: 0;
    }}
    QListWidget#SceneList::item {{ margin: 0 0 7px 0; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: #30323B; border-radius: 4px; min-height: 32px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QProgressBar {{ background: #1A1B21; border: 0; border-radius: 3px; height: 6px; text-align: center; }}
    QProgressBar::chunk {{ background: {t['accent']}; border-radius: 3px; }}
    QStatusBar#GlobalStatusBar {{ background: {t['sidebar']}; border-top: 1px solid {t['border_soft']}; color: {t['text_muted']}; }}
    """
