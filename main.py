"""
Thermalright Warframe 360 SE - Pro Max Application Main Entry.
Starts the high-efficiency display driver, hardware monitor, embedded API server,
and launches the sleek Standalone Desktop Control Deck.
Includes bulletproof single-instance handling and multi-browser support.
"""

import sys
import os
import time
import socket
import logging
import tempfile
import threading
import subprocess
import urllib.request
import webbrowser
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

LOG_FILE = os.path.join(SCRIPT_DIR, "app.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("WarframeApp")

try:
    import pystray
except ImportError:
    pystray = None

from display_driver import WarframeDisplayDriver
from gif_processor import GifProcessor
from system_monitor import SystemMonitor
from config_manager import ConfigManager
from web_ui import WebUIServer

PORT = 28765

BROWSER_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

def is_server_alive(port=PORT, timeout=0.8) -> bool:
    """Check if the local embedded web server is already listening and responding."""
    try:
        url = f"http://127.0.0.1:{port}/api/status"
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False

def request_open_window(port=PORT) -> bool:
    """Ask existing instance to focus/open its UI window."""
    try:
        url = f"http://127.0.0.1:{port}/api/open_window"
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False

def wait_for_server(port=PORT, max_wait=3.0) -> bool:
    """Wait until embedded web server socket is active."""
    start = time.time()
    while time.time() - start < max_wait:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(0.08)
    return False

def launch_browser_app(url=f"http://127.0.0.1:{PORT}"):
    """Launch standalone app window via Edge or Chrome, fallback to default browser."""
    browser_exe = None
    for p in BROWSER_PATHS:
        if os.path.exists(p):
            browser_exe = p
            break

    if browser_exe:
        profile_dir = os.path.join(tempfile.gettempdir(), "WarframeAIO_EdgeApp")
        cmd = [
            browser_exe,
            f"--app={url}",
            f"--user-data-dir={profile_dir}",
            "--window-size=1080,720",
            "--disable-features=TranslateUI"
        ]
        try:
            return subprocess.Popen(cmd)
        except Exception as e:
            logger.warning(f"Failed to launch standalone browser {browser_exe}: {e}")

    try:
        webbrowser.open(url)
    except Exception as e:
        logger.error(f"Failed to open browser URL: {e}")
    return None

class WarframeControllerApp:
    def __init__(self):
        self.driver = WarframeDisplayDriver()
        self.processor = GifProcessor()
        self.monitor = SystemMonitor(interval=1.5)
        self.config = ConfigManager()
        self.server = WebUIServer(
            self.driver,
            self.processor,
            self.monitor,
            self.config,
            port=PORT,
            on_open_window=self.open_window
        )

        self.running = True
        self.is_playing = True
        self.current_frame_index = 0
        self.browser_proc = None
        self.tray_icon = None

        # Load last used file or default core preset
        last_file = self.config.get("last_file", "")
        if not last_file or not os.path.exists(last_file):
            last_file = os.path.join(SCRIPT_DIR, "assets", "sample_core.gif")

        rot = self.config.get("rotation", 0)
        fit = self.config.get("fit_mode", "fill")
        fps = self.config.get("fps_override", 20)
        bri = self.config.get("brightness", 1.0)
        mount = self.config.get("mount_mode", "landscape")
        if os.path.exists(last_file):
            self.processor.load_file(last_file, rotation=rot, fit_mode=fit, brightness=bri, fps_override=fps, mount_mode=mount)

    def start(self, minimized=False):
        logger.info("Initializing Thermalright Frozen Warframe Controller...")

        # 1. Connect to display hardware
        connected = self.driver.connect()
        if not connected:
            logger.warning("Warframe display hardware not detected or in use. Will keep retrying in background.")

        # 2. Start hardware monitor
        self.monitor.start()

        # 3. Start embedded API server
        self.server.start()

        # 4. Wait for web server to bind
        server_ready = wait_for_server(port=PORT, max_wait=3.0)
        if not server_ready:
            logger.warning("Web server socket took longer than expected to bind.")

        # 5. Start background display streaming loop
        threading.Thread(target=self._display_loop, daemon=True).start()

        # 6. Launch Standalone App window if not minimized
        if not minimized:
            self.open_window()

        # 7. Start system tray on main thread or keep process alive
        self._run_tray_or_wait()

    def open_window(self):
        """Open or refocus the standalone Control Deck Window."""
        self.browser_proc = launch_browser_app(f"http://127.0.0.1:{PORT}")

    def _display_loop(self):
        """High-performance frame streaming loop directly over WinUSB."""
        last_web_preview = 0

        while self.running:
            try:
                if not self.is_playing:
                    time.sleep(0.05)
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
                    style = self.config.get("overlay_style", "badges")
                    pil_preview, rgb565_bytes = self.processor.render_overlay_frame(
                        self.current_frame_index,
                        cpu_usage=stats["cpu_usage"],
                        cpu_temp=stats["gpu_temp"],
                        ram_usage=stats["ram_usage"],
                        position=pos,
                        style=style
                    )
                else:
                    pil_preview = frame_data.preview_image
                    rgb565_bytes = frame_data.rgb565_bytes

                # 1. Send directly to hardware LCD over WinUSB if connected
                if not self.driver.is_connected():
                    # Attempt background reconnect every 2s
                    if time.time() - self.driver.last_send_time > 2.0:
                        self.driver.connect()
                else:
                    self.driver.send_frame(rgb565_bytes)

                # 2. Update web preview image at ~10 FPS to minimize CPU
                now = time.time()
                if now - last_web_preview >= 0.10:
                    last_web_preview = now
                    self.server.set_preview_image(pil_preview)

                # Advance frame
                total = len(self.processor.frames)
                if total > 0:
                    self.current_frame_index = (self.current_frame_index + 1) % total

                # Target frame sleep
                dur_sec = max(0.015, frame_data.duration_ms / 1000.0)
                time.sleep(dur_sec)

            except Exception as e:
                logger.error(f"Error in display streaming loop: {e}")
                time.sleep(0.05)

    def _run_tray_or_wait(self):
        if pystray is None:
            self._keep_alive_loop()
            return

        icon_path = os.path.join(SCRIPT_DIR, "assets", "app_icon.png")
        if os.path.exists(icon_path):
            try:
                img = Image.open(icon_path)
            except Exception:
                img = Image.new("RGB", (64, 64), (0, 240, 255))
        else:
            img = Image.new("RGB", (64, 64), (0, 240, 255))

        menu = pystray.Menu(
            pystray.MenuItem("❄️ Mở Control Deck", lambda: self.open_window(), default=True),
            pystray.MenuItem("⏯️ Tạm dừng / Tiếp tục", self._toggle_play),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🛑 Thoát hoàn toàn", self.quit)
        )

        try:
            self.tray_icon = pystray.Icon("WarframeAIO", img, "Thermalright Warframe Control", menu)
            # Run tray loop on main thread (handles Win32 window messages smoothly)
            self.tray_icon.run()
        except Exception as e:
            logger.warning(f"System tray icon could not be displayed: {e}")
            self._keep_alive_loop()

    def _keep_alive_loop(self):
        try:
            while self.running:
                time.sleep(1.0)
        except KeyboardInterrupt:
            self.quit()

    def _toggle_play(self, icon=None, item=None):
        self.is_playing = not self.is_playing

    def quit(self, icon=None, item=None):
        logger.info("Stopping Warframe Controller...")
        self.running = False
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        if self.browser_proc and self.browser_proc.poll() is None:
            try:
                self.browser_proc.terminate()
            except Exception:
                pass
        self.driver.disconnect()
        self.monitor.stop()
        sys.exit(0)

def main():
    minimized = "--minimized" in sys.argv

    # Check for single instance: is app already running on port 28765?
    if is_server_alive():
        logger.info("Found existing Warframe Display instance already active.")
        if not minimized:
            # Wake up window on existing instance
            woken = request_open_window()
            if not woken:
                launch_browser_app()
            time.sleep(0.5)
        sys.exit(0)

    try:
        app = WarframeControllerApp()
        app.start(minimized=minimized)
    except Exception as e:
        logger.critical(f"Fatal error starting WarframeController: {e}", exc_info=True)
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f"Lỗi khi khởi động ứng dụng:\n\n{e}\n\nVui lòng xem file app.log để biết chi tiết.",
                "Thermalright Warframe Display Error",
                0x10
            )
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
