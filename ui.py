"""
Modern Native GUI for Thermalright Frozen Warframe 360 SE AIO Display.
Built with CustomTkinter (fluent dark theme, ultra-low resource consumption).
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk

from display_driver import WarframeDisplayDriver
from gif_processor import GifProcessor
from system_monitor import SystemMonitor
from config_manager import ConfigManager

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class WarframeApp(ctk.CTk):
    def __init__(self, driver: WarframeDisplayDriver, processor: GifProcessor, monitor: SystemMonitor, config: ConfigManager):
        super().__init__()

        self.driver = driver
        self.processor = processor
        self.monitor = monitor
        self.config = config

        # Window configuration
        self.title("Thermalright Warframe AIO - Native Display Control")
        self.geometry("920x620")
        self.minsize(860, 580)

        # Set window icon if available
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "app_icon.png")
        if os.path.exists(icon_path):
            try:
                self.iconphoto(False, tk.PhotoImage(file=icon_path))
            except Exception:
                pass

        # Playback state
        self.is_playing = True
        self.current_frame_index = 0
        self.last_frame_time = 0
        self.running = True
        self.tray_icon = None

        self._setup_ui()
        self._load_saved_settings()

        # Start playback thread
        self.worker_thread = threading.Thread(target=self._display_loop, daemon=True)
        self.worker_thread.start()

        # Handle window close (minimize to tray)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Regular periodic check for device connection & TRCC status
        self.after(2000, self._periodic_status_check)

    def _setup_ui(self):
        # Grid layout: 2 columns (Left: Preview + controls, Right: Settings tabs)
        self.grid_columnconfigure(0, weight=0, minsize=380)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ==========================================
        # LEFT PANEL: Virtual Screen & Preview
        # ==========================================
        left_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#181B20")
        left_frame.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsew")
        left_frame.grid_rowconfigure(1, weight=1)

        # Header Title
        title_box = ctk.CTkFrame(left_frame, fg_color="transparent")
        title_box.pack(fill="x", padx=16, pady=(16, 8))
        
        lbl_title = ctk.CTkLabel(title_box, text="❄️ Frozen Warframe 360 SE", font=ctk.CTkFont(size=18, weight="bold"), text_color="#FFFFFF")
        lbl_title.pack(anchor="w")
        
        self.lbl_status_badge = ctk.CTkLabel(title_box, text="● Đang kiểm tra kết nối...", font=ctk.CTkFont(size=12), text_color="#F5A623")
        self.lbl_status_badge.pack(anchor="w", pady=(2, 0))

        # Virtual AIO Bezel & Display Preview
        preview_container = ctk.CTkFrame(left_frame, fg_color="#0F1115", corner_radius=16, border_width=2, border_color="#2A2F38")
        preview_container.pack(padx=20, pady=10, fill="both", expand=True)

        self.lbl_preview = ctk.CTkLabel(preview_container, text="", width=240, height=320)
        self.lbl_preview.place(relx=0.5, rely=0.5, anchor="center")

        # Preview Controls bar
        controls_bar = ctk.CTkFrame(left_frame, fg_color="transparent")
        controls_bar.pack(fill="x", padx=20, pady=(4, 16))

        self.btn_play_pause = ctk.CTkButton(controls_bar, text="⏸️ Tạm dừng", width=120, height=34, fg_color="#2962FF", hover_color="#1E40AF", command=self._toggle_playback)
        self.btn_play_pause.pack(side="left", padx=(0, 8))

        self.btn_quick_rotate = ctk.CTkButton(controls_bar, text="🔄 Xoay 90°", width=110, height=34, fg_color="#2D333B", hover_color="#3E4752", command=self._quick_rotate)
        self.btn_quick_rotate.pack(side="left")

        self.lbl_fps_stat = ctk.CTkLabel(controls_bar, text="0 FPS", font=ctk.CTkFont(size=11), text_color="#8B949E")
        self.lbl_fps_stat.pack(side="right")

        # ==========================================
        # RIGHT PANEL: Tabview for Settings
        # ==========================================
        right_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#181B20")
        right_frame.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(right_frame, fg_color="#181B20")
        self.tabview.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")

        tab_media = self.tabview.add("🖼️ GIF & Hình Ảnh")
        tab_overlay = self.tabview.add("📊 Thông Số (Overlay)")
        tab_perf = self.tabview.add("⚡ Tối Ưu & Hệ Thống")

        # --- TAB 1: GIF & Media Settings ---
        # File selector section
        grp_file = ctk.CTkFrame(tab_media, fg_color="#21262D", corner_radius=10)
        grp_file.pack(fill="x", padx=8, pady=8)

        btn_browse = ctk.CTkButton(grp_file, text="📁 Chọn GIF hoặc Ảnh mới...", height=38, font=ctk.CTkFont(weight="bold"), fg_color="#00C853", hover_color="#00A844", command=self._choose_file)
        btn_browse.pack(fill="x", padx=16, pady=(14, 8))

        self.lbl_file_info = ctk.CTkLabel(grp_file, text="Chưa chọn tệp", font=ctk.CTkFont(size=12), text_color="#8B949E", wraplength=400)
        self.lbl_file_info.pack(padx=16, pady=(0, 12))

        # Orientation Settings
        grp_orient = ctk.CTkFrame(tab_media, fg_color="#21262D", corner_radius=10)
        grp_orient.pack(fill="x", padx=8, pady=8)

        ctk.CTkLabel(grp_orient, text="Hướng xoay màn hình (Orientation):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(12, 4))
        self.seg_rotation = ctk.CTkSegmentedButton(grp_orient, values=["0°", "90°", "180°", "270°"], command=self._on_rotation_changed)
        self.seg_rotation.pack(fill="x", padx=16, pady=(0, 12))

        # Scaling / Fit Mode
        grp_fit = ctk.CTkFrame(tab_media, fg_color="#21262D", corner_radius=10)
        grp_fit.pack(fill="x", padx=8, pady=8)

        ctk.CTkLabel(grp_fit, text="Chế độ vừa khung (Fit Mode):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(12, 4))
        self.seg_fit = ctk.CTkSegmentedButton(grp_fit, values=["Cắt vừa (Fill)", "Giữ tỷ lệ (Fit)", "Kéo giãn (Stretch)"], command=self._on_fit_changed)
        self.seg_fit.pack(fill="x", padx=16, pady=(0, 12))

        # Sliders: FPS Limit & Brightness
        grp_sliders = ctk.CTkFrame(tab_media, fg_color="#21262D", corner_radius=10)
        grp_sliders.pack(fill="x", padx=8, pady=8)

        # FPS Slider
        fps_box = ctk.CTkFrame(grp_sliders, fg_color="transparent")
        fps_box.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(fps_box, text="Giới hạn tốc độ khung hình (FPS):", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.lbl_fps_val = ctk.CTkLabel(fps_box, text="20 FPS", text_color="#00E5FF", font=ctk.CTkFont(weight="bold"))
        self.lbl_fps_val.pack(side="right")

        self.slider_fps = ctk.CTkSlider(grp_sliders, from_=5, to=30, number_of_steps=25, command=self._on_fps_slider_changed)
        self.slider_fps.pack(fill="x", padx=16, pady=(0, 8))

        # Brightness Slider
        bri_box = ctk.CTkFrame(grp_sliders, fg_color="transparent")
        bri_box.pack(fill="x", padx=16, pady=(8, 4))
        ctk.CTkLabel(bri_box, text="Độ sáng hiển thị (Brightness):", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.lbl_bri_val = ctk.CTkLabel(bri_box, text="100%", text_color="#00E5FF", font=ctk.CTkFont(weight="bold"))
        self.lbl_bri_val.pack(side="right")

        self.slider_bri = ctk.CTkSlider(grp_sliders, from_=10, to=100, number_of_steps=18, command=self._on_brightness_slider_changed)
        self.slider_bri.pack(fill="x", padx=16, pady=(0, 14))

        # --- TAB 2: Hardware Overlay Settings ---
        grp_ov = ctk.CTkFrame(tab_overlay, fg_color="#21262D", corner_radius=10)
        grp_ov.pack(fill="x", padx=8, pady=8)

        self.sw_overlay = ctk.CTkSwitch(grp_ov, text="Bật hiển thị thông số CPU / RAM trên màn hình", font=ctk.CTkFont(weight="bold"), command=self._on_overlay_toggle)
        self.sw_overlay.pack(anchor="w", padx=16, pady=14)

        grp_pos = ctk.CTkFrame(tab_overlay, fg_color="#21262D", corner_radius=10)
        grp_pos.pack(fill="x", padx=8, pady=8)

        ctk.CTkLabel(grp_pos, text="Vị trí hiển thị (Overlay Position):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(12, 4))
        self.seg_pos = ctk.CTkSegmentedButton(grp_pos, values=["Dưới cùng (Bottom)", "Ở giữa (Center)", "Trên cùng (Top)"], command=self._on_overlay_pos_changed)
        self.seg_pos.pack(fill="x", padx=16, pady=(0, 14))

        # Live stats preview card
        card_stats = ctk.CTkFrame(tab_overlay, fg_color="#181B20", corner_radius=10, border_width=1, border_color="#30363D")
        card_stats.pack(fill="x", padx=8, pady=12)

        ctk.CTkLabel(card_stats, text="Thông số phần cứng hiện tại (Siêu nhẹ):", font=ctk.CTkFont(size=12, weight="bold"), text_color="#8B949E").pack(anchor="w", padx=14, pady=(10, 4))
        self.lbl_live_stats = ctk.CTkLabel(card_stats, text="CPU: 0% | RAM: 0% | GPU: 0°C", font=ctk.CTkFont(size=14, weight="bold"), text_color="#00E5FF")
        self.lbl_live_stats.pack(anchor="w", padx=14, pady=(0, 10))

        # --- TAB 3: TRCC & Performance Optimization ---
        grp_trcc = ctk.CTkFrame(tab_perf, fg_color="#21262D", corner_radius=10)
        grp_trcc.pack(fill="x", padx=8, pady=8)

        ctk.CTkLabel(grp_trcc, text="Quản lý tiến trình TRCC gốc:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(12, 2))
        self.lbl_trcc_status = ctk.CTkLabel(grp_trcc, text="Đang kiểm tra...", font=ctk.CTkFont(size=12), text_color="#8B949E")
        self.lbl_trcc_status.pack(anchor="w", padx=16, pady=(0, 10))

        self.btn_kill_trcc = ctk.CTkButton(grp_trcc, text="🛑 Tắt ngay TRCC & HWINFO (Giải phóng CPU & RAM)", fg_color="#D32F2F", hover_color="#B71C1C", font=ctk.CTkFont(weight="bold"), command=self._kill_trcc)
        self.btn_kill_trcc.pack(fill="x", padx=16, pady=(0, 14))

        grp_startup = ctk.CTkFrame(tab_perf, fg_color="#21262D", corner_radius=10)
        grp_startup.pack(fill="x", padx=8, pady=8)

        self.sw_autostart = ctk.CTkSwitch(grp_startup, text="Khởi động ứng dụng này cùng Windows (Chạy nền)", command=self._on_autostart_toggle)
        self.sw_autostart.pack(anchor="w", padx=16, pady=(14, 8))

        self.sw_disable_trcc_startup = ctk.CTkSwitch(grp_startup, text="Tắt tự khởi động TRCC gốc trong Task Scheduler", command=self._on_disable_trcc_task_toggle)
        self.sw_disable_trcc_startup.pack(anchor="w", padx=16, pady=(0, 14))

        grp_tray = ctk.CTkFrame(tab_perf, fg_color="#21262D", corner_radius=10)
        grp_tray.pack(fill="x", padx=8, pady=8)

        self.sw_minimize_tray = ctk.CTkSwitch(grp_tray, text="Thu nhỏ xuống khay hệ thống (System Tray) khi đóng cửa sổ", command=self._on_minimize_tray_toggle)
        self.sw_minimize_tray.pack(anchor="w", padx=16, pady=(14, 8))

        btn_hide_now = ctk.CTkButton(grp_tray, text="🔽 Thu nhỏ vào khay ngay bây giờ", fg_color="#30363D", hover_color="#484F58", command=self._minimize_to_tray)
        btn_hide_now.pack(fill="x", padx=16, pady=(0, 14))

    def _load_saved_settings(self):
        # Load from config
        rot = self.config.get("rotation", 0)
        rot_str = f"{rot}°"
        self.seg_rotation.set(rot_str)

        fit = self.config.get("fit_mode", "fill")
        fit_map = {"fill": "Cắt vừa (Fill)", "fit": "Giữ tỷ lệ (Fit)", "stretch": "Kéo giãn (Stretch)"}
        self.seg_fit.set(fit_map.get(fit, "Cắt vừa (Fill)"))

        fps = self.config.get("fps_override", 20)
        self.slider_fps.set(fps)
        self.lbl_fps_val.configure(text=f"{fps} FPS")

        bri = int(self.config.get("brightness", 1.0) * 100)
        self.slider_bri.set(bri)
        self.lbl_bri_val.configure(text=f"{bri}%")

        ov_en = self.config.get("overlay_enabled", False)
        if ov_en:
            self.sw_overlay.select()
        else:
            self.sw_overlay.deselect()

        ov_pos = self.config.get("overlay_position", "bottom")
        pos_map = {"bottom": "Dưới cùng (Bottom)", "center": "Ở giữa (Center)", "top": "Trên cùng (Top)"}
        self.seg_pos.set(pos_map.get(ov_pos, "Dưới cùng (Bottom)"))

        autostart = self.config.get("autostart", False)
        if autostart:
            self.sw_autostart.select()
        else:
            self.sw_autostart.deselect()

        min_tray = self.config.get("minimize_to_tray", True)
        if min_tray:
            self.sw_minimize_tray.select()
        else:
            self.sw_minimize_tray.deselect()

        # Load last file or sample core GIF
        last_file = self.config.get("last_file", "")
        if not last_file or not os.path.exists(last_file):
            last_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sample_core.gif")

        if os.path.exists(last_file):
            self._load_file(last_file)

    def _choose_file(self):
        path = filedialog.askopenfilename(
            title="Chọn GIF hoặc Ảnh cho màn hình AIO",
            filetypes=[
                ("Hình ảnh & GIF", "*.gif;*.png;*.jpg;*.jpeg;*.webp;*.bmp"),
                ("Ảnh GIF động", "*.gif"),
                ("Tất cả tệp", "*.*")
            ]
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        rot = int(self.seg_rotation.get().replace("°", ""))
        fit_reverse = {"Cắt vừa (Fill)": "fill", "Giữ tỷ lệ (Fit)": "fit", "Kéo giãn (Stretch)": "stretch"}
        fit = fit_reverse.get(self.seg_fit.get(), "fill")
        fps = int(self.slider_fps.get())
        bri = self.slider_bri.get() / 100.0

        if self.processor.load_file(path, rotation=rot, fit_mode=fit, brightness=bri, fps_override=fps):
            self.config.set("last_file", path)
            name = os.path.basename(path)
            frames_count = self.processor.total_frames
            dur_info = f"{frames_count} khung hình" if frames_count > 1 else "Ảnh tĩnh"
            self.lbl_file_info.configure(text=f"Tệp: {name}\n({dur_info} | {fit})")
            self.current_frame_index = 0

    def _on_rotation_changed(self, value):
        rot = int(value.replace("°", ""))
        self.processor.set_rotation(rot)
        self.config.set("rotation", rot)

    def _quick_rotate(self):
        cur_rot = int(self.seg_rotation.get().replace("°", ""))
        next_rot = (cur_rot + 90) % 360
        self.seg_rotation.set(f"{next_rot}°")
        self._on_rotation_changed(f"{next_rot}°")

    def _on_fit_changed(self, value):
        fit_reverse = {"Cắt vừa (Fill)": "fill", "Giữ tỷ lệ (Fit)": "fit", "Kéo giãn (Stretch)": "stretch"}
        fit = fit_reverse.get(value, "fill")
        self.processor.set_fit_mode(fit)
        self.config.set("fit_mode", fit)

    def _on_fps_slider_changed(self, value):
        fps = int(value)
        self.lbl_fps_val.configure(text=f"{fps} FPS")
        self.processor.set_fps_override(fps)
        self.config.set("fps_override", fps)

    def _on_brightness_slider_changed(self, value):
        bri_pct = int(value)
        self.lbl_bri_val.configure(text=f"{bri_pct}%")
        self.processor.set_brightness(bri_pct / 100.0)
        self.config.set("brightness", bri_pct / 100.0)

    def _on_overlay_toggle(self):
        enabled = self.sw_overlay.get() == 1
        self.config.set("overlay_enabled", enabled)

    def _on_overlay_pos_changed(self, value):
        pos_map = {"Dưới cùng (Bottom)": "bottom", "Ở giữa (Center)": "center", "Trên cùng (Top)": "top"}
        pos = pos_map.get(value, "bottom")
        self.config.set("overlay_position", pos)

    def _toggle_playback(self):
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.btn_play_pause.configure(text="⏸️ Tạm dừng", fg_color="#2962FF")
        else:
            self.btn_play_pause.configure(text="▶️ Tiếp tục", fg_color="#00C853")

    def _kill_trcc(self):
        killed = ConfigManager.kill_trcc_processes()
        if killed > 0:
            messagebox.showinfo("Đã tối ưu", f"Đã dừng thành công {killed} tiến trình TRCC/HWINFO!\nCPU và RAM đã được giải phóng.")
        else:
            messagebox.showinfo("Thông báo", "Không tìm thấy tiến trình TRCC nào đang chạy.")
        self._periodic_status_check()

    def _on_autostart_toggle(self):
        enabled = self.sw_autostart.get() == 1
        self.config.set_autostart(enabled)

    def _on_disable_trcc_task_toggle(self):
        disable = self.sw_disable_trcc_startup.get() == 1
        ConfigManager.set_trcc_task_enabled(not disable)

    def _on_minimize_tray_toggle(self):
        self.config.set("minimize_to_tray", self.sw_minimize_tray.get() == 1)

    def _periodic_status_check(self):
        """Checks connection status and TRCC running state."""
        # 1. Device connection check
        if self.driver.is_connected():
            self.lbl_status_badge.configure(text="🟢 Đã kết nối AIO (0416:5302)", text_color="#00E676")
        else:
            connected = self.driver.connect()
            if connected:
                self.lbl_status_badge.configure(text="🟢 Đã kết nối AIO (0416:5302)", text_color="#00E676")
            else:
                self.lbl_status_badge.configure(text="🔴 Không tìm thấy thiết bị AIO", text_color="#FF5252")

        # 2. TRCC process check
        trcc_running = ConfigManager.is_trcc_running()
        if trcc_running:
            self.lbl_trcc_status.configure(text="⚠️ Cảnh báo: TRCC đang chạy ngầm gây tốn CPU & RAM", text_color="#FF5252")
            self.btn_kill_trcc.configure(state="normal")
        else:
            self.lbl_trcc_status.configure(text="✅ Tối ưu: TRCC không chạy, tiết kiệm tối đa CPU/RAM", text_color="#00E676")

        # 3. Live stats update
        stats = self.monitor.get_stats()
        self.lbl_live_stats.configure(
            text=f"CPU: {stats['cpu_usage']:.0f}%  |  RAM: {stats['ram_usage']:.0f}%  |  GPU: {stats['gpu_temp']:.0f}°C ({stats['gpu_usage']:.0f}%)"
        )

        if self.running:
            self.after(2000, self._periodic_status_check)

    def _display_loop(self):
        """Dedicated high-efficiency display thread sending frames to LCD and UI preview."""
        fps_counter = 0
        fps_timer = time.time()
        last_preview_time = 0

        while self.running:
            if not self.is_playing or not self.processor.frames:
                time.sleep(0.05)
                continue

            frame_data = self.processor.get_frame(self.current_frame_index)
            if not frame_data:
                time.sleep(0.05)
                continue

            # Overlay handling
            overlay_en = self.config.get("overlay_enabled", False)
            if overlay_en:
                stats = self.monitor.get_stats()
                pos = self.config.get("overlay_position", "bottom")
                pil_display, rgb565_bytes = self.processor.render_overlay_frame(
                    self.current_frame_index,
                    cpu_usage=stats["cpu_usage"],
                    cpu_temp=stats["gpu_temp"], # fallback or GPU temp
                    ram_usage=stats["ram_usage"],
                    position=pos
                )
            else:
                pil_display = frame_data.pil_image
                rgb565_bytes = frame_data.rgb565_bytes

            # 1. Send to hardware LCD
            self.driver.send_frame(rgb565_bytes)

            # 2. Update Tkinter UI preview (only if window is actually visible, throttled to 12 FPS)
            now = time.time()
            if now - last_preview_time >= 0.08:
                last_preview_time = now
                try:
                    if self.state() == "normal" and self.winfo_viewable():
                        preview_img = ctk.CTkImage(light_image=pil_display, dark_image=pil_display, size=(240, 320))
                        self.lbl_preview.configure(image=preview_img)
                        self.lbl_preview.image = preview_img
                except Exception:
                    pass

            # FPS counter
            fps_counter += 1
            now = time.time()
            if now - fps_timer >= 1.0:
                calc_fps = fps_counter / (now - fps_timer)
                self.lbl_fps_stat.configure(text=f"{calc_fps:.1f} FPS")
                fps_counter = 0
                fps_timer = now

            # Advance frame
            self.current_frame_index = (self.current_frame_index + 1) % len(self.processor.frames)

            # Target frame duration sleep
            dur_sec = max(0.015, frame_data.duration_ms / 1000.0)
            time.sleep(dur_sec)

    def _on_close(self):
        if self.config.get("minimize_to_tray", True):
            self._minimize_to_tray()
        else:
            self._quit_app()

    def _minimize_to_tray(self):
        self.withdraw()
        if self.tray_icon is None:
            self._create_tray_icon()

    def _create_tray_icon(self):
        import pystray
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "app_icon.png")
        if os.path.exists(icon_path):
            img = Image.open(icon_path)
        else:
            img = Image.new("RGB", (64, 64), (0, 180, 255))

        menu = pystray.Menu(
            pystray.MenuItem("Hiển thị cửa sổ", self._restore_from_tray, default=True),
            pystray.MenuItem("Tạm dừng / Tiếp tục", self._tray_toggle_playback),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Thoát", self._quit_app)
        )

        self.tray_icon = pystray.Icon("WarframeAIO", img, "Thermalright Warframe AIO", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _restore_from_tray(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.after(0, self.deiconify)
        self.after(0, self.lift)

    def _tray_toggle_playback(self, icon=None, item=None):
        self.after(0, self._toggle_playback)

    def _quit_app(self, icon=None, item=None):
        self.running = False
        if self.tray_icon:
            self.tray_icon.stop()
        self.driver.disconnect()
        self.monitor.stop()
        self.destroy()
        sys.exit(0)

