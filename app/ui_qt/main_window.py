"""PySide6 Vox Studio shell — first visually accepted Script slice."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui_qt.components import AnalysisRow, Card, NavButton, SceneRow, StatPill
from app.ui_qt.theme import build_stylesheet
from app.version import APP_VERSION


class VoxStudioWindow(QMainWindow):
    """Premium dark media-production shell using existing Vox services later."""

    def __init__(self, *, autoload: bool = True) -> None:
        super().__init__()
        self.autoload = autoload
        self.setObjectName("VoxStudioWindow")
        self.setWindowTitle(f"Vox Studio v{APP_VERSION}")
        self.setMinimumSize(1180, 720)
        self.resize(1440, 900)
        self.setStyleSheet(build_stylesheet())
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        self.sidebar = self._build_sidebar()
        shell.addWidget(self.sidebar)
        shell.addWidget(self._build_content(), 1)
        status = QStatusBar()
        status.setObjectName("GlobalStatusBar")
        status.showMessage("Sẵn sàng · Chọn project hoặc nhập chủ đề để bắt đầu")
        self.setStatusBar(status)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 22, 18, 18)
        layout.setSpacing(7)

        brand_row = QHBoxLayout()
        logo = QLabel("◆")
        logo.setStyleSheet("color:#8978FF; font-size:22px; font-weight:700;")
        brand = QLabel("Vox Studio")
        brand.setObjectName("Brand")
        pro = QLabel("PRO")
        pro.setObjectName("ProBadge")
        brand_row.addWidget(logo)
        brand_row.addWidget(brand)
        brand_row.addWidget(pro)
        brand_row.addStretch(1)
        layout.addLayout(brand_row)
        self.new_project_button = QPushButton("＋  Tạo dự án mới")
        self.new_project_button.setObjectName("NewProjectButton")
        self.new_project_button.setProperty("kind", "secondary")
        self.new_project_button.setMinimumHeight(42)
        layout.addWidget(self.new_project_button)
        workflow = QLabel("WORKFLOW")
        workflow.setObjectName("Overline")
        layout.addWidget(workflow)
        nav_host = QWidget()
        nav_host.setObjectName("WorkflowNav")
        nav = QVBoxLayout(nav_host)
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(3)
        self.nav_buttons: dict[str, NavButton] = {}

        # 1. Primary Quiz & Core Studio Navigation (Always visible, clean, focused)
        primary_items = (
            ("quiz", "Quiz", "?"),
            ("projects", "Dự án", "▦"),
            ("logs", "Logs", "≣"),
            ("settings", "Cài đặt", "⚙"),
        )
        for key, label, icon in primary_items:
            button = NavButton(f"{icon}   {label}", active=key == "overview")
            nav.addWidget(button)
            self.nav_buttons[key] = button

        # 2. Toggle button for secondary/advanced documentary tabs
        self.toggle_advanced_button = QPushButton("▸ Tab mở rộng (Phóng sự)")
        self.toggle_advanced_button.setObjectName("ToggleAdvancedButton")
        self.toggle_advanced_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_advanced_button.setStyleSheet(
            "background: transparent; color: #718096; border: none; text-align: left; padding: 6px 8px; font-size: 11px; font-weight: 600;"
        )
        self.toggle_advanced_button.clicked.connect(self._toggle_advanced_tabs)
        nav.addWidget(self.toggle_advanced_button)

        # 3. Collapsible Advanced Container for legacy documentary workflow
        self.advanced_nav_container = QWidget()
        self.advanced_nav_container.setObjectName("AdvancedNavContainer")
        adv_layout = QVBoxLayout(self.advanced_nav_container)
        adv_layout.setContentsMargins(0, 0, 0, 0)
        adv_layout.setSpacing(3)

        self.advanced_nav_keys = {
            "overview", "script", "storyboard", "voice", "visuals",
            "music", "video", "queue", "acceptance", "publish",
            "style", "caption", "render"
        }
        secondary_items = (
            ("overview", "Tổng quan", "⌂"),
            ("script", "Kịch bản", "✦"),
            ("storyboard", "Storyboard", "▤"),
            ("voice", "Giọng đọc", "◉"),
            ("visuals", "Hình ảnh", "◫"),
            ("music", "Nhạc", "♫"),
            ("video", "Video", "▣"),
            ("queue", "Hàng đợi", "≣"),
            ("acceptance", "Nghiệm thu", "✓"),
            ("publish", "Xuất bản", "⇧"),
            ("style", "Vox Style", "◐"),
            ("caption", "Phụ đề", "≡"),
            ("render", "Render", "▶"),
        )
        for key, label, icon in secondary_items:
            button = NavButton(f"{icon}   {label}", active=key == "overview")
            adv_layout.addWidget(button)
            self.nav_buttons[key] = button

        # Library tool buttons inside advanced container
        self.assets_button = NavButton("▧   Assets")
        self.assets_button.setObjectName("AssetsButton")
        self.templates_button = NavButton("▤   Templates")
        self.templates_button.setObjectName("TemplatesButton")
        self.settings_button = NavButton("⚙   Cài đặt providers")
        self.settings_button.setObjectName("SettingsButton")
        adv_layout.addWidget(self.assets_button)
        adv_layout.addWidget(self.templates_button)
        adv_layout.addWidget(self.settings_button)

        # Hidden by default to keep the sidebar compact and clean!
        self.advanced_nav_container.setVisible(False)
        nav.addWidget(self.advanced_nav_container)

        layout.addWidget(nav_host)
        layout.addStretch(1)
        return sidebar

    def _build_content(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 0, 24, 18)
        layout.setSpacing(16)
        layout.addWidget(self._build_topbar())
        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("PageStack")
        self.overview_page = self._build_overview_page()
        self.projects_page = self._build_projects_page()
        self.script_page = self._build_script_page()
        self.storyboard_page = self._build_storyboard_page()
        self.visuals_page = self._build_visuals_page()
        self.style_page = self._build_style_page()
        self.voice_page = self._build_voice_page()
        self.caption_page = self._build_caption_page()
        self.quiz_page = self._build_quiz_page()
        self.render_page = self._build_render_page()
        self.logs_page = self._build_logs_page()
        self.music_page = self._build_music_page()
        self.video_page = self._build_video_page()
        self.queue_page = self._build_media_queue_page()
        self.acceptance_page = self._build_acceptance_page()
        self.publish_page = self._build_publish_page()
        self.settings_page = self._build_settings_page()
        self.pages = {
            "overview": self.overview_page,
            "projects": self.projects_page,
            "script": self.script_page,
            "storyboard": self.storyboard_page,
            "quiz": self.quiz_page,
            "voice": self.voice_page,
            "visuals": self.visuals_page,
            "music": self.music_page,
            "video": self.video_page,
            "queue": self.queue_page,
            "acceptance": self.acceptance_page,
            "publish": self.publish_page,
            "settings": self.settings_page,
            "style": self.style_page,
            "caption": self.caption_page,
            "render": self.render_page,
            "logs": self.logs_page,
        }
        for page in self.pages.values():
            if self.page_stack.indexOf(page) < 0:
                self.page_stack.addWidget(page)
        self.set_media_project_ready(False)
        self.page_stack.setCurrentWidget(self.overview_page)
        layout.addWidget(self.page_stack, 1)
        return content

    def _build_overview_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("OverviewPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        hero = Card("Tổng quan sản xuất", raised=True)
        self.overview_project_state = QLabel("Chưa chọn dự án · Chọn hoặc tạo dự án để bắt đầu")
        self.overview_project_state.setObjectName("OverviewProjectState")
        hero.layout.addWidget(self.overview_project_state)
        self.overview_workflow_text = QLabel(
            "Nguồn nội dung  →  Kịch bản  →  Giọng đọc  →  Hình ảnh & Video  →  "
            "Dựng timeline  →  Nghiệm thu  →  Xuất bản"
        )
        self.overview_workflow_text.setObjectName("OverviewWorkflowText")
        self.overview_workflow_text.setWordWrap(True)
        hero.layout.addWidget(self.overview_workflow_text)
        self.overview_next_action_button = QPushButton("Bắt đầu từ kịch bản")
        self.overview_next_action_button.setObjectName("OverviewNextActionButton")
        self.overview_next_action_button.setProperty("kind", "primary")
        hero.layout.addWidget(self.overview_next_action_button)
        layout.addWidget(hero)
        state_row = QHBoxLayout()
        for title, text in (
            ("Nội dung", "Chưa có kịch bản"),
            ("Voice", "Chưa có audio"),
            ("Media", "Chưa có asset được chọn"),
            ("Đầu ra", "Chưa có final.mp4"),
        ):
            card = Card(title, raised=True)
            label = QLabel(text)
            label.setObjectName("Muted")
            label.setWordWrap(True)
            card.layout.addWidget(label)
            state_row.addWidget(card, 1)
        layout.addLayout(state_row)
        layout.addStretch(1)
        return page

    def _build_projects_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("ProjectsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        card = Card("Dự án", raised=True)
        card.layout.addWidget(QLabel("Chọn dự án ở thanh trên hoặc tạo dự án mới từ sidebar."))
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_storyboard_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("StoryboardPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        card = Card("Storyboard", raised=True)
        self.storyboard_state = QLabel(
            "Storyboard dùng cùng dữ liệu cảnh của project. Tạo hoặc cập nhật từ Kịch bản."
        )
        self.storyboard_state.setWordWrap(True)
        card.layout.addWidget(self.storyboard_state)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_unavailable_page(self, title: str, message: str) -> QWidget:
        page = QWidget()
        page.setObjectName(f"{title.replace(' ', '')}Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        card = Card(title, raised=True)
        label = QLabel(message)
        label.setObjectName("UnavailableMessage")
        label.setWordWrap(True)
        card.layout.addWidget(label)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_music_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("MusicPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        card = Card("Nhạc · nhập file local", raised=True)
        card.layout.addWidget(
            QLabel("File được FFprobe, copy theo SHA vào project rồi mới thành công.")
        )
        row = QHBoxLayout()
        self.music_source_path = QLineEdit()
        self.music_source_path.setObjectName("MusicSourcePath")
        self.music_source_path.setPlaceholderText("Chọn MP3, WAV, M4A hoặc audio local...")
        self.browse_music_button = QPushButton("Chọn file")
        self.browse_music_button.setObjectName("BrowseMusicButton")
        self.queue_music_button = QPushButton("Thêm nhạc vào hàng đợi")
        self.queue_music_button.setObjectName("QueueMusicButton")
        self.queue_music_button.setProperty("kind", "primary")
        row.addWidget(self.music_source_path, 1)
        row.addWidget(self.browse_music_button)
        row.addWidget(self.queue_music_button)
        card.layout.addLayout(row)
        self.music_status = QLabel("Chưa mở project · chưa nhập nhạc")
        self.music_status.setObjectName("MusicStatus")
        self.music_status.setWordWrap(True)
        card.layout.addWidget(self.music_status)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_video_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("VideoPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        card = Card("Video · nhập file local", raised=True)
        card.layout.addWidget(
            QLabel("MP4 được kiểm codec, độ phân giải, FPS và duration trước khi nhập.")
        )
        row = QHBoxLayout()
        self.video_source_path = QLineEdit()
        self.video_source_path.setObjectName("VideoSourcePath")
        self.video_source_path.setPlaceholderText("Chọn MP4 local...")
        self.browse_video_button = QPushButton("Chọn file")
        self.browse_video_button.setObjectName("BrowseVideoButton")
        self.queue_video_button = QPushButton("Thêm video vào hàng đợi")
        self.queue_video_button.setObjectName("QueueVideoButton")
        self.queue_video_button.setProperty("kind", "primary")
        row.addWidget(self.video_source_path, 1)
        row.addWidget(self.browse_video_button)
        row.addWidget(self.queue_video_button)
        card.layout.addLayout(row)
        self.video_status = QLabel("Chưa mở project · chưa nhập video")
        self.video_status.setObjectName("VideoStatus")
        self.video_status.setWordWrap(True)
        card.layout.addWidget(self.video_status)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_media_queue_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("MediaQueuePage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        card = Card("Hàng đợi local · tuần tự", raised=True)
        self.media_queue_table = QTableWidget(0, 6)
        self.media_queue_table.setObjectName("MediaQueueTable")
        self.media_queue_table.setHorizontalHeaderLabels(
            ["Job", "Action", "Trạng thái", "Lần chạy", "Kết quả", "Lỗi"]
        )
        header = self.media_queue_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        card.layout.addWidget(self.media_queue_table, 1)
        actions = QHBoxLayout()
        self.recover_queue_button = QPushButton("Khôi phục job dở")
        self.recover_queue_button.setObjectName("RecoverQueueButton")
        self.run_queue_button = QPushButton("Chạy mục tiếp theo")
        self.run_queue_button.setObjectName("RunQueueButton")
        self.run_queue_button.setProperty("kind", "primary")
        actions.addWidget(self.recover_queue_button)
        actions.addWidget(self.run_queue_button)
        actions.addStretch(1)
        card.layout.addLayout(actions)
        self.media_queue_status = QLabel("Chưa mở project · concurrency=1")
        self.media_queue_status.setObjectName("MediaQueueStatus")
        card.layout.addWidget(self.media_queue_status)
        layout.addWidget(card, 1)
        return page

    def _build_publish_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PublishPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        card = Card("Xuất bản · chuẩn bị local", raised=True)
        card.layout.addWidget(
            QLabel("Chỉ tạo bản giao local + manifest. Không upload, không đăng nền tảng.")
        )
        row = QHBoxLayout()
        self.publish_source_path = QLineEdit()
        self.publish_source_path.setObjectName("PublishSourcePath")
        self.publish_source_path.setPlaceholderText("Chọn final.mp4 đã nghiệm thu...")
        self.browse_publish_button = QPushButton("Chọn final.mp4")
        self.browse_publish_button.setObjectName("BrowsePublishButton")
        self.prepare_publish_button = QPushButton("Chuẩn bị package local")
        self.prepare_publish_button.setObjectName("PreparePublishButton")
        self.prepare_publish_button.setProperty("kind", "primary")
        row.addWidget(self.publish_source_path, 1)
        row.addWidget(self.browse_publish_button)
        row.addWidget(self.prepare_publish_button)
        card.layout.addLayout(row)
        self.publish_status = QLabel("0 network calls · chưa có package local")
        self.publish_status.setObjectName("PublishStatus")
        self.publish_status.setWordWrap(True)
        card.layout.addWidget(self.publish_status)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_acceptance_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("AcceptancePage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        card = Card("Nghiệm thu", raised=True)
        self.acceptance_summary = QLabel(
            "Chưa có final.mp4 · Render xong để kiểm codec, audio, khung hình đen và artifact."
        )
        self.acceptance_summary.setWordWrap(True)
        card.layout.addWidget(self.acceptance_summary)
        layout.addWidget(card)
        semantic = Card("Semantic Motion Pilot", raised=True)
        semantic.layout.addWidget(
            QLabel(
                "Candidate cô lập gồm 6 grammar · Character/object/path/data motion · "
                "không gọi provider và không sửa project hiện tại."
            )
        )
        self.semantic_pilot_status = QLabel("Chưa render semantic candidate")
        self.semantic_pilot_status.setObjectName("Muted")
        semantic.layout.addWidget(self.semantic_pilot_status)
        self.semantic_pilot_artifact = QLabel("Chưa có artifact")
        self.semantic_pilot_artifact.setWordWrap(True)
        semantic.layout.addWidget(self.semantic_pilot_artifact)
        semantic_actions = QHBoxLayout()
        self.render_semantic_pilot_button = QPushButton(
            "Render semantic pilot · 0 provider calls"
        )
        self.render_semantic_pilot_button.setObjectName("RenderSemanticPilotButton")
        self.render_semantic_pilot_button.setProperty("kind", "primary")
        self.open_semantic_pilot_button = QPushButton("Mở final semantic pilot")
        self.open_semantic_pilot_button.setObjectName("OpenSemanticPilotButton")
        self.open_semantic_pilot_button.setEnabled(False)
        semantic_actions.addWidget(self.render_semantic_pilot_button)
        semantic_actions.addWidget(self.open_semantic_pilot_button)
        semantic.layout.addLayout(semantic_actions)
        layout.addWidget(semantic)
        layout.addStretch(1)
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("SettingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        card = Card("Cài đặt", raised=True)
        card.layout.addWidget(QLabel("Quản lý provider, model và đường dẫn runtime."))
        self.open_settings_from_page_button = QPushButton("Mở cài đặt providers")
        self.open_settings_from_page_button.setObjectName("OpenSettingsFromPageButton")
        card.layout.addWidget(self.open_settings_from_page_button)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_script_page(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(16)
        page_layout.addWidget(self._build_topic_card())
        page_layout.addLayout(self._build_script_workspace(), 1)
        scroll.setWidget(page)
        return scroll

    def _build_visuals_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("VisualsPage")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        scene_card = Card("Danh sách cảnh", raised=True)
        scene_card.setFixedWidth(250)
        self.visual_scene_list = QListWidget()
        self.visual_scene_list.setObjectName("VisualSceneList")
        scene_card.layout.addWidget(self.visual_scene_list)
        layout.addWidget(scene_card)

        prompt_card = Card("Prompt cảnh", raised=True)
        self.visual_prompt_editor = QTextEdit()
        self.visual_prompt_editor.setObjectName("VisualPromptEditor")
        self.visual_prompt_editor.setPlaceholderText("Chọn một scene để chỉnh prompt ảnh...")
        prompt_card.layout.addWidget(self.visual_prompt_editor, 1)
        controls = QHBoxLayout()
        self.save_prompt_button = QPushButton("Lưu prompt")
        self.save_prompt_button.setObjectName("SavePromptButton")
        self.generate_images_button = QPushButton("Tạo ảnh")
        self.generate_images_button.setObjectName("GenerateImagesButton")
        self.generate_images_button.setProperty("kind", "primary")
        controls.addWidget(self.save_prompt_button)
        controls.addWidget(self.generate_images_button)
        prompt_card.layout.addLayout(controls)
        layout.addWidget(prompt_card, 1)

        result_card = Card("ẢNH ĐÃ TẠO", raised=True)
        result_card.setFixedWidth(320)
        self.image_preview = QLabel("Chưa có ảnh được tạo")
        self.image_preview.setObjectName("ImagePreview")
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setMinimumHeight(330)
        self.image_preview.setStyleSheet("background:#0D0E12;border:1px solid #262832;border-radius:10px;color:#707789;")
        result_card.layout.addWidget(self.image_preview)
        self.generated_asset_list = QListWidget()
        self.generated_asset_list.setObjectName("GeneratedAssetList")
        result_card.layout.addWidget(self.generated_asset_list, 1)
        self.use_image_button = QPushButton("Dùng ảnh này")
        self.use_image_button.setObjectName("UseImageButton")
        self.use_image_button.setProperty("kind", "primary")
        result_card.layout.addWidget(self.use_image_button)
        layout.addWidget(result_card)
        return page

    def _build_style_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("StylePage")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        controls = Card("Chọn & tùy chỉnh style", raised=True)
        self.style_preset_list = QListWidget()
        self.style_preset_list.setObjectName("StylePresetList")
        for preset in (
            "editorial_collage",
            "johnny_harris_geopolitics",
            "magnates_media_billionaires",
            "true_crime_dossier",
            "archival_vintage_history",
            "cyberpunk_tech_breakdown",
            "tactical_investigation",
            "documentary",
            "minimal_motion",
        ):
            self.style_preset_list.addItem(preset)
        controls.layout.addWidget(self.style_preset_list)
        self.style_visual_language = QLineEdit()
        self.style_visual_language.setObjectName("StyleVisualLanguage")
        self.style_visual_language.setPlaceholderText("Visual language")
        controls.layout.addWidget(self.style_visual_language)
        self.style_palette = QLineEdit()
        self.style_palette.setObjectName("StylePalette")
        self.style_palette.setPlaceholderText("#111111, #f4f4f4, #e5484d")
        controls.layout.addWidget(self.style_palette)
        self.style_texture = QLineEdit()
        self.style_texture.setObjectName("StyleTexture")
        self.style_texture.setPlaceholderText("paper grain, ink, collage")
        controls.layout.addWidget(self.style_texture)
        self.save_style_button = QPushButton("Lưu bản nháp")
        self.save_style_button.setObjectName("SaveStyleButton")
        self.save_style_button.setProperty("kind", "primary")
        controls.layout.addWidget(self.save_style_button)
        self.apply_style_button = QPushButton("Áp dụng style")
        self.apply_style_button.setObjectName("ApplyStyleButton")
        controls.layout.addWidget(self.apply_style_button)
        self.style_state = QLabel(
            "Bản nháp chưa ảnh hưởng ảnh/render cho đến khi bấm Áp dụng style."
        )
        self.style_state.setObjectName("StyleState")
        self.style_state.setWordWrap(True)
        controls.layout.addWidget(self.style_state)
        self.style_freshness_summary = QLabel(
            "fresh=0 · stale=0 · unknown=0 · missing=0"
        )
        self.style_freshness_summary.setObjectName("StyleFreshnessSummary")
        self.style_freshness_summary.setWordWrap(True)
        controls.layout.addWidget(self.style_freshness_summary)
        self.regenerate_style_scene_button = QPushButton("Tạo lại scene hiện tại")
        self.regenerate_style_scene_button.setObjectName("RegenerateStyleSceneButton")
        controls.layout.addWidget(self.regenerate_style_scene_button)
        self.regenerate_all_style_images_button = QPushButton("Tạo lại tất cả ảnh")
        self.regenerate_all_style_images_button.setObjectName(
            "RegenerateAllStyleImagesButton"
        )
        controls.layout.addWidget(self.regenerate_all_style_images_button)
        layout.addWidget(controls, 1)
        preview = Card("Preview", raised=True)
        self.style_preview = QLabel("Style preview dùng dữ liệu project đã lưu")
        self.style_preview.setObjectName("StylePreview")
        self.style_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.style_preview.setMinimumWidth(430)
        preview.layout.addWidget(self.style_preview)
        layout.addWidget(preview)
        return page

    def _build_voice_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("VoicePage")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        controls = Card("Tạo voice", raised=True)
        self.voice_profile = QComboBox()
        self.voice_profile.setObjectName("VoiceProfile")
        self.voice_profile.addItems(["voice_vi_01", "Minh Quang", "Mạnh Dũng", "Nguyệt Nga"])
        controls.layout.addWidget(self.voice_profile)
        self.voice_speed = QDoubleSpinBox()
        self.voice_speed.setObjectName("VoiceSpeed")
        self.voice_speed.setRange(0.5, 2.0)
        self.voice_speed.setSingleStep(0.05)
        self.voice_speed.setValue(1.0)
        controls.layout.addWidget(self.voice_speed)
        self.generate_voice_button = QPushButton("Tạo voice")
        self.generate_voice_button.setObjectName("GenerateVoiceButton")
        self.generate_voice_button.setProperty("kind", "primary")
        controls.layout.addWidget(self.generate_voice_button)
        layout.addWidget(controls)
        results = Card("Kết quả voice", raised=True)
        self.voice_result_list = QListWidget()
        self.voice_result_list.setObjectName("VoiceResultList")
        results.layout.addWidget(self.voice_result_list)
        layout.addWidget(results, 1)
        return page

    def _build_caption_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("CaptionPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        card = Card("Caption tự động", raised=True)
        self.caption_table = QTableWidget(0, 4)
        self.caption_table.setObjectName("CaptionTable")
        self.caption_table.setHorizontalHeaderLabels(["#", "Bắt đầu", "Kết thúc", "Nội dung"])
        card.layout.addWidget(self.caption_table)
        buttons = QHBoxLayout()
        self.generate_caption_button = QPushButton("Tạo caption")
        self.generate_caption_button.setObjectName("GenerateCaptionButton")
        self.generate_caption_button.setProperty("kind", "primary")
        self.export_srt_button = QPushButton("Xuất SRT")
        self.export_srt_button.setObjectName("ExportSrtButton")
        buttons.addWidget(self.generate_caption_button)
        buttons.addWidget(self.export_srt_button)
        buttons.addStretch(1)
        card.layout.addLayout(buttons)
        layout.addWidget(card)
        return page

    def _build_render_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("RenderPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        prerequisites = Card("Điều kiện render", raised=True)
        self.render_prerequisites = QLabel(
            "Mở project để kiểm tra voice, selected image, motion, scenes và final artifact."
        )
        self.render_prerequisites.setObjectName("RenderPrerequisites")
        self.render_prerequisites.setWordWrap(True)
        prerequisites.layout.addWidget(self.render_prerequisites)
        layout.addWidget(prerequisites)
        progress_card = Card("Tiến trình render", raised=True)
        self.render_progress = QProgressBar()
        self.render_progress.setObjectName("RenderProgress")
        self.render_progress.setRange(0, 100)
        progress_card.layout.addWidget(self.render_progress)
        self.final_artifact_path = QLabel("Chưa có final.mp4")
        self.final_artifact_path.setObjectName("FinalArtifactPath")
        progress_card.layout.addWidget(self.final_artifact_path)
        actions = QHBoxLayout()
        self.render_final_button = QPushButton("Render final")
        self.render_final_button.setObjectName("RenderFinalButton")
        self.render_final_button.setProperty("kind", "primary")
        self.cancel_render_button = QPushButton("Dừng sau stage hiện tại")
        self.cancel_render_button.setObjectName("CancelRenderButton")
        self.retry_scene_button = QPushButton("Retry scene")
        self.retry_scene_button.setObjectName("RetrySceneButton")
        actions.addWidget(self.render_final_button)
        actions.addWidget(self.cancel_render_button)
        actions.addWidget(self.retry_scene_button)
        progress_card.layout.addLayout(actions)
        layout.addWidget(progress_card, 1)
        return page

    def _build_quiz_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("QuizPage")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        review = Card("⚡ Quiz Studio · Ngân hàng câu hỏi & Mẫu", raised=True)
        self.quiz_review_card = review

        # Quick Preset Selector Row
        preset_row = QHBoxLayout()
        preset_lbl = QLabel("Mẫu hot:")
        preset_lbl.setStyleSheet("color:#A0AEC0; font-weight:600; font-size:12px;")
        self.quiz_preset_combo = QComboBox()
        self.quiz_preset_combo.setObjectName("QuizPresetCombo")
        self.quiz_preset_combo.addItems([
            "⚡ QuizMystra 4-Cards (Who is Pregnant / Killer / Dating)",
            "🕵️ QuizMystra Visual Riddle (Logic Scene Anomaly)",
            "🇺🇸 US World Flag Challenge (30 câu Master 5.5 phút)",
            "🎁 Multi-Mode Dynamic Quiz (Travel Battle, Mystery Box)",
            "🎯 Pilot 5 câu chuẩn hoá (Địa lý Việt Nam)",
            "📋 30 câu chuẩn hoá (Candidate Bank)",
        ])
        self.load_preset_quick_button = QPushButton("⚡ Nạp nhanh")
        self.load_preset_quick_button.setObjectName("LoadPresetQuickButton")
        self.load_preset_quick_button.setProperty("kind", "secondary")
        preset_row.addWidget(preset_lbl)
        preset_row.addWidget(self.quiz_preset_combo, 1)
        preset_row.addWidget(self.load_preset_quick_button)
        review.layout.addLayout(preset_row)
        from app.services.quiz_channel_profiles import PROFILES
        self.quiz_channel_combo = QComboBox()
        self.quiz_channel_combo.setObjectName("QuizChannelCombo")
        self.quiz_channel_combo.addItem("Baseline VI/EN · không đổi", "")
        for key, profile in PROFILES.items():
            self.quiz_channel_combo.addItem(profile["name"], key)
        review.layout.addWidget(self.quiz_channel_combo)

        style_row = QHBoxLayout()
        style_row.addWidget(QLabel("Visual style"))
        self.quiz_style_combo = QComboBox()
        self.quiz_style_combo.setObjectName("QuizStyleCombo")
        self.quiz_style_combo.addItem("Baseline · legacy route", "")
        self.quiz_style_combo.addItem("Sport Scoreboard", "sport-scoreboard")
        self.quiz_style_combo.addItem("Editorial Culture", "editorial-culture")
        self.quiz_style_combo.addItem("Clear Knowledge", "clear-knowledge")
        self.quiz_motion_combo = QComboBox()
        self.quiz_motion_combo.setObjectName("QuizMotionCombo")
        for motion in ("low", "medium", "high"):
            self.quiz_motion_combo.addItem(motion.capitalize(), motion)
        style_row.addWidget(self.quiz_style_combo, 1)
        style_row.addWidget(QLabel("Motion"))
        style_row.addWidget(self.quiz_motion_combo)
        review.layout.addLayout(style_row)
        analytics_button = QPushButton("Channel analytics · mở CSV")
        analytics_button.clicked.connect(self._open_channel_analytics)
        review.layout.addWidget(analytics_button)

        research_row = QHBoxLayout()
        self.quiz_topic_input = QLineEdit("Địa lý Việt Nam")
        self.quiz_topic_input.setObjectName("QuizTopicInput")
        self.quiz_topic_input.setPlaceholderText("Nhập chủ đề quiz...")
        self.research_quiz_button = QPushButton("Tạo pilot 5 câu")
        self.research_quiz_button.setObjectName("ResearchQuizButton")
        self.research_quiz_button.setProperty("kind", "primary")
        research_row.addWidget(self.quiz_topic_input, 1)
        research_row.addWidget(self.research_quiz_button)
        review.layout.addLayout(research_row)

        file_row = QHBoxLayout()
        self.quiz_file_path = QLineEdit("presets/quiz_5_vi_candidates_verified.json")
        self.quiz_file_path.setObjectName("QuizFilePath")
        self.load_quiz_button = QPushButton("Tải candidate bank")
        self.load_quiz_button.setObjectName("LoadQuizButton")
        self.paste_json_button = QPushButton("✦ AI & Dán JSON Quiz")
        self.paste_json_button.setObjectName("PasteJsonButton")
        self.paste_json_button.setProperty("kind", "primary")
        file_row.addWidget(self.quiz_file_path, 1)
        file_row.addWidget(self.load_quiz_button)
        file_row.addWidget(self.paste_json_button)
        review.layout.addLayout(file_row)

        self.quiz_question_table = QTableWidget(0, 8)
        self.quiz_question_table.setObjectName("QuizQuestionTable")
        self.quiz_question_table.setHorizontalHeaderLabels(
            ["#", "Câu hỏi", "A", "B", "C", "Đúng", "Nguồn", "Trạng thái"]
        )
        self.quiz_question_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        header = self.quiz_question_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.quiz_question_table.setColumnWidth(0, 42)
        self.quiz_question_table.setColumnWidth(5, 56)
        self.quiz_question_table.setColumnWidth(7, 84)
        review.layout.addWidget(self.quiz_question_table, 1)
        actions = QHBoxLayout()
        self.save_quiz_draft_button = QPushButton("Lưu nháp")
        self.save_quiz_draft_button.setObjectName("SaveQuizDraftButton")
        self.approve_quiz_button = QPushButton("Duyệt 5 câu")
        self.approve_quiz_button.setObjectName("ApproveQuizButton")
        self.approve_quiz_button.setProperty("kind", "primary")
        actions.addWidget(self.save_quiz_draft_button)
        self.quiz_generate_assets_button = QPushButton("Sinh ảnh thiếu · tối đa 6")
        actions.addWidget(self.quiz_generate_assets_button)
        actions.addWidget(self.approve_quiz_button)
        review.layout.addLayout(actions)
        layout.addWidget(review, 3)

        operate = Card("🎬 Xuất xưởng & Trình chiếu", raised=True)
        operate.setMinimumWidth(380)

        fmt_row = QHBoxLayout()
        fmt_lbl = QLabel("Tỉ lệ:")
        fmt_lbl.setStyleSheet("color:#A0AEC0; font-weight:600; font-size:12px;")
        self.quiz_aspect_combo = QComboBox()
        self.quiz_aspect_combo.setObjectName("QuizAspectCombo")
        self.quiz_aspect_combo.addItems(["16:9 Ngang (YouTube Widescreen)", "9:16 Dọc (TikTok / Shorts)"])
        fmt_row.addWidget(fmt_lbl)
        fmt_row.addWidget(self.quiz_aspect_combo, 1)
        operate.layout.addLayout(fmt_row)

        voice_row = QHBoxLayout()
        self.quiz_voice_combo = QComboBox()
        self.quiz_voice_combo.setEditable(True)
        self.quiz_voice_combo.addItems(["manh_dung", "minh_khang", "ngoc_huyen_moi", "ngocngan3701", "nguyet_nga", "en_US-ryan-high"])
        self.quiz_speed_spin = QDoubleSpinBox()
        self.quiz_speed_spin.setRange(0.25, 3.0)
        self.quiz_speed_spin.setSingleStep(0.05)
        self.quiz_speed_spin.setValue(1.05)
        voice_row.addWidget(QLabel("Piper · Giọng / tốc độ"))
        voice_row.addWidget(self.quiz_voice_combo)
        voice_row.addWidget(self.quiz_speed_spin)
        operate.layout.addLayout(voice_row)

        self.quiz_preview = QTextEdit()
        self.quiz_preview.setObjectName("QuizPreview")
        self.quiz_preview.setReadOnly(True)
        self.quiz_preview.setPlaceholderText("Chọn một câu để review nội dung và nguồn...")
        operate.layout.addWidget(self.quiz_preview, 1)

        preview_controls = QHBoxLayout()
        self.quiz_preview_state_combo = QComboBox()
        self.quiz_preview_state_combo.setObjectName("QuizPreviewStateCombo")
        self.quiz_preview_state_combo.addItem("Question", "question")
        self.quiz_preview_state_combo.addItem("Reveal", "reveal")
        self.quiz_preview_aspect_combo = QComboBox()
        self.quiz_preview_aspect_combo.setObjectName("QuizPreviewAspectCombo")
        self.quiz_preview_aspect_combo.addItem("16:9", "16:9")
        self.quiz_preview_aspect_combo.addItem("9:16", "9:16")
        self.quiz_preview_button = QPushButton("Preview style")
        self.quiz_preview_button.setObjectName("QuizPreviewButton")
        self.quiz_preview_button.setProperty("kind", "secondary")
        self.quiz_save_style_button = QPushButton("Save style snapshot")
        self.quiz_save_style_button.setObjectName("QuizSaveStyleButton")
        self.quiz_cancel_style_button = QPushButton("Cancel style")
        self.quiz_cancel_style_button.setObjectName("QuizCancelStyleButton")
        preview_controls.addWidget(self.quiz_preview_state_combo)
        preview_controls.addWidget(self.quiz_preview_aspect_combo)
        preview_controls.addWidget(self.quiz_preview_button)
        preview_controls.addWidget(self.quiz_save_style_button)
        preview_controls.addWidget(self.quiz_cancel_style_button)
        operate.layout.addLayout(preview_controls)
        self.quiz_preview_image = QLabel("Chưa có style preview")
        self.quiz_preview_image.setObjectName("QuizPreviewImage")
        self.quiz_preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.quiz_preview_image.setMinimumSize(280, 180)
        self.quiz_preview_image.setProperty("preview_status", "empty")
        operate.layout.addWidget(self.quiz_preview_image)
        self.quiz_style_preview_status = QLabel("Preview chưa chạy")
        self.quiz_style_preview_status.setObjectName("QuizStylePreviewStatus")
        self.quiz_style_preview_status.setWordWrap(True)
        operate.layout.addWidget(self.quiz_style_preview_status)
        self.quiz_approval_fingerprint = QLabel("Chưa duyệt")
        self.quiz_approval_fingerprint.setObjectName("QuizApprovalFingerprint")
        self.quiz_approval_fingerprint.setWordWrap(True)
        operate.layout.addWidget(self.quiz_approval_fingerprint)
        self.quiz_output_dir = QLineEdit("output/quiz-pilot-5")
        self.quiz_output_dir.setObjectName("QuizOutputDir")
        operate.layout.addWidget(self.quiz_output_dir)
        self.render_quiz_button = QPushButton("Render pilot 5 câu")
        self.render_quiz_button.setObjectName("RenderQuizButton")
        self.render_quiz_button.setProperty("kind", "primary")
        self.render_quiz_button.setEnabled(False)
        operate.layout.addWidget(self.render_quiz_button)
        self.quiz_progress = QProgressBar()
        self.quiz_progress.setObjectName("QuizProgress")
        self.quiz_progress.setRange(0, 100)
        operate.layout.addWidget(self.quiz_progress)
        self.quiz_status = QLabel("Phase 2 · chưa gọi AI/TTS/render")
        self.quiz_status.setObjectName("QuizStatus")
        self.quiz_status.setWordWrap(True)
        operate.layout.addWidget(self.quiz_status)
        self.quiz_artifact_path = QLabel("Chưa có MP4")
        self.quiz_artifact_path.setObjectName("QuizArtifactPath")
        operate.layout.addWidget(self.quiz_artifact_path)

        quick_acts = QHBoxLayout()
        self.open_output_folder_button = QPushButton("📁 Thư mục video")
        self.open_output_folder_button.setObjectName("OpenOutputFolderButton")
        self.play_latest_video_button = QPushButton("▶ Phát video MP4")
        self.play_latest_video_button.setObjectName("PlayLatestVideoButton")
        quick_acts.addWidget(self.open_output_folder_button)
        quick_acts.addWidget(self.play_latest_video_button)
        operate.layout.addLayout(quick_acts)

        layout.addWidget(operate, 2)
        return page

    def _build_logs_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("LogsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        friendly = Card("Tiến trình", raised=True)
        self.friendly_log = QTextEdit()
        self.friendly_log.setObjectName("FriendlyLog")
        self.friendly_log.setReadOnly(True)
        self.friendly_log.setPlaceholderText("Tiến trình thao tác sẽ xuất hiện tại đây...")
        friendly.layout.addWidget(self.friendly_log)
        layout.addWidget(friendly, 1)
        technical = Card("Log kỹ thuật", raised=True)
        self.technical_log = QTextEdit()
        self.technical_log.setObjectName("TechnicalLog")
        self.technical_log.setReadOnly(True)
        self.technical_log.setPlaceholderText("Provider, artifact path và lỗi kỹ thuật...")
        technical.layout.addWidget(self.technical_log)
        actions = QHBoxLayout()
        self.clear_logs_button = QPushButton("Xóa màn hình log")
        self.clear_logs_button.setObjectName("ClearLogsButton")
        self.open_log_folder_button = QPushButton("Mở thư mục log")
        self.open_log_folder_button.setObjectName("OpenLogFolderButton")
        actions.addWidget(self.clear_logs_button)
        actions.addWidget(self.open_log_folder_button)
        actions.addStretch(1)
        technical.layout.addLayout(actions)
        layout.addWidget(technical, 1)
        return page

    def _build_topbar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(62)
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 10, 0, 10)
        self.project_selector = QComboBox()
        self.project_selector.setObjectName("ProjectSelector")
        self.project_selector.addItem("Chưa chọn dự án")
        self.project_selector.setMinimumWidth(270)
        row.addWidget(self.project_selector)
        row.addStretch(1)
        self.provider_status = QLabel("●  Đang kiểm tra providers...")
        self.provider_status.setObjectName("ProviderStatus")
        row.addWidget(self.provider_status)
        self.guide_button = QPushButton("Hướng dẫn")
        self.guide_button.setObjectName("GuideButton")
        row.addWidget(self.guide_button)
        self.open_project_button = QPushButton("Mở project")
        self.open_project_button.setObjectName("OpenProjectButton")
        row.addWidget(self.open_project_button)
        return bar

    def _build_topic_card(self) -> Card:
        self.topic_card = Card("Chủ đề / Ý tưởng", raised=True)
        self.topic_card.setProperty("elevation", "raised")
        topic_row = QHBoxLayout()
        self.topic_input = QLineEdit()
        self.topic_input.setObjectName("TopicInput")
        self.topic_input.setPlaceholderText("Nhập chủ đề video, nhân vật hoặc góc khai thác...")
        self.topic_input.setMinimumHeight(42)
        topic_row.addWidget(self.topic_input, 1)
        self.generate_script_button = QPushButton("✦  AI Viết kịch bản")
        self.generate_script_button.setObjectName("GenerateScriptButton")
        self.generate_script_button.setProperty("kind", "primary")
        self.generate_script_button.setMinimumHeight(42)
        topic_row.addWidget(self.generate_script_button)

        self.auto_pipeline_button = QPushButton("🚀  1-CLICK TỰ ĐỘNG TẠO VIDEO")
        self.auto_pipeline_button.setObjectName("AutoPipelineButton")
        self.auto_pipeline_button.setProperty("kind", "accent")
        self.auto_pipeline_button.setMinimumHeight(42)
        self.auto_pipeline_button.setStyleSheet("background-color: #2E7D32; color: #FFFFFF; font-weight: bold; padding: 0 16px; border-radius: 6px;")
        topic_row.addWidget(self.auto_pipeline_button)
        self.topic_card.layout.addLayout(topic_row)
        self.script_editor = QTextEdit()
        self.script_editor.setObjectName("ScriptEditor")
        self.script_editor.setPlaceholderText("Nhập hoặc chỉnh sửa nội dung kịch bản nguồn...")
        self.script_editor.setMinimumHeight(100)
        self.topic_card.layout.addWidget(self.script_editor)
        example = QLabel("Gợi ý: nhân vật, sự kiện, câu hỏi hoặc góc khai thác cụ thể")
        example.setObjectName("Muted")
        self.topic_card.layout.addWidget(example)
        return self.topic_card

    def _build_script_workspace(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(14)
        self.script_card = Card("Kịch bản · chưa có cảnh", raised=True)
        self.script_card.setProperty("elevation", "raised")
        self.script_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        toolbar = QHBoxLayout()
        stats = QHBoxLayout()
        self.scene_count_stat = StatPill("0", "Cảnh")
        self.duration_stat = StatPill("00:00", "Thời lượng")
        self.word_count_stat = StatPill("0", "Từ")
        stats.addWidget(self.scene_count_stat)
        stats.addWidget(self.duration_stat)
        stats.addWidget(self.word_count_stat)
        toolbar.addLayout(stats)
        toolbar.addStretch(1)
        edit_button = QPushButton("Chỉnh sửa")
        edit_button.clicked.connect(self.script_editor.setFocus)
        toolbar.addWidget(edit_button)
        self.script_card.layout.addLayout(toolbar)
        self.scene_list = QListWidget()
        self.scene_list.setObjectName("SceneList")
        self.scene_list.setSpacing(0)
        self.script_card.layout.addWidget(self.scene_list, 1)
        footer = QHBoxLayout()
        self.save_script_button = QPushButton("Lưu script")
        self.save_script_button.setObjectName("SaveScriptButton")
        footer.addWidget(self.save_script_button)
        self.create_storyboard_button = QPushButton("Tạo storyboard")
        self.create_storyboard_button.setObjectName("CreateStoryboardButton")
        self.create_storyboard_button.setProperty("kind", "primary")
        footer.addWidget(self.create_storyboard_button)
        footer.addStretch(1)
        self.saved_badge = QLabel("Chưa tải project")
        self.saved_badge.setObjectName("StatusSuccess")
        footer.addWidget(self.saved_badge)
        self.script_card.layout.addLayout(footer)
        row.addWidget(self.script_card, 1)
        self.analysis_card = self._build_analysis_card()
        row.addWidget(self.analysis_card)
        return row

    def _build_analysis_card(self) -> Card:
        card = Card("Phân tích nội dung", object_name="AnalysisCard", raised=True)
        card.setMinimumWidth(300)
        card.setMaximumWidth(340)
        grid_host = QWidget()
        self.analysis_grid = QGridLayout(grid_host)
        self.analysis_grid.setContentsMargins(0, 0, 0, 0)
        self.analysis_grid.setVerticalSpacing(14)
        pairs = (
            ("Chủ đề chính", "Chưa phân tích"),
            ("Cảm xúc chủ đạo", "Chưa phân tích"),
            ("Phong cách phù hợp", "Chưa chọn"),
            ("Độ dài đề xuất", "Chưa có dữ liệu"),
        )
        for index, (label, value) in enumerate(pairs):
            self.analysis_grid.addWidget(AnalysisRow(label, value), index, 0)
        card.layout.addWidget(grid_host)
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background:#272933;")
        card.layout.addWidget(divider)
        suggestion_title = QLabel("GỢI Ý CẢI TIẾN")
        suggestion_title.setObjectName("SectionTitle")
        card.layout.addWidget(suggestion_title)
        for text in (
            "Phân tích sẽ xuất hiện sau khi storyboard được tạo.",
        ):
            bullet = QLabel(f"•  {text}")
            bullet.setWordWrap(True)
            bullet.setObjectName("Muted")
            card.layout.addWidget(bullet)
        title_heading = QLabel("TIÊU ĐỀ ĐỀ XUẤT")
        title_heading.setObjectName("SectionTitle")
        card.layout.addWidget(title_heading)
        self.title_suggestions = QWidget()
        self.title_suggestions.setObjectName("TitleSuggestions")
        suggestions = QVBoxLayout(self.title_suggestions)
        suggestions.setContentsMargins(0, 0, 0, 0)
        suggestions.setSpacing(8)
        for text in (
            "Chưa có tiêu đề đề xuất",
        ):
            label = QLabel(text)
            label.setWordWrap(True)
            label.setObjectName("BodyStrong")
            suggestions.addWidget(label)
        card.layout.addWidget(self.title_suggestions)
        card.layout.addStretch(1)
        self.regenerate_storyboard_button = QPushButton("Tạo kịch bản khác")
        self.regenerate_storyboard_button.setObjectName("RegenerateStoryboardButton")
        self.regenerate_storyboard_button.setProperty("kind", "primary")
        card.layout.addWidget(self.regenerate_storyboard_button)
        return card

    def set_projects(self, projects: list[dict], selected_id: str | None = None) -> None:
        self.project_selector.blockSignals(True)
        self.project_selector.clear()
        self.project_selector.addItem("Chưa chọn dự án", None)
        selected_index = 0
        for index, project in enumerate(projects, start=1):
            title = project.get("title") or project["project_id"]
            self.project_selector.addItem(title, project["project_id"])
            if project["project_id"] == selected_id:
                selected_index = index
        self.project_selector.setCurrentIndex(selected_index)
        self.project_selector.blockSignals(False)

    def set_project_content(self, project: dict, scenes: list[dict]) -> None:
        title = str(project.get("title") or project.get("project_id") or "Project")
        status = str(project.get("status") or "unknown")
        self.overview_project_state.setText(f"{title} · trạng thái {status}")
        self.topic_input.setText(project.get("title") or "")
        self.script_editor.setPlainText(project.get("script_text") or "")
        self.scene_list.clear()
        self.visual_scene_list.clear()
        self._visual_scenes = scenes
        total_duration = sum(
            float(scene.get("estimated_duration_seconds") or 0) for scene in scenes
        )
        word_count = len((project.get("script_text") or "").split())
        if self.script_card.title_label is not None:
            title = f"Kịch bản · {len(scenes)} cảnh" if scenes else "Kịch bản · chưa có cảnh"
            self.script_card.title_label.setText(title.upper())
        self.scene_count_stat.value.setText(str(len(scenes)))
        self.duration_stat.value.setText(self._format_time(total_duration))
        self.word_count_stat.value.setText(f"{word_count:,}".replace(",", "."))
        for index, scene in enumerate(scenes, start=1):
            duration_seconds = float(scene.get("estimated_duration_seconds") or 0)
            start_seconds = sum(float(item.get("estimated_duration_seconds") or 0) for item in scenes[: index - 1])
            end_seconds = start_seconds + duration_seconds
            item = QListWidgetItem()
            widget = SceneRow(
                index,
                scene.get("purpose") or scene["scene_id"],
                scene.get("narration_text") or scene.get("visual_summary") or "",
                f"{self._format_time(start_seconds)} – {self._format_time(end_seconds)}",
                f"{duration_seconds:.0f}s",
                selected=index == 1,
            )
            item.setSizeHint(widget.sizeHint())
            self.scene_list.addItem(item)
            self.scene_list.setItemWidget(item, widget)
            self.visual_scene_list.addItem(
                f"{index:02d}  {scene.get('purpose') or scene['scene_id']}"
            )
            self.visual_scene_list.item(index - 1).setData(
                Qt.ItemDataRole.UserRole,
                scene["scene_id"],
            )
        self.saved_badge.setText("Đã tải")

    def set_media_project_ready(self, ready: bool) -> None:
        for button in (
            self.queue_music_button,
            self.queue_video_button,
            self.run_queue_button,
            self.recover_queue_button,
            self.prepare_publish_button,
        ):
            button.setEnabled(ready)
        if not ready:
            self.music_status.setText("Chưa mở project · chưa nhập nhạc")
            self.video_status.setText("Chưa mở project · chưa nhập video")
            self.media_queue_status.setText("Chưa mở project · concurrency=1")

    def set_media_queue_rows(self, rows: list[dict]) -> None:
        import json

        self.media_queue_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            result = row.get("result") or ""
            if isinstance(result, dict):
                result = result.get("path") or json.dumps(result, ensure_ascii=False)
            values = (
                str(row.get("job_id") or ""),
                str(row.get("action") or ""),
                str(row.get("status") or ""),
                str(row.get("attempts") or 0),
                str(result),
                str(row.get("error") or ""),
            )
            for column, value in enumerate(values):
                self.media_queue_table.setItem(
                    row_index, column, QTableWidgetItem(value)
                )
        pending = sum(1 for row in rows if row.get("status") == "pending")
        running = sum(1 for row in rows if row.get("status") == "running")
        self.media_queue_status.setText(
            f"{len(rows)} job · pending={pending} · running={running} · concurrency=1"
        )

    def _toggle_advanced_tabs(self) -> None:
        if hasattr(self, "advanced_nav_container"):
            visible = not self.advanced_nav_container.isVisible()
            self.advanced_nav_container.setVisible(visible)
            if hasattr(self, "toggle_advanced_button"):
                self.toggle_advanced_button.setText("▾ Thu gọn tab mở rộng" if visible else "▸ Tab mở rộng (Phóng sự)")

    def show_page(self, name: str) -> None:
        page = self.pages.get(name)
        if page is not None:
            self.page_stack.setCurrentWidget(page)
        for key, button in self.nav_buttons.items():
            button.set_active(key == name)
        # If showing an advanced page, expand container automatically
        if getattr(self, "advanced_nav_keys", None) and name in self.advanced_nav_keys:
            if hasattr(self, "advanced_nav_container") and not self.advanced_nav_container.isVisible():
                self.advanced_nav_container.setVisible(True)
                if hasattr(self, "toggle_advanced_button"):
                    self.toggle_advanced_button.setText("▾ Thu gọn tab mở rộng")

    def selected_visual_scene_id(self) -> str | None:
        item = self.visual_scene_list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def set_quiz_document(self, quiz: dict) -> None:
        questions = list(quiz.get("questions") or [])
        self.quiz_question_table.setRowCount(len(questions))
        is_v2 = bool(quiz.get("engine_v2"))
        style = quiz.get("visual_style") if isinstance(quiz.get("visual_style"), dict) else {}
        style_id = str(style.get("id") or "")
        motion = str(style.get("motion") or "medium")
        self.quiz_style_combo.blockSignals(True)
        self.quiz_motion_combo.blockSignals(True)
        self.quiz_style_combo.setCurrentIndex(max(0, self.quiz_style_combo.findData(style_id)))
        self.quiz_motion_combo.setCurrentIndex(max(0, self.quiz_motion_combo.findData(motion)))
        self.quiz_style_combo.blockSignals(False)
        self.quiz_motion_combo.blockSignals(False)
        for row, question in enumerate(questions):
            choices = {str(item.get("id")): str(item.get("text") or "") for item in question.get("choices") or []}
            cards = {str(item.get("id")): str(item.get("label") or "") for item in question.get("cards") or []}
            sources = question.get("fact_sources") or []
            first_source = sources[0] if sources else ""
            source_url = str(first_source.get("url") or "") if isinstance(first_source, dict) else str(first_source)
            if not source_url and "cards" in question:
                source_url = "QuizMystra 4-Cards"
            elif not source_url and "scene_image" in question:
                source_url = "Visual Riddle"
            elif not source_url and "boxes" in question:
                source_url = "Mystery Box"

            opt_a = choices.get("A", "") or cards.get("1", "") or choices.get("1", "")
            opt_b = choices.get("B", "") or cards.get("2", "") or choices.get("2", "")
            opt_c = choices.get("C", "") or cards.get("3", "") or choices.get("3", "")
            correct_val = str(question.get("correct_choice_id") or question.get("correct_option") or question.get("correct_id") or "")

            values = (
                str(question.get("order") or row + 1),
                str(question.get("question") or ""),
                opt_a,
                opt_b,
                opt_c,
                correct_val,
                source_url,
                str(question.get("approval_status") or "draft"),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if is_v2 or column in {0, 7}:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.quiz_question_table.setItem(row, column, item)
        approval = quiz.get("approval") or {}
        fingerprint = str(approval.get("content_fingerprint") or "")

        if is_v2:
            from app.services.quiz_v2_runtime import require_review
            self.quiz_channel_combo.setCurrentIndex(max(0, self.quiz_channel_combo.findData(quiz.get("channel_profile", ""))))
            try:
                require_review(quiz)
                reviewed = True
            except (ValueError, OSError):
                reviewed = False
            settings = quiz.get("settings") or {}
            voice = settings.get("piper_voice") or ("en_US-ryan-high" if quiz.get("language") == "en" else "manh_dung")
            if self.quiz_voice_combo.findText(voice) < 0:
                self.quiz_voice_combo.addItem(voice)
            self.quiz_voice_combo.setCurrentText(voice)
            self.quiz_speed_spin.setValue(float(settings.get("piper_speed", 1.05)))
            self.render_quiz_button.setEnabled(reviewed)
            self.render_quiz_button.setText(f"Render bản đã duyệt ({len(questions)} câu)")
            self.approve_quiz_button.setText("Xem ảnh & duyệt nội dung")
            self.approve_quiz_button.setEnabled(True)
            self.quiz_approval_fingerprint.setText("Đã duyệt đúng nội dung/ảnh" if reviewed else "Chưa duyệt ảnh/manh mối; sửa nội dung bằng Dán JSON")
            self.quiz_status.setText(f"Đã nạp {len(questions)} câu · " + ("đã duyệt" if reviewed else "bản nháp, chưa sẵn sàng render"))
        else:
            render_approved = (
                len(questions) in {5, 30}
                and approval.get("status") == "approved"
                and len(fingerprint) == 64
            )
            self.render_quiz_button.setEnabled(render_approved)
            if len(questions) == 30:
                if self.quiz_review_card.title_label is not None:
                    self.quiz_review_card.title_label.setText("QUIZ MODE · BẢN 30 CÂU")
                self.approve_quiz_button.setText("Duyệt 30 câu")
                self.render_quiz_button.setText("Render bản 30 câu")
                self.quiz_output_dir.setText("output/quiz-30")
            else:
                if self.quiz_review_card.title_label is not None:
                    self.quiz_review_card.title_label.setText("QUIZ MODE · PILOT 5 CÂU")
                self.approve_quiz_button.setText("Duyệt 5 câu")
                self.render_quiz_button.setText("Render pilot 5 câu")
                self.quiz_output_dir.setText("output/quiz-pilot-5")
            self.quiz_approval_fingerprint.setText(
                f"Fingerprint: {fingerprint}" if fingerprint else "Chưa duyệt"
            )
            self.quiz_status.setText(f"Đã nạp {len(questions)} câu · Phase 2 review")

        if questions:
            self.quiz_question_table.setCurrentCell(0, 0)
            self.set_quiz_preview(questions[0], total=len(questions))

    def confirm_quiz_visual_review(self, quiz: dict) -> bool:
        from PySide6.QtWidgets import QDialog, QDialogButtonBox
        import json
        dialog = QDialog(self)
        dialog.setWindowTitle("Review nội dung & ảnh thật — không phải AI tự duyệt")
        dialog.resize(980, 800)
        layout = QVBoxLayout(dialog)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        items = QVBoxLayout(body)
        warning = QLabel("Chỉ duyệt nếu ảnh có đúng nhân vật/manh mối, đáp án duy nhất và lời giải hợp lý. Tóc khô hoặc thèm ăn không tự chứng minh nói dối/mang thai.")
        warning.setWordWrap(True)
        items.addWidget(warning)
        for question in quiz.get("questions", []):
            text = QLabel(json.dumps(question, ensure_ascii=False, indent=2))
            text.setTextFormat(Qt.TextFormat.PlainText)
            text.setWordWrap(True)
            items.addWidget(text)
            paths = [c.get("image_path") for c in question.get("cards", [])]
            paths += [question.get("scene_image"), question.get("reveal_image_path")]
            for path in filter(None, paths):
                image = QLabel()
                image.setPixmap(QPixmap(path).scaled(860, 520, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                items.addWidget(image)
        scroll.setWidget(body)
        layout.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Tôi đã xem ảnh và xác nhận nội dung")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        return dialog.exec() == QDialog.DialogCode.Accepted

    def _open_channel_analytics(self):
        import json
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from app.services.quiz_channel_analytics import read_metrics, summarize
        path, _ = QFileDialog.getOpenFileName(self, "Analytics CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            rows = read_metrics(path)
            key = self.quiz_channel_combo.currentData()
            if key:
                rows = [row for row in rows if row.get("channel_profile") == key]
            QMessageBox.information(self, "Channel analytics", json.dumps(summarize(rows), ensure_ascii=False, indent=2))
        except Exception as exc:
            QMessageBox.warning(self, "Analytics", str(exc))

    def read_quiz_review(self, quiz: dict) -> dict:
        from copy import deepcopy

        edited = deepcopy(quiz)
        if edited.get("engine_v2"):
            key = self.quiz_channel_combo.currentData() or ""
            if key and key != edited.get("channel_profile"):
                from app.services.quiz_channel_profiles import bind_profile
                edited = bind_profile(edited, key)
            elif not key and edited.get("channel_profile"):
                edited.pop("channel_profile", None)
                edited.pop("channel_profile_version", None)
                edited["language"] = "auto"
                edited["approval"] = {"status": "draft"}
            edited.setdefault("settings", {}).update({
                "tts_engine": "piper", "piper_voice": self.quiz_voice_combo.currentText(),
                "piper_speed": self.quiz_speed_spin.value(),
            })
            if edited.get("channel_profile"):
                from app.services.quiz_channel_profiles import review_content
                edited["editorial_qa"] = review_content(edited)
            return edited
        changed = False
        for row, question in enumerate(edited.get("questions") or []):
            before = deepcopy(question)
            question["question"] = self.quiz_question_table.item(row, 1).text().strip()
            choices = question.get("choices") or []
            for column, choice_id in ((2, "A"), (3, "B"), (4, "C")):
                match = next((item for item in choices if str(item.get("id")) == choice_id), None)
                if match is not None:
                    match["text"] = self.quiz_question_table.item(row, column).text().strip()
            correct_id = self.quiz_question_table.item(row, 5).text().strip().upper()
            question["correct_choice_id"] = correct_id
            correct = next((item for item in choices if str(item.get("id")) == correct_id), None)
            if correct is not None:
                question["answer_text"] = str(correct.get("text") or "")
                question["answer_voice"] = f"Đáp án là {question['answer_text']}."
            source_url = self.quiz_question_table.item(row, 6).text().strip()
            sources = question.get("fact_sources") or []
            if sources and isinstance(sources[0], dict):
                sources[0]["url"] = source_url
            else:
                question["fact_sources"] = [source_url]
            changed = changed or question != before
        if changed:
            edited["approval"] = {"status": "draft", "approved_at": None, "content_fingerprint": None}
            for question in edited.get("questions") or []:
                question["approval_status"] = "draft"
                question["content_fingerprint"] = None
                question.setdefault("ledger", {})["approval_status"] = "pending"
        return edited

    def set_quiz_preview(self, question: dict, *, total: int | None = None) -> None:
        ord_num = question.get('order') if question.get('order') is not None else 1
        if "cards" in question:
            cards_lines = "\n".join(f"Card {c.get('id')}: {c.get('label')}" for c in question.get("cards") or [])
            self.quiz_preview.setPlainText(
                f"Câu {ord_num}/{total or self.quiz_question_table.rowCount()} [QuizMystra 4-Cards]\n\n"
                f"{question.get('question')}\n\n"
                f"{cards_lines}\n\n"
                f"Đáp án: Card {question.get('correct_option') or question.get('correct_id')}\n"
                f"{question.get('explanation_text') or ''}"
            )
        elif "scene_image" in question:
            self.quiz_preview.setPlainText(
                f"Câu {ord_num}/{total or self.quiz_question_table.rowCount()} [Visual Logic Riddle]\n\n"
                f"{question.get('question')}\n\n"
                f"Bối cảnh tranh: {question.get('scene_image')}\n"
                f"Lựa chọn: {', '.join(str(o) for o in question.get('options') or [])}\n\n"
                f"Đáp án đúng: {question.get('correct_option')}\n"
                f"{question.get('explanation_text') or ''}"
            )
        else:
            choices = "\n".join(
                f"{item.get('id')}. {item.get('text')}"
                for item in question.get("choices") or []
            )
            self.quiz_preview.setPlainText(
                f"Câu {ord_num}/{total or self.quiz_question_table.rowCount()}\n\n"
                f"{question.get('question')}\n\n"
                f"{choices}\n\nĐáp án: {question.get('correct_choice_id')} — "
                f"{question.get('answer_text')}"
            )

    def set_quiz_style_preview(self, payload: dict) -> None:
        path = str(payload.get("path") or "")
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.set_quiz_style_preview_error(f"Không đọc được preview: {path}")
            return
        self.quiz_preview_image.setText("")
        self.quiz_preview_image.setPixmap(
            pixmap.scaled(
                self.quiz_preview_image.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.quiz_preview_image.setProperty("preview_status", "ready")
        self.quiz_style_preview_status.setText(
            f"Preview ready · style={payload.get('style_id', 'baseline')} · "
            f"motion={payload.get('motion', 'medium')} · {payload.get('aspect')} · {payload.get('state')} · "
            f"provider={payload.get('provider_calls', 0)} · TTS={payload.get('tts_calls', 0)}"
        )

    def set_quiz_style_preview_error(self, message: str) -> None:
        self.quiz_preview_image.setPixmap(QPixmap())
        self.quiz_preview_image.setText("Preview lỗi · chưa có ảnh hiện hành")
        self.quiz_preview_image.setProperty("preview_status", "error")
        self.quiz_style_preview_status.setText(f"Preview lỗi: {message}")

    def restore_quiz_style_controls(self, quiz: dict) -> None:
        style = quiz.get("visual_style") if isinstance(quiz.get("visual_style"), dict) else {}
        self.quiz_style_combo.blockSignals(True)
        self.quiz_motion_combo.blockSignals(True)
        self.quiz_style_combo.setCurrentIndex(max(0, self.quiz_style_combo.findData(str(style.get("id") or ""))))
        self.quiz_motion_combo.setCurrentIndex(max(0, self.quiz_motion_combo.findData(str(style.get("motion") or "medium"))))
        self.quiz_style_combo.blockSignals(False)
        self.quiz_motion_combo.blockSignals(False)
        self.quiz_style_preview_status.setText("Đã hủy thay đổi style chưa lưu")

    def set_quiz_render_result(self, payload: dict) -> None:
        self.quiz_progress.setValue(100)
        self.quiz_status.setText(
            f"Render hoàn tất · provider calls={payload.get('provider_calls', 0)} · TTS calls={payload.get('tts_calls', 0)} · cache hits={payload.get('tts_cache_hits', 0)}"
        )
        self.quiz_artifact_path.setText(str(payload.get("final_mp4") or ""))

    def set_visual_scene(self, scene: dict, assets: list[dict]) -> None:
        self.visual_prompt_editor.setPlainText(scene.get("image_prompt") or "")
        self.generated_asset_list.clear()
        for asset in assets:
            self.generated_asset_list.addItem(
                f"{asset.get('role')} · v{asset.get('version', 1):03d} · {asset.get('provider')}"
            )
            self.generated_asset_list.item(self.generated_asset_list.count() - 1).setData(
                Qt.ItemDataRole.UserRole,
                asset,
            )
        if assets:
            selected_index = next(
                (index for index, asset in enumerate(assets) if asset.get("selected")),
                0,
            )
            self.generated_asset_list.setCurrentRow(selected_index)
            self.set_image_preview(assets[selected_index].get("path") or "")
        else:
            self.image_preview.setPixmap(QPixmap())
            self.image_preview.setText("Chưa có ảnh được tạo")

    def set_image_preview(self, path: str) -> bool:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.image_preview.setPixmap(QPixmap())
            self.image_preview.setText("Không đọc được ảnh")
            return False
        self.image_preview.setText("")
        self.image_preview.setPixmap(
            pixmap.scaled(
                self.image_preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        return not self.image_preview.pixmap().isNull()

    def append_activity_log(self, friendly: str, technical: str = "") -> None:
        if friendly:
            self.friendly_log.append(friendly)
        if technical:
            self.technical_log.append(technical)

    def clear_activity_logs(self) -> None:
        self.friendly_log.clear()
        self.technical_log.clear()

    def set_provider_status(self, text: str, *, ok: bool = False) -> None:
        self.provider_status.setText(text)
        self.provider_status.setObjectName("StatusSuccess" if ok else "ProviderStatus")
        self.provider_status.style().unpolish(self.provider_status)
        self.provider_status.style().polish(self.provider_status)

    def set_style_content(self, project: dict, style: dict) -> None:
        preset = str(
            style.get("preset")
            or project.get("style_preset")
            or "editorial_collage"
        )
        matches = self.style_preset_list.findItems(
            preset,
            Qt.MatchFlag.MatchExactly,
        )
        if matches:
            self.style_preset_list.setCurrentItem(matches[0])
        self.style_visual_language.setText(str(style.get("visual_language") or ""))
        self.style_palette.setText(", ".join(style.get("palette") or []))
        self.style_texture.setText(", ".join(style.get("texture") or []))
        revision = style.get("style_revision") or style.get("revision")
        visual_hash = style.get("visual_hash") or style.get("draft_hash") or ""
        motion_hash = style.get("motion_hash") or ""
        theme_hash = style.get("render_theme_hash") or ""
        self.style_preview.setText(
            f"{preset}\n{self.style_visual_language.text()}\n{self.style_palette.text()}"
            f"\nrevision={revision or '-'} · visual={str(visual_hash)[:12] or '-'}"
            f"\nmotion={str(motion_hash)[:12] or '-'} · theme={str(theme_hash)[:12] or '-'}"
        )
        freshness = style.get("freshness") or {}
        self.style_freshness_summary.setText(
            " · ".join(
                f"{key}={int(freshness.get(key, 0) or 0)}"
                for key in ("fresh", "stale", "unknown", "missing")
            )
        )

    def set_style_regeneration_budget(self, *, scene_count: int, role_count: int) -> None:
        calls = max(0, int(scene_count)) * max(0, int(role_count))
        self.regenerate_all_style_images_button.setText(
            f"Tạo lại tất cả ảnh · {calls} provider calls"
        )
        self.regenerate_all_style_images_button.setToolTip(
            "Chạy tuần tự; ảnh đã fresh sẽ được cache/skip. "
            f"Ngân sách tối đa hiện tại: {calls} provider calls."
        )

    @staticmethod
    def style_regeneration_confirmation_text(*, scene_count: int, role_count: int) -> str:
        calls = max(0, int(scene_count)) * max(0, int(role_count))
        return (
            f"Tạo lại tối đa {scene_count} scene × {role_count} role = "
            f"{calls} provider calls. Tác vụ chạy tuần tự, cache-hit sẽ được bỏ qua."
        )

    def set_style_regeneration_running(
        self,
        running: bool,
        *,
        current: int = 0,
        total: int = 0,
    ) -> None:
        self.regenerate_style_scene_button.setEnabled(not running)
        self.regenerate_all_style_images_button.setEnabled(not running)
        if running:
            self.regenerate_all_style_images_button.setText(
                f"Đang tạo lại ảnh · {current}/{total}"
            )
        else:
            scene_count = len(getattr(self, "_visual_scenes", []) or [])
            self.set_style_regeneration_budget(scene_count=scene_count, role_count=5)

    def set_voice_results(self, results: list[dict], narration_path: str = "") -> None:
        self.voice_result_list.clear()
        for result in results:
            self.voice_result_list.addItem(
                f"{result.get('scene_id')} · {result.get('duration_ms', 0)} ms · "
                f"{'cache' if result.get('cached') else 'generated'}"
            )
        if narration_path:
            self.voice_result_list.addItem(f"Narration: {narration_path}")

    def set_caption_entries(self, entries: list[dict]) -> None:
        self.caption_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = (
                str(entry.get("index", row + 1)),
                str(entry.get("start", "")),
                str(entry.get("end", "")),
                str(entry.get("text", "")),
            )
            for column, value in enumerate(values):
                self.caption_table.setItem(row, column, QTableWidgetItem(value))

    def set_render_state(
        self,
        *,
        progress: int | None = None,
        prerequisites: str | None = None,
        artifact: str | None = None,
    ) -> None:
        if progress is not None:
            self.render_progress.setValue(max(0, min(100, progress)))
        if prerequisites is not None:
            self.render_prerequisites.setText(prerequisites)
        if artifact is not None:
            self.final_artifact_path.setText(artifact)

    def clear_project_content(self) -> None:
        """Clear every project-owned widget so stale lineage is never shown."""
        self.topic_input.clear()
        self.script_editor.clear()
        self.scene_list.clear()
        self.visual_scene_list.clear()
        self.generated_asset_list.clear()
        self.visual_prompt_editor.clear()
        self._visual_scenes = []
        self.image_preview.setPixmap(QPixmap())
        self.image_preview.setText("Chưa có ảnh được tạo")
        self.voice_result_list.clear()
        self.caption_table.setRowCount(0)
        self.render_progress.setValue(0)
        self.render_prerequisites.setText(
            "Mở project để kiểm tra voice, selected image, motion, scenes và final artifact."
        )
        self.final_artifact_path.setText("Chưa có final.mp4")
        self.saved_badge.setText("Chưa tải project")
        self.overview_project_state.setText(
            "Chưa chọn dự án · Chọn hoặc tạo dự án để bắt đầu"
        )

    @staticmethod
    def _format_time(seconds: float) -> str:
        whole = max(0, int(round(seconds)))
        return f"{whole // 60:02d}:{whole % 60:02d}"

    def statusBar(self) -> QStatusBar:  # type: ignore[override]
        return super().statusBar()

    @property
    def global_status_bar(self) -> QStatusBar:
        return self.statusBar()
