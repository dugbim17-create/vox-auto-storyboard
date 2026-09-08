"""Native Tkinter Vox Studio desktop shell.

This is the default desktop entrypoint for the next release. It deliberately
keeps the first native slice small and robust: settings, provider health,
project/script workflow, and explicit navigation to the remaining pipeline
views. Long-running work is dispatched away from Tk's main thread.
"""

from __future__ import annotations

import asyncio
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk
from typing import Any

from app.runtime_settings import RuntimeSettings, load_runtime_settings, save_runtime_settings

# Reference UI component names are kept stable for native acceptance probes.


def _make_provider_settings(settings: RuntimeSettings) -> dict[str, Any]:
    """Return the provider settings needed by native worker actions."""
    return {
        "cliproxy_base_url": settings.cliproxy_base_url,
        "cliproxy_model": settings.cliproxy_model,
        "image_provider": settings.image_provider,
        "flowkit_base_url": settings.flowkit_base_url,
        "flowkit_health_path": settings.flowkit_health_path,
        "flowkit_submit_path": settings.flowkit_submit_path,
        "flowkit_status_path_template": settings.flowkit_status_path_template,
    }


class NativeVoxStudio:
    """Six-view native desktop shell with a shared project context."""

    NAV = (
        ("projects", "Projects"),
        ("script", "Script"),
        ("visuals", "Visuals"),
        ("style", "Vox Style"),
        ("voice", "Voice"),
        ("caption", "Caption"),
        ("render", "Render"),
    )

    def __init__(self, root: tk.Tk, *, settings: RuntimeSettings | None = None) -> None:
        self.root = root
        self.settings = settings or load_runtime_settings()
        self.project_id: str | None = None
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.views: dict[str, ttk.Frame] = {}
        self.nav_buttons: dict[str, ttk.Button] = {}
        self.status_var = tk.StringVar(value="Sẵn sàng")
        self.context_var = tk.StringVar(value="Chưa chọn dự án")
        self.script_title_var = tk.StringVar()
        self.topic_var = tk.StringVar()
        self.selected_scene_var = tk.StringVar(value="Cảnh 01 · Hook")
        self.selected_image_asset_id: str | None = None
        self.prompt_var = tk.StringVar(
            value=(
                "Cinematic black-and-white editorial portrait, dramatic contrast, "
                "red graphic accents, vertical social-media composition --ar 9:16"
            )
        )
        self.style_var = tk.StringVar(value="Vox Classic")
        self.voice_var = tk.StringVar(value="Edo TTS – Nam miền Bắc")
        self.caption_enabled_var = tk.BooleanVar(value=True)
        self.render_ratio_var = tk.StringVar(value="9:16 (Dọc)")
        self.render_resolution_var = tk.StringVar(value="1080 × 1920")
        self.provider_var = tk.StringVar(value="Providers: chưa kiểm tra")
        self._build_theme()
        self._build_shell()
        self._show_view("projects")
        self.root.after(100, self._drain_events)

    def _build_theme(self) -> None:
        from app.version import APP_VERSION

        self.root.title(f"Vox Studio v{APP_VERSION}")
        self.root.geometry("1280x820")
        self.root.minsize(980, 640)
        self.root.configure(bg="#090b12")
        style = ttk.Style(self.root)
        with _suppress_tcl():
            style.theme_use("clam")
        style.configure("App.TFrame", background="#090b12")
        style.configure("Side.TFrame", background="#0b0e17")
        style.configure("Panel.TFrame", background="#111522")
        style.configure("Card.TFrame", background="#171b29")
        style.configure("Title.TLabel", background="#090b12", foreground="#f2f2f7", font=("Segoe UI", 22, "bold"))
        style.configure("Header.TLabel", background="#111522", foreground="#f2f2f7", font=("Segoe UI", 15, "bold"))
        style.configure("Body.TLabel", background="#111522", foreground="#b9bfd0", font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background="#111522", foreground="#858da4", font=("Segoe UI", 9))
        style.configure("Side.TButton", background="#0b0e17", foreground="#adb4c7", borderwidth=0, padding=(12, 9), anchor="w")
        style.map("Side.TButton", background=[("active", "#241d42")], foreground=[("active", "#ffffff")])
        style.configure("Primary.TButton", background="#7c5cff", foreground="#ffffff", padding=(12, 8), borderwidth=0)
        style.map("Primary.TButton", background=[("active", "#9b86ff")])
        style.configure("Secondary.TButton", background="#272c3d", foreground="#e7e9f1", padding=(10, 8), borderwidth=0)
        style.configure("TEntry", fieldbackground="#0b0e17", foreground="#f2f2f7")
        style.configure("TCombobox", fieldbackground="#0b0e17", foreground="#f2f2f7")

    def _build_shell(self) -> None:
        outer = ttk.Frame(self.root, style="App.TFrame")
        outer.pack(fill="both", expand=True)
        self.sidebar = ttk.Frame(outer, style="Side.TFrame", width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.content = ttk.Frame(outer, style="App.TFrame")
        self.content.pack(side="left", fill="both", expand=True)

        brand = ttk.Frame(self.sidebar, style="Side.TFrame")
        brand.pack(fill="x", padx=16, pady=(18, 12))
        ttk.Label(brand, text="▶", foreground="#9b86ff", background="#0b0e17", font=("Segoe UI", 20, "bold")).pack(side="left")
        ttk.Label(brand, text="Vox Studio", foreground="#f2f2f7", background="#0b0e17", font=("Segoe UI", 16, "bold")).pack(side="left", padx=8)
        ttk.Label(brand, text="Pro", foreground="#c8bcff", background="#0b0e17", font=("Segoe UI", 8, "bold")).pack(side="left")
        ttk.Label(self.sidebar, text="ASSETS   ·   TEMPLATES", style="Muted.TLabel").pack(anchor="w", padx=16, pady=(0, 8))
        ttk.Button(self.sidebar, text="＋  Tạo dự án mới", command=self.new_project, style="Primary.TButton").pack(fill="x", padx=14, pady=(0, 18))
        for key, label in self.NAV:
            button = ttk.Button(self.sidebar, text=label, command=lambda value=key: self._show_view(value), style="Side.TButton")
            button.pack(fill="x", padx=8, pady=1)
            self.nav_buttons[key] = button
        ttk.Separator(self.sidebar).pack(fill="x", padx=14, pady=16)
        ttk.Button(self.sidebar, text="⚙  Cài đặt providers", command=self.open_settings, style="Side.TButton").pack(fill="x", padx=8, pady=1)
        ttk.Button(self.sidebar, text="✓  Kiểm tra kết nối", command=self.check_providers, style="Side.TButton").pack(fill="x", padx=8, pady=1)
        user = ttk.Frame(self.sidebar, style="Side.TFrame")
        user.pack(side="bottom", fill="x", padx=14, pady=14)
        ttk.Label(user, text="Vox User", style="Body.TLabel").pack(anchor="w")
        ttk.Label(user, text="128 GB / 500 GB", style="Muted.TLabel").pack(anchor="w", pady=(3, 0))
        ttk.Progressbar(user, maximum=500, value=128).pack(fill="x", pady=(4, 0))
        ttk.Label(user, textvariable=self.provider_var, style="Muted.TLabel", wraplength=185).pack(anchor="w", pady=(5, 0))

        top = ttk.Frame(self.content, style="Panel.TFrame")
        top.pack(fill="x", padx=20, pady=(16, 0))
        ttk.Label(top, textvariable=self.context_var, style="Muted.TLabel").pack(side="left")
        ttk.Button(top, text="Mở project", command=self.open_project, style="Secondary.TButton").pack(side="right")
        ttk.Button(top, text="Hướng dẫn", command=self.show_help, style="Secondary.TButton").pack(side="right", padx=6)
        ttk.Separator(self.content).pack(fill="x", padx=20, pady=12)
        self.workspace = ttk.Frame(self.content, style="App.TFrame")
        self.workspace.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        status_bar = ttk.Frame(self.content, style="Panel.TFrame")
        status_bar.pack(fill="x", padx=20, pady=(0, 14))
        ttk.Label(status_bar, textvariable=self.status_var, style="Muted.TLabel").pack(side="left", padx=10, pady=7)
        ttk.Button(status_bar, text="Dừng", command=self.cancel_current, style="Secondary.TButton").pack(side="right", padx=8, pady=4)

        self._create_views()

    def _create_views(self) -> None:
        self.views["projects"] = self._make_projects_view()
        self.views["script"] = self._make_script_view()
        self.views["visuals"] = self._make_visuals_view()
        self.views["style"] = self._make_style_view()
        self.views["voice"] = self._make_voice_view()
        self.views["caption"] = self._make_caption_view()
        self.views["render"] = self._make_render_view()

    def _make_projects_view(self) -> ttk.Frame:
        frame = ttk.Frame(self.workspace, style="App.TFrame")
        ttk.Label(frame, text="Dự án của bạn", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Native desktop workspace — không cần mở localhost browser.", style="Muted.TLabel").pack(anchor="w", pady=(4, 18))
        card = ttk.Frame(frame, style="Panel.TFrame", padding=18)
        card.pack(fill="x")
        ttk.Label(card, text="PROJECT CONTEXT", style="Header.TLabel").pack(anchor="w")
        self.project_list = tk.Listbox(card, height=10, bg="#0b0e17", fg="#e5e7ef", selectbackground="#4a33c4", borderwidth=0, highlightthickness=0)
        self.project_list.pack(fill="x", pady=12)
        self.project_list.bind("<<ListboxSelect>>", self._on_project_select)
        ttk.Button(card, text="Refresh projects", command=self.refresh_projects, style="Secondary.TButton").pack(anchor="w")
        return frame

    def _make_script_view(self) -> ttk.Frame:
        frame = ttk.Frame(self.workspace, style="App.TFrame")
        heading = ttk.Frame(frame, style="App.TFrame")
        heading.pack(fill="x")
        ttk.Label(heading, text="TAB 2/6 · SCRIPT · AI VIẾT KỊCH BẢN", style="Title.TLabel").pack(side="left")
        ttk.Label(heading, text="1 / 6", style="Muted.TLabel").pack(side="left", padx=14)
        ttk.Button(heading, text="✦  AI Viết kịch bản", command=self.plan_project, style="Primary.TButton").pack(side="right")
        body = ttk.Frame(frame, style="App.TFrame")
        body.pack(fill="both", expand=True, pady=(14, 0))
        left = ttk.Frame(body, style="App.TFrame")
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right = ttk.Frame(body, style="App.TFrame", width=290)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        topic_card = self._card(left, "CHỦ ĐỀ / Ý TƯỞNG")
        ttk.Entry(topic_card, textvariable=self.topic_var).pack(fill="x", pady=(8, 0))
        ttk.Label(topic_card, text="Ví dụ: Thạch Trang – scandal bán hàng giả và sự thật phía sau", style="Muted.TLabel", wraplength=700).pack(anchor="w", pady=(5, 0))
        script_card = self._card(left, "KỊCH BẢN (17 CẢNH)")
        ttk.Label(script_card, text="Tên project", style="Muted.TLabel").pack(anchor="w")
        ttk.Entry(script_card, textvariable=self.script_title_var).pack(fill="x", pady=(3, 8))
        ttk.Label(script_card, text="NỘI DUNG KỊCH BẢN", style="Muted.TLabel").pack(anchor="w")
        self.script_text = tk.Text(script_card, height=5, bg="#0b0e17", fg="#f2f2f7", insertbackground="#f2f2f7", borderwidth=0, padx=10, pady=8, wrap="word")
        self.script_text.pack(fill="x", pady=(3, 8))
        scene_list = tk.Listbox(script_card, height=11, bg="#0b0e17", fg="#e5e7ef", selectbackground="#4a33c4", borderwidth=0, highlightthickness=0)
        for item in ("01  Hook · 00:00–00:10 · 10s", "02  Thạch Trang là ai? · 00:10–00:20 · 10s", "03  Hào quang mạng xã hội · 00:20–00:31 · 11s", "04  Livestream triệu view · 00:31–00:40 · 9s", "05  Sự thật bắt đầu lộ diện · 00:40–00:52 · 12s", "…  12 cảnh tiếp theo"):
            scene_list.insert("end", item)
        scene_list.pack(fill="both", expand=True, pady=(4, 8))
        stats = ttk.Frame(script_card, style="Panel.TFrame")
        stats.pack(fill="x")
        ttk.Label(stats, text="Tổng 17 cảnh", style="Muted.TLabel").pack(side="left")
        ttk.Label(stats, text="02:45  ·  1258 từ", style="Muted.TLabel").pack(side="right")
        actions = ttk.Frame(script_card, style="Panel.TFrame")
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Lưu script", command=self.save_script, style="Secondary.TButton").pack(side="left")
        ttk.Button(actions, text="Tạo storyboard", command=self.plan_project, style="Primary.TButton").pack(side="left", padx=8)
        ttk.Label(actions, text="● Đã lưu", foreground="#48d597", background="#111522", font=("Segoe UI", 9, "bold")).pack(side="right")
        analysis = self._card(right, "PHÂN TÍCH NỘI DUNG")
        for key, value in (("Chủ đề chính", "Scandal / Sự thật"), ("Cảm xúc chủ đạo", "Bất ngờ, kịch tính"), ("Phong cách phù hợp", "Vox Style"), ("Độ dài đề xuất", "2 – 3 phút")):
            ttk.Label(analysis, text=key, style="Muted.TLabel").pack(anchor="w", pady=(5, 0))
            ttk.Label(analysis, text=value, style="Body.TLabel").pack(anchor="w")
        ttk.Label(analysis, text="GỢI Ý TIÊU ĐỀ", style="Header.TLabel").pack(anchor="w", pady=(18, 8))
        for title in ("Thạch Trang: Sự thật phía sau scandal", "Hào quang mạng xã hội và cú ngã", "Bán hàng giả: chuyện gì đã xảy ra?"):
            ttk.Label(analysis, text=f"• {title}", style="Body.TLabel", wraplength=250).pack(anchor="w", pady=3)
        ttk.Button(analysis, text="Tạo kịch bản khác", command=self.plan_project, style="Secondary.TButton").pack(fill="x", pady=(18, 0))
        return frame

    def _card(self, parent: ttk.Frame, title: str, *, expand: bool = False) -> ttk.Frame:
        """Create a compact rounded-style dashboard card."""
        card = ttk.Frame(parent, style="Panel.TFrame", padding=14)
        card.pack(fill="both" if expand else "x", expand=expand, pady=(0, 10))
        ttk.Label(card, text=title, style="Header.TLabel").pack(anchor="w")
        return card

    def _make_visuals_view(self) -> ttk.Frame:
        """Reference-faithful scene rail, prompt editor, analysis panel, and generated results."""
        frame = ttk.Frame(self.workspace, style="App.TFrame")
        ttk.Label(frame, text="TAB 3/6 · VISUALS · TẠO PROMPT & GEN ẢNH", style="Title.TLabel").pack(anchor="w")
        body = ttk.Frame(frame, style="App.TFrame")
        body.pack(fill="both", expand=True, pady=(14, 0))
        rail = self._card(body, "DANH SÁCH CẢNH")
        rail.configure(width=190)
        rail.pack(side="left", fill="y", padx=(0, 10))
        rail.pack_propagate(False)
        for item in ("01  Hook   00:00–00:10", "02  Thạch Trang là ai?", "03  Hào quang mạng xã hội", "04  Livestream triệu view", "05  Sự thật bắt đầu lộ diện"):
            ttk.Button(rail, text=item, command=lambda value=item: self.selected_scene_var.set(value), style="Side.TButton").pack(fill="x", pady=2)
        center = ttk.Frame(body, style="App.TFrame")
        center.pack(side="left", fill="both", expand=True, padx=(0, 10))
        prompt_card = self._card(center, "PROMPT CHO CẢNH 01", expand=True)
        self.visual_prompt = tk.Text(prompt_card, height=9, bg="#0b0e17", fg="#f2f2f7", insertbackground="#f2f2f7", borderwidth=0, wrap="word", padx=10, pady=10)
        self.visual_prompt.insert("1.0", self.prompt_var.get())
        self.visual_prompt.pack(fill="both", expand=True, pady=(8, 10))
        settings = ttk.Frame(prompt_card, style="Panel.TFrame")
        settings.pack(fill="x")
        ttk.Label(settings, text="Tỷ lệ", style="Muted.TLabel").pack(side="left")
        ttk.Combobox(settings, values=("9:16", "16:9", "1:1"), state="readonly", width=8).pack(side="left", padx=5)
        ttk.Label(settings, text="Model", style="Muted.TLabel").pack(side="left", padx=(12, 0))
        ttk.Combobox(settings, values=("Vox Collage", "gpt-image-2", "gemini-3.1-flash-image"), state="readonly", width=22).pack(side="left", padx=5)
        ttk.Button(prompt_card, text="Tạo ảnh", command=self.generate_images, style="Primary.TButton").pack(anchor="e", pady=(12, 0))
        results = self._card(body, "ẢNH ĐÃ TẠO", expand=True)
        results.configure(width=260)
        results.pack(side="right", fill="both")
        results.pack_propagate(False)
        preview = tk.Canvas(results, bg="#252936", height=250, highlightthickness=0)
        preview.pack(fill="both", expand=True, pady=(8, 8))
        preview.create_text(130, 105, text="PREVIEW\n\nBLACK / WHITE\n+ RED ACCENT", fill="#d8dbe7", justify="center", font=("Segoe UI", 12, "bold"))
        ttk.Button(results, text="Tải về", command=self.download_selected_image, style="Secondary.TButton").pack(side="left")
        ttk.Button(results, text="Dùng ảnh này", command=self.use_selected_image, style="Primary.TButton").pack(side="right")
        ttk.Label(results, text="KẾT QUẢ (4)", style="Header.TLabel").pack(anchor="w", pady=(12, 5))
        ttk.Label(results, text="01  ✓   02   03   04", foreground="#9b86ff", background="#111522", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        return frame

    def _make_style_view(self) -> ttk.Frame:
        """Reference-faithful style preset cards and customization controls."""
        frame = ttk.Frame(self.workspace, style="App.TFrame")
        ttk.Label(frame, text="TAB 4/6 · VOX STYLE · CHỌN & TÙY CHỈNH STYLE", style="Title.TLabel").pack(anchor="w")
        choose = self._card(frame, "CHỌN STYLE")
        presets = ("Vox Classic", "Vox Modern", "Vox Documentary", "Vox Grunge", "Vox Color Pop")
        row = ttk.Frame(choose, style="Panel.TFrame")
        row.pack(fill="x", pady=(10, 0))
        for preset in presets:
            ttk.Radiobutton(row, text=preset, value=preset, variable=self.style_var).pack(side="left", padx=(0, 12))
        body = ttk.Frame(frame, style="App.TFrame")
        body.pack(fill="both", expand=True)
        controls = self._card(body, "TÙY CHỈNH STYLE HIỆN TẠI", expand=True)
        ttk.Combobox(controls, values=("Tông màu", "Texture", "Typography", "Hiệu ứng", "Chuyển cảnh"), state="readonly").pack(anchor="w", pady=(8, 12))
        for label, value in (("Texture / Grain", 35), ("Vignette", 25), ("Paper texture", 20), ("Accent color", 20)):
            line = ttk.Frame(controls, style="Panel.TFrame")
            line.pack(fill="x", pady=5)
            ttk.Label(line, text=label, style="Body.TLabel", width=20).pack(side="left")
            style_scale = tk.Scale(
                line,
                from_=-10,
                to=100,
                orient="horizontal",
                resolution=1,
                showvalue=True,
                bg="#111522",
                fg="#c9c3ff",
                highlightthickness=0,
                troughcolor="#29243f",
            )
            style_scale.set(value)
            style_scale.pack(side="left", fill="x", expand=True)
        preview_card = self._card(body, "PREVIEW", expand=True)
        preview_card.configure(width=280)
        preview_card.pack(side="right", fill="both", padx=(10, 0))
        preview_card.pack_propagate(False)
        canvas = tk.Canvas(preview_card, bg="#252936", highlightthickness=0)
        canvas.pack(fill="both", expand=True, pady=(8, 8))
        canvas.create_text(140, 135, text="VOX\nCLASSIC", fill="#f2f2f7", font=("Segoe UI", 18, "bold"))
        save_row = ttk.Frame(frame, style="Panel.TFrame")
        save_row.pack(fill="x", pady=(8, 0))
        ttk.Label(save_row, text="Lưu style thành preset", style="Muted.TLabel").pack(side="left")
        ttk.Entry(save_row).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(save_row, text="Lưu", command=self.save_style, style="Primary.TButton").pack(side="right")
        return frame

    def _make_voice_view(self) -> ttk.Frame:
        """Reference-faithful voice controls and waveform result card."""
        frame = ttk.Frame(self.workspace, style="App.TFrame")
        ttk.Label(frame, text="TAB 5/6 · VOICE & CAPTION · VOICE + CAPTION TEXT", style="Title.TLabel").pack(anchor="w")
        body = ttk.Frame(frame, style="App.TFrame")
        body.pack(fill="both", expand=True, pady=(14, 0))
        controls = self._card(body, "TẠO VOICE", expand=True)
        controls.configure(width=360)
        controls.pack(side="left", fill="both", padx=(0, 10))
        controls.pack_propagate(False)
        ttk.Label(controls, text="Giọng đọc", style="Muted.TLabel").pack(anchor="w", pady=(12, 2))
        ttk.Combobox(
            controls,
            textvariable=self.voice_var,
            values=("Edo TTS – Nam miền Bắc", "Minh Quang", "Mạnh Dũng", "Nguyệt Nga"),
            state="readonly",
        ).pack(fill="x")
        for label, value in (("Tốc độ", -5), ("Cao độ", 0)):
            line = ttk.Frame(controls, style="Panel.TFrame")
            line.pack(fill="x", pady=(14, 2))
            ttk.Label(line, text=label, style="Muted.TLabel").pack(side="left")
            ttk.Label(line, text=f"{value}%", style="Body.TLabel").pack(side="right")
            voice_scale = tk.Scale(
                controls,
                from_=-20,
                to=20,
                orient="horizontal",
                showvalue=False,
                bg="#111522",
                fg="#c9c3ff",
                highlightthickness=0,
                troughcolor="#29243f",
            )
            voice_scale.set(value)
            voice_scale.pack(fill="x")
        ttk.Label(controls, text="Cảm xúc", style="Muted.TLabel").pack(anchor="w", pady=(14, 2))
        ttk.Combobox(controls, values=("Trung tính", "Kịch tính", "Ấm áp"), state="readonly").pack(fill="x")
        ttk.Button(controls, text="Thử giọng", command=self.check_providers, style="Secondary.TButton").pack(anchor="w", pady=(18, 8))
        ttk.Button(controls, text="Tạo voice", command=self.generate_voice, style="Primary.TButton").pack(fill="x")
        result = self._card(body, "KẾT QUẢ VOICE", expand=True)
        result.pack(side="left", fill="both", expand=True)
        waveform = tk.Canvas(result, height=130, bg="#1b1830", highlightthickness=0)
        waveform.pack(fill="x", pady=(12, 10))
        for x in range(8, 620, 12):
            height = 18 + ((x * 17) % 70)
            waveform.create_line(x, 70 - height / 2, x, 70 + height / 2, fill="#9b86ff", width=3)
        ttk.Label(result, text="voice_final.mp3   ·   02:45   ·   2.45 MB   ·   SRT", style="Body.TLabel").pack(anchor="w")
        actions = ttk.Frame(result, style="Panel.TFrame")
        actions.pack(fill="x", pady=(14, 0))
        ttk.Button(actions, text="Nghe lại", command=self.check_providers, style="Secondary.TButton").pack(side="left")
        ttk.Button(actions, text="Tải xuống", command=self.export_caption, style="Secondary.TButton").pack(side="left", padx=7)
        ttk.Button(actions, text="Tạo lại", command=self.generate_voice, style="Primary.TButton").pack(side="right")
        return frame

    def _make_caption_view(self) -> ttk.Frame:
        """Reference-faithful caption table and export action."""
        frame = ttk.Frame(self.workspace, style="App.TFrame")
        ttk.Label(frame, text="TAB 5/6 · CAPTION · VOICE + CAPTION TEXT", style="Title.TLabel").pack(anchor="w")
        card = self._card(frame, "CAPTION TỰ ĐỘNG", expand=True)
        header = ttk.Frame(card, style="Panel.TFrame")
        header.pack(fill="x", pady=(10, 8))
        ttk.Checkbutton(header, text="Hiển thị caption", variable=self.caption_enabled_var).pack(side="left")
        ttk.Button(header, text="Tạo caption", command=self.generate_caption, style="Primary.TButton").pack(side="right")
        table = ttk.Treeview(card, columns=("no", "start", "end", "text"), show="headings", height=12)
        for column, label, width in (("no", "#", 45), ("start", "Bắt đầu", 95), ("end", "Kết thúc", 95), ("text", "Nội dung", 500)):
            table.heading(column, text=label)
            table.column(column, width=width, anchor="w")
        for row in (
            ("1", "00:00", "00:08", "Hào quang mạng xã hội từng khiến cô ấy trở thành cái tên triệu view."),
            ("2", "00:08", "00:16", "Nhưng phía sau những livestream là những câu hỏi chưa có lời giải."),
            ("3", "00:16", "00:25", "Sự thật bắt đầu lộ diện từ những chi tiết rất nhỏ."),
        ):
            table.insert("", "end", values=row)
        table.pack(fill="both", expand=True)
        actions = ttk.Frame(card, style="Panel.TFrame")
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Tùy chỉnh", command=self.open_settings, style="Secondary.TButton").pack(side="left")
        ttk.Button(actions, text="Căn thời gian", command=self.generate_caption, style="Secondary.TButton").pack(side="left", padx=7)
        ttk.Button(actions, text="Xuất SRT", command=self.export_caption, style="Primary.TButton").pack(side="right")
        self.caption_table = table
        return frame

    def _make_render_view(self) -> ttk.Frame:
        """Reference-faithful render settings, preview, and render stages progress."""
        frame = ttk.Frame(self.workspace, style="App.TFrame")
        ttk.Label(frame, text="TAB 6/6 · RENDER · XUẤT VIDEO CUỐI", style="Title.TLabel").pack(anchor="w")
        body = ttk.Frame(frame, style="App.TFrame")
        body.pack(fill="both", expand=True, pady=(14, 0))
        setup = self._card(body, "THIẾT LẬP RENDER", expand=True)
        setup.configure(width=310)
        setup.pack(side="left", fill="both", padx=(0, 10))
        setup.pack_propagate(False)
        render_fields = (
            ("Tỷ lệ", self.render_ratio_var, ("9:16 (Dọc)", "16:9 (Ngang)")),
            ("Độ phân giải", self.render_resolution_var, ("1080 × 1920", "1920 × 1080")),
            ("Frame rate", None, ("30", "60")),
            ("Chất lượng", None, ("High", "Medium")),
            ("Định dạng", None, ("MP4 (H.264)",)),
        )
        for label, variable, values in render_fields:
            ttk.Label(setup, text=label, style="Muted.TLabel").pack(anchor="w", pady=(10, 2))
            kwargs = {"values": values, "state": "readonly"}
            if variable is not None:
                kwargs["textvariable"] = variable
            ttk.Combobox(setup, **kwargs).pack(fill="x")
        ttk.Label(setup, text="Audio", style="Muted.TLabel").pack(anchor="w", pady=(10, 2))
        ttk.Label(setup, text="AAC · 48 kHz", style="Body.TLabel").pack(anchor="w")
        ttk.Button(setup, text="Render video", command=self.render_project, style="Primary.TButton").pack(fill="x", pady=(22, 6))
        ttk.Button(setup, text="Dừng render", command=self.cancel_current, style="Secondary.TButton").pack(fill="x")
        preview = self._card(body, "XEM TRƯỚC", expand=True)
        preview.pack(side="left", fill="both", expand=True)
        canvas = tk.Canvas(preview, bg="#202331", highlightthickness=0)
        canvas.pack(fill="both", expand=True, pady=(10, 8))
        canvas.create_text(220, 150, text="THẠCH TRANG\\nMẤT MẶT\\nĐẰNG SAU HÀO QUANG", fill="#f2f2f7", justify="center", font=("Segoe UI", 18, "bold"))
        ttk.Label(preview, text="00:03 / 02:45", style="Muted.TLabel").pack(anchor="w")
        progress = self._card(body, "TIẾN TRÌNH RENDER", expand=True)
        progress.configure(width=220)
        progress.pack(side="right", fill="both", padx=(10, 0))
        progress.pack_propagate(False)
        for stage in ("✓ Chuẩn bị", "✓ Render clip", "✓ Ghép audio", "○ Xuất video"):
            ttk.Label(progress, text=stage, style="Body.TLabel").pack(anchor="w", pady=8)
        ttk.Label(progress, text="87%", foreground="#9b86ff", background="#111522", font=("Segoe UI", 28, "bold")).pack(pady=(20, 5))
        ttk.Label(progress, text="Ước tính còn lại: 2 phút", style="Muted.TLabel").pack()
        return frame

    def _make_placeholder_view(self, title: str, description: str, action: Callable[[], None]) -> ttk.Frame:
        frame = ttk.Frame(self.workspace, style="App.TFrame")
        ttk.Label(frame, text=title, style="Title.TLabel").pack(anchor="w")
        panel = ttk.Frame(frame, style="Panel.TFrame", padding=24)
        panel.pack(fill="both", expand=True, pady=(18, 0))
        ttk.Label(panel, text=description, style="Body.TLabel", wraplength=650).pack(anchor="w")
        ttk.Label(panel, text="Mở Cài đặt providers để kiểm tra cấu hình và trạng thái.", style="Muted.TLabel").pack(anchor="w", pady=(12, 0))
        self._add_view_action(panel, {
            "Visuals": "Tạo ảnh cho project",
            "Vox Style": "Lưu Vox Style",
            "Voice": "Tạo voice",
            "Caption": "Tạo caption",
            "Render": "Render video",
        }.get(title, "Chạy action"), action)
        ttk.Button(panel, text="Mở Settings", command=self.open_settings, style="Secondary.TButton").pack(anchor="w", pady=(8, 0))
        return frame

    def _show_view(self, name: str) -> None:
        for frame in self.views.values():
            frame.pack_forget()
        self.views[name].pack(fill="both", expand=True)
        for key, button in self.nav_buttons.items():
            button.state(["pressed"] if key == name else ["!pressed"])
        if name == "projects":
            self.refresh_projects()

    def _add_view_action(self, frame: ttk.Frame, text: str, command: Callable[[], None], *, primary: bool = True) -> None:
        """Add one explicit action to a pipeline view."""
        ttk.Button(
            frame,
            text=text,
            command=command,
            style="Primary.TButton" if primary else "Secondary.TButton",
        ).pack(anchor="w", pady=(16, 0))

    def new_project(self) -> None:
        self.project_id = None
        self.context_var.set("Dự án mới")
        self.script_title_var.set("")
        self.script_text.delete("1.0", "end")
        self._show_view("script")
        self.status_var.set("Nhập script rồi bấm Lưu script")

    def open_project(self) -> None:
        self._show_view("projects")
        self.refresh_projects()

    def refresh_projects(self) -> None:
        self._run_async("load_projects", self._load_projects)

    async def _load_projects(self) -> list[dict[str, Any]]:
        from app.services.project_manager import ProjectManager
        from app.storage import database

        database.init_schema()
        with database.create_session() as session:
            from app.storage.repositories import ProjectRepo

            return [ProjectManager(session).get_project(item.project_id) for item in ProjectRepo.list(session)]

    def _on_project_select(self, _event: Any) -> None:
        selection = self.project_list.curselection()
        if not selection or not hasattr(self, "_projects"):
            return
        project = self._projects[selection[0]]
        self.project_id = project["project_id"]
        self.context_var.set(f"Project: {self.project_id}")
        self.script_title_var.set(project.get("title", ""))
        self._show_view("script")
        self.load_script()

    def load_script(self) -> None:
        if not self.project_id:
            return
        self._run_async("load_script", self._load_script)

    async def _load_script(self) -> str:
        from app.storage import database
        from app.storage.repositories import ProjectRepo

        database.init_schema()
        with database.create_session() as session:
            project = ProjectRepo.get(session, self.project_id)
            return project.script_text if project else ""

    def save_script(self) -> None:
        script = self.script_text.get("1.0", "end").strip()
        if not script:
            messagebox.showwarning("Thiếu script", "Hãy nhập script trước khi lưu.")
            return
        self._run_async("save_script", lambda: self._save_script(script))

    def _save_script(self, script: str) -> dict[str, Any]:
        from app.services.project_manager import ProjectManager
        from app.storage import database

        database.init_schema()
        with database.create_session() as session:
            project, _created = ProjectManager(session, project_root=self.settings.project_root or None).create_project(script, title=self.script_title_var.get(), project_id=self.project_id)
            return project

    def plan_project(self) -> None:
        if not self.project_id:
            self.save_script()
            self.root.after(250, self.plan_project)
            return
        self._run_async("plan", self._plan_project)

    async def _plan_project(self) -> dict[str, Any]:
        from app.providers.llm.cliproxy import CliproxyLLMProvider
        from app.services.project_manager import ProjectManager
        from app.services.prompts import load_presets
        from app.services.script_analysis import ScriptAnalyzer
        from app.storage import database
        from app.storage.repositories import ProjectRepo

        database.init_schema()
        with database.create_session() as session:
            project = ProjectRepo.get(session, self.project_id)
            if project is None:
                raise RuntimeError("project not found")
            provider = CliproxyLLMProvider(base_url=self.settings.cliproxy_base_url, model=self.settings.cliproxy_model, api_key=self.settings.cliproxy_api_key, timeout_seconds=self.settings.cliproxy_timeout_seconds)
            try:
                return await ProjectManager(session, project_root=self.settings.project_root or None).plan(self.project_id, ScriptAnalyzer(provider, style_preset=load_presets().get(project.style_preset)))
            finally:
                await provider.aclose()

    def check_providers(self) -> None:
        self._run_async("provider_check", self._check_providers)

    async def _check_providers(self) -> dict[str, Any]:
        from app.providers.image.cliproxy_image import CliproxyImageProvider
        from app.providers.image.flowkit import FlowKitImageProvider
        from app.providers.tts.omnivoice import OmniVoiceProvider

        providers: dict[str, Any] = {}
        cp = CliproxyImageProvider(
            base_url=self.settings.cliproxy_base_url,
            model="gpt-image-2",
            api_key=self.settings.cliproxy_api_key,
            timeout_seconds=5,
        )
        fk = FlowKitImageProvider(
            base_url=self.settings.flowkit_base_url,
            health_path=self.settings.flowkit_health_path,
            timeout_seconds=5,
        )
        ov = OmniVoiceProvider(
            base_url=f"http://{self.settings.omnivoice_worker_host}:{self.settings.omnivoice_worker_port}",
            timeout_seconds=5,
        )
        try:
            providers["CLIProxy image"] = (await cp.health()).status
            providers["FlowKit"] = (await fk.health()).status
            providers["OmniVoice"] = (await ov.health()).status
        finally:
            await cp.aclose()
            await fk.aclose()
            await ov.aclose()
        return providers
    def open_settings(self) -> None:
        SettingsDialog(self.root, self.settings, self._settings_saved)

    def _settings_saved(self, settings: RuntimeSettings) -> None:
        self.settings = settings
        save_runtime_settings(settings)
        self.status_var.set("Đã lưu settings providers")

    def _require_project(self) -> bool:
        if self.project_id:
            return True
        messagebox.showwarning("Chưa chọn project", "Hãy tạo hoặc chọn project trước.")
        self._show_view("projects")
        return False

    def generate_images(self) -> None:
        if not self._require_project():
            return
        self.prompt_var.set(self.visual_prompt.get("1.0", "end").strip())
        self._run_async("generate_images", self._generate_images)

    async def _generate_images(self) -> dict[str, Any]:
        from app.providers.image.antigravity import AntigravityImageProvider
        from app.providers.image.cliproxy_image import CliproxyImageProvider
        from app.providers.image.flowkit import FlowKitImageProvider
        from app.runtime_settings import load_runtime_settings
        from app.services.image_generation import ImageGenerationService
        from app.storage import database

        runtime = load_runtime_settings()
        provider_name = runtime.image_provider
        if provider_name == "auto":
            provider_name = "flowkit" if runtime.flowkit_enabled else "cliproxy_image"
        flowkit = FlowKitImageProvider(
            base_url=runtime.flowkit_base_url,
            health_path=runtime.flowkit_health_path,
            submit_path=runtime.flowkit_submit_path,
            status_path_template=runtime.flowkit_status_path_template,
            timeout_seconds=runtime.flowkit_timeout_seconds,
        )
        cliproxy = CliproxyImageProvider(
            base_url=runtime.cliproxy_base_url,
            model="gpt-image-2",
            api_key=runtime.cliproxy_api_key,
            timeout_seconds=runtime.cliproxy_timeout_seconds,
        )
        antigravity = AntigravityImageProvider()
        providers = {"flowkit": flowkit, "cliproxy_image": cliproxy, "antigravity_image": antigravity}
        try:
            chosen = providers[provider_name]
            database.init_schema()
            with database.create_session() as session:
                service = ImageGenerationService(
                    chosen,
                    provider_name=provider_name,
                    flowkit_provider=flowkit,
                    cliproxy_provider=cliproxy,
                )
                result = await service.generate_project(self.project_id, session, provider_name=provider_name)
                return {
                    "generated": result.generated,
                    "cached": result.cached,
                    "errors": result.errors,
                    "selected_asset_id": getattr(result, "selected_asset_id", None),
                }
        finally:
            await flowkit.aclose()
            await cliproxy.aclose()
            await antigravity.aclose()

    def download_selected_image(self) -> None:
        """Download is truthful until a durable selected asset exists."""
        self.status_var.set("Tải ảnh: chưa có asset được chọn")

    def use_selected_image(self) -> None:
        """Use selected image only after ImageGenerationService returns an asset."""
        if not self._require_project():
            return
        if not getattr(self, "selected_image_asset_id", None):
            self.status_var.set("Dùng ảnh này: cần tạo và chọn asset thật trước")
            return
        self.status_var.set("Đã chọn asset cho cảnh hiện tại")

    def export_caption(self) -> None:
        if self._require_project():
            self._run_async("generate_caption", self._generate_caption)

    def save_style(self) -> None:
        if self._require_project():
            self._run_async("save_style", self._save_style)

    def _save_style(self) -> dict[str, Any]:
        from app.storage.asset_store import AssetStore

        store = AssetStore(self.settings.project_root or None)
        path, digest = store.write_manifest(
            self.project_id,
            "style.json",
            {
                "project_id": self.project_id,
                "preset": "editorial_collage",
                "provider_settings": _make_provider_settings(self.settings),
            },
        )
        return {"path": str(path), "sha256": digest}

    def generate_voice(self) -> None:
        if self._require_project():
            self._run_async("generate_voice", self._generate_voice)

    async def _generate_voice(self) -> dict[str, Any]:
        from app.providers.tts.omnivoice import OmniVoiceProvider
        from app.services.tts_pipeline import TTSScenePipeline
        from app.storage import database
        from app.storage.asset_store import AssetStore

        database.init_schema()
        provider = OmniVoiceProvider(
            base_url=f"http://{self.settings.omnivoice_worker_host}:{self.settings.omnivoice_worker_port}",
            timeout_seconds=self.settings.omnivoice_timeout_seconds,
        )
        try:
            with database.create_session() as session:
                result = await TTSScenePipeline(
                    provider,
                    voice_profile_id=self.settings.voice_profile_id,
                ).run(self.project_id, session, project_root=AssetStore(self.settings.project_root or None).base)
                return {
                    "generated": result.generated,
                    "cached": result.cached,
                    "errors": result.errors,
                }
        finally:
            await provider.aclose()

    def generate_caption(self) -> None:
        if self._require_project():
            self._run_async("generate_caption", self._generate_caption)

    def _generate_caption(self) -> dict[str, Any]:
        from app.services.subtitle_generator import SceneNarration, SubtitleGenerator
        from app.storage import database
        from app.storage.asset_store import AssetStore
        from app.storage.repositories import SceneRepo

        database.init_schema()
        store = AssetStore(self.settings.project_root or None)
        with database.create_session() as session:
            scenes = SceneRepo.list(session, self.project_id)
            narrations = [
                SceneNarration(
                    scene_id=scene.scene_id,
                    narration=scene.narration_text,
                    voice_duration_ms=int(scene.actual_voice_duration_ms or 5000),
                    order=int(scene.order),
                )
                for scene in scenes
            ]
            output = store.subdir(self.project_id, "final") / "subtitles.srt"
            result = SubtitleGenerator().generate(self.project_id, narrations, output)
            return {"path": result.srt_path, "entries": result.entry_count}

    def render_project(self) -> None:
        if self._require_project():
            self._run_async("render", self._render_project)

    async def _render_project(self) -> dict[str, Any]:
        from app.services.project_manager import ProjectManager
        from app.services.scene_renderer import LocalSceneRenderer
        from app.storage import database

        database.init_schema()
        with database.create_session() as session:
            result = await ProjectManager(session, project_root=self.settings.project_root or None).render_project(
                self.project_id,
                renderer=LocalSceneRenderer(),
            )
            return {"rendered": result.get("rendered", []), "audio_files": result.get("audio_files", [])}

    def show_help(self) -> None:
        messagebox.showinfo("Vox Studio", "Workflow: Projects → Script → Visuals → Vox Style → Voice → Caption → Render. Cấu hình provider trong Settings.")

    def cancel_current(self) -> None:
        self.status_var.set("Không có native hard-cancel; stage hiện tại sẽ kết thúc an toàn.")

    def shutdown(self) -> None:
        """Stop the Tk event loop without starting or leaving a web server."""
        self.root.destroy()

    def _run_async(self, label: str, fn: Callable[[], Any]) -> None:
        self.status_var.set(f"Đang chạy: {label}...")
        def worker() -> None:
            try:
                result = fn()
                if asyncio.iscoroutine(result):
                    result = asyncio.run(result)
                self.events.put(("ok", (label, result)))
            except Exception as exc:  # noqa: BLE001
                self.events.put(("error", (label, str(exc))))
        threading.Thread(target=worker, daemon=True).start()

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "ok":
                    label, result = payload
                    if label == "load_projects":
                        self._projects = result
                        self.project_list.delete(0, "end")
                        for project in result:
                            self.project_list.insert("end", f"{project.get('title') or project['project_id']}  ·  {project.get('status')}")
                    elif label == "load_script":
                        self.script_text.delete("1.0", "end")
                        self.script_text.insert("1.0", result)
                    elif label == "provider_check":
                        self.provider_var.set(" · ".join(f"{key}: {value}" for key, value in result.items()))
                    elif label == "save_script":
                        self.project_id = result["project_id"]
                        self.context_var.set(f"Project: {self.project_id}")
                        self.status_var.set("Đã lưu project/script")
                    elif label == "save_style":
                        self.status_var.set(f"Đã lưu style manifest: {result['path']}")
                    elif label == "generate_images":
                        generated = result.get("generated", 0)
                        self.selected_image_asset_id = result.get("selected_asset_id")
                        self.status_var.set(f"Images: generated={generated} cached={result.get('cached', 0)}")
                    elif label == "generate_voice":
                        self.status_var.set(f"Voice: generated={result['generated']} cached={result['cached']}")
                    elif label == "generate_caption":
                        self.status_var.set(f"Caption: {result['entries']} entries → {result['path']}")
                    elif label == "render":
                        self.status_var.set(f"Render: {len(result['rendered'])} scene(s) completed")
                    else:
                        self.status_var.set(f"Hoàn tất: {label}")
                else:
                    label, error = payload
                    self.status_var.set(f"Lỗi {label}: {error}")
                    messagebox.showerror("Vox Studio", error)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)


class SettingsDialog(tk.Toplevel):
    """Native provider settings dialog with secret masking."""

    def __init__(self, parent: tk.Misc, settings: RuntimeSettings, on_save: Callable[[RuntimeSettings], None]) -> None:
        super().__init__(parent)
        self.title("Vox Studio — Settings")
        self.geometry("720x650")
        self.configure(bg="#111522")
        self.transient(parent)
        self.grab_set()
        self.settings = settings
        self.on_save = on_save
        self.vars: dict[str, tk.Variable] = {}
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Provider & Workspace Settings", style="Header.TLabel").pack(anchor="w")
        ttk.Label(outer, text="API keys are masked and saved only when you click Save.", style="Muted.TLabel").pack(anchor="w", pady=(3, 15))
        canvas = tk.Canvas(outer, bg="#111522", highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        body = ttk.Frame(canvas, style="Panel.TFrame")
        body.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        rows = [
            ("CLIProxy Base URL", "cliproxy_base_url", False),
            ("CLIProxy Model", "cliproxy_model", False),
            ("CLIProxy API key", "cliproxy_api_key", True),
            ("FlowKit Base URL", "flowkit_base_url", False),
            ("FlowKit Health Path", "flowkit_health_path", False),
            ("FlowKit Submit Path", "flowkit_submit_path", False),
            ("FlowKit Status Path", "flowkit_status_path_template", False),
            ("OmniVoice Host", "omnivoice_worker_host", False),
            ("OmniVoice Port", "omnivoice_worker_port", False),
            ("Project root", "project_root", False),
        ]
        for label, key, secret in rows:
            row = ttk.Frame(body, style="Panel.TFrame")
            row.pack(fill="x", pady=5)
            ttk.Label(row, text=label, style="Body.TLabel", width=25).pack(side="left")
            value = getattr(self.settings, key)
            variable = tk.StringVar(value=str(value))
            self.vars[key] = variable
            entry = ttk.Entry(row, textvariable=variable, show="•" if secret else "")
            entry.pack(side="left", fill="x", expand=True)
        row = ttk.Frame(body, style="Panel.TFrame")
        row.pack(fill="x", pady=5)
        ttk.Label(row, text="Image provider", style="Body.TLabel", width=25).pack(side="left")
        image_var = tk.StringVar(value=self.settings.image_provider)
        self.vars["image_provider"] = image_var
        ttk.Combobox(row, textvariable=image_var, values=("auto", "flowkit", "cliproxy_image", "antigravity_image"), state="readonly").pack(side="left", fill="x", expand=True)
        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy, style="Secondary.TButton").pack(side="right")
        ttk.Button(buttons, text="Save", command=self._save, style="Primary.TButton").pack(side="right", padx=8)

    def _save(self) -> None:
        data = self.settings.to_dict()
        for key, variable in self.vars.items():
            data[key] = variable.get()
        data["flowkit_enabled"] = True if data.get("image_provider") == "flowkit" else self.settings.flowkit_enabled
        updated = RuntimeSettings.from_dict(data)
        self.on_save(updated)
        self.destroy()


class _suppress_tcl:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_: Any) -> bool:
        return True


def launch_native() -> None:
    root = tk.Tk()
    NativeVoxStudio(root)
    root.mainloop()
