"""
Thermalright Warframe 360 SE - Pro Max Application Main Entry.
Starts the high-efficiency display driver, hardware monitor, embedded API server,
and launches the sleek Standalone Desktop Control Deck.
"""

import sys
import os
import time
import threading
import subprocess
import pystray
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from display_driver import WarframeDisplayDriver
from gif_processor import GifProcessor
from system_monitor import SystemMonitor
from config_manager import ConfigManager
from web_ui import WebUIServer

EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

class WarframeControllerApp:
    def __init__(self):
        self.driver = WarframeDisplayDriver()
        self.processor = GifProcessor()
        self.monitor = SystemMonitor(interval=1.5)
        self.config = ConfigManager()
        self.server = WebUIServer(self.driver, self.processor, self.monitor, self.config, port=28765)

        self.running = True
        self.is_playing = True
        self.current_frame_index = 0
        self.edge_proc = None
        self.tray_icon = None

        # Load last used file or default core preset
        last_file = self.config.get("last_file", "")
        if not last_file or not os.path.exists(last_file):
            last_file = os.path.join(SCRIPT_DIR, "assets", "sample_core.gif")

        rot = self.config.get("rotation", 0)
        fit = self.config.get("fit_mode", "fill")
        fps = self.config.get("fps_override", 20)
        bri = self.config.get("brightness", 1.0)
        if os.path.exists(last_file):
            self.processor.load_file(last_file, rotation=rot, fit_mode=fit, brightness=bri, fps_override=fps)

    def start(self, minimized=False):
        # 1. Connect to display
        self.driver.connect()

        # 2. Start hardware monitor
        self.monitor.start()

        # 3. Start embedded API server
        self.server.start()

        # 4. Start background display streaming loop
        threading.Thread(target=self._display_loop, daemon=True).start()

        # 5. Start system tray icon
        threading.Thread(target=self._run_tray, daemon=True).start()

        # 6. Launch Edge Standalone App window if not minimized
        if not minimized:
            self.open_window()

        # Keep main thread alive
        try:
            while self.running:
                time.sleep(1.0)
        except KeyboardInterrupt:
            self.quit()

    def open_window(self):
        """Open or refocus the standalone Edge App Window."""
        if self.edge_proc is not None and self.edge_proc.poll() is None:
            # Already running
            return

        edge_exe = None
        for p in EDGE_PATHS:
            if os.path.exists(p):
                edge_exe = p
                break

        url = "http://127.0.0.1:28765"
        if edge_exe:
            cmd = [
                edge_exe,
                f"--app={url}",
                "--window-size=1080,720",
                "--disable-features=TranslateUI"
            ]
            self.edge_proc = subprocess.Popen(cmd)
        else:
            # Fallback to default browser
            import webbrowser
            webbrowser.open(url)

    def _display_loop(self):
        """High-performance frame streaming loop directly over WinUSB."""
        last_web_preview = 0

        while self.running:
            if not self.is_playing or not self.processor.frames:
                time.sleep(0.04)
                continue

            frame_data = self.processor.get_frame(self.current_frame_index)
            if not frame_data:
                time.sleep(0.04)
                continue

            # Overlay handling
            overlay_en = self.config.get("overlay_enabled", False)
            if overlay_en:
                stats = self.monitor.get_stats()
                pos = self.config.get("overlay_position", "bottom")
                pil_display, rgb565_bytes = self.processor.render_overlay_frame(
                    self.current_frame_index,
                    cpu_usage=stats["cpu_usage"],
                    cpu_temp=stats["gpu_temp"],
                    ram_usage=stats["ram_usage"],
                    position=pos
                )
            else:
                pil_display = frame_data.pil_image
                rgb565_bytes = frame_data.rgb565_bytes

            # 1. Send directly to hardware LCD over WinUSB
            self.driver.send_frame(rgb565_bytes)

            # 2. Update web preview image at ~10 FPS to minimize CPU
            now = time.time()
            if now - last_web_preview >= 0.10:
                last_web_preview = now
                self.server.set_preview_image(pil_display)

            # Advance frame
            self.current_frame_index = (self.current_frame_index + 1) % len(self.processor.frames)

            # Target frame sleep
            dur_sec = max(0.015, frame_data.duration_ms / 1000.0)
            time.sleep(dur_sec)

    def _run_tray(self):
        icon_path = os.path.join(SCRIPT_DIR, "assets", "app_icon.png")
        if os.path.exists(icon_path):
            img = Image.open(icon_path)
        else:
            img = Image.new("RGB", (64, 64), (0, 240, 255))

        menu = pystray.Menu(
            pystray.MenuItem("❄️ Mở Control Deck", lambda: self.open_window(), default=True),
            pystray.MenuItem("⏯️ Tạm dừng / Tiếp tục", self._toggle_play),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🛑 Thoát hoàn toàn", self.quit)
        )

        self.tray_icon = pystray.Icon("WarframeAIO", img, "Thermalright Warframe Control", menu)
        self.tray_icon.run()

    def _toggle_play(self, icon=None, item=None):
        self.is_playing = not self.is_playing

    def quit(self, icon=None, item=None):
        self.running = False
        if self.tray_icon:
            self.tray_icon.stop()
        if self.edge_proc and self.edge_proc.poll() is None:
            try:
                self.edge_proc.terminate()
            except Exception:
                pass
        self.driver.disconnect()
        self.monitor.stop()
        sys.exit(0)

def main():
    minimized = "--minimized" in sys.argv
    app = WarframeControllerApp()
    app.start(minimized=minimized)

if __name__ == "__main__":
    main()
