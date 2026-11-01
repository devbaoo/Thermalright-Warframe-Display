"""
Embedded Web Server & API Bridge for Thermalright Warframe Pro Max UI.
Powered by Bottle (lightweight, zero-overhead, in-process).
"""

import os
import io
import json
import threading
import tkinter as tk
from tkinter import filedialog
from bottle import Bottle, request, response, static_file
from PIL import Image

class WebUIServer:
    def __init__(self, driver, processor, monitor, config, port=28765):
        self.driver = driver
        self.processor = processor
        self.monitor = monitor
        self.config = config
        self.port = port
        self.app = Bottle()
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.web_dir = os.path.join(self.base_dir, "web")
        self.assets_dir = os.path.join(self.base_dir, "assets")
        self.current_preview_jpeg = b""
        self._lock = threading.Lock()

        self._setup_routes()

    def set_preview_image(self, pil_image: Image.Image):
        """Called by background playback loop to keep browser preview updated."""
        try:
            buf = io.BytesIO()
            pil_image.save(buf, format="JPEG", quality=85)
            with self._lock:
                self.current_preview_jpeg = buf.getvalue()
        except Exception:
            pass

    def _setup_routes(self):
        app = self.app

        @app.route("/")
        def index():
            return static_file("index.html", root=self.web_dir)

        @app.route("/assets/<filepath:path>")
        def serve_assets(filepath):
            return static_file(filepath, root=self.assets_dir)

        @app.route("/api/status")
        def get_status():
            response.content_type = "application/json"
            stats = self.monitor.get_stats()
            trcc_running = self.config.is_trcc_running()
            
            last_file = self.config.get("last_file", "")
            file_name = os.path.basename(last_file) if last_file else "sample_core.gif"
            
            presets = [
                {"id": "sample_core", "name": "Sci-Fi Plasma Core", "file": "assets/sample_core.gif"},
                {"id": "matrix_rain", "name": "Matrix Digital Rain", "file": "assets/presets/matrix_rain.gif"},
                {"id": "synthwave", "name": "Synthwave Horizon", "file": "assets/presets/synthwave.gif"},
                {"id": "radar_telemetry", "name": "AIO Radar Telemetry", "file": "assets/presets/radar_telemetry.gif"}
            ]

            return json.dumps({
                "connected": self.driver.is_connected(),
                "device_name": "Thermalright Frozen Warframe 360 SE",
                "device_id": "0416:5302",
                "file_name": file_name,
                "total_frames": self.processor.total_frames,
                "rotation": self.config.get("rotation", 0),
                "fit_mode": self.config.get("fit_mode", "fill"),
                "fps": self.config.get("fps_override", 20),
                "brightness": int(self.config.get("brightness", 1.0) * 100),
                "overlay_enabled": self.config.get("overlay_enabled", False),
                "overlay_position": self.config.get("overlay_position", "bottom"),
                "autostart": self.config.get("autostart", False),
                "trcc_running": trcc_running,
                "stats": stats,
                "presets": presets
            })

        @app.route("/api/preview")
        def get_preview():
            response.content_type = "image/jpeg"
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            with self._lock:
                return self.current_preview_jpeg

        @app.route("/api/set_rotation", method="POST")
        def set_rotation():
            data = request.json or {}
            rot = int(data.get("rotation", 0))
            self.processor.set_rotation(rot)
            self.config.set("rotation", rot)
            return {"status": "ok", "rotation": rot}

        @app.route("/api/set_fit_mode", method="POST")
        def set_fit():
            data = request.json or {}
            fit = data.get("fit_mode", "fill")
            self.processor.set_fit_mode(fit)
            self.config.set("fit_mode", fit)
            return {"status": "ok", "fit_mode": fit}

        @app.route("/api/set_fps", method="POST")
        def set_fps():
            data = request.json or {}
            fps = int(data.get("fps", 20))
            self.processor.set_fps_override(fps)
            self.config.set("fps_override", fps)
            return {"status": "ok", "fps": fps}

        @app.route("/api/set_brightness", method="POST")
        def set_brightness():
            data = request.json or {}
            bri_pct = int(data.get("brightness", 100))
            self.processor.set_brightness(bri_pct / 100.0)
            self.config.set("brightness", bri_pct / 100.0)
            return {"status": "ok", "brightness": bri_pct}

        @app.route("/api/set_overlay", method="POST")
        def set_overlay():
            data = request.json or {}
            enabled = bool(data.get("enabled", False))
            pos = data.get("position", "bottom")
            self.config.set("overlay_enabled", enabled)
            self.config.set("overlay_position", pos)
            return {"status": "ok", "enabled": enabled, "position": pos}

        @app.route("/api/select_preset", method="POST")
        def select_preset():
            data = request.json or {}
            preset_id = data.get("id")
            mapping = {
                "sample_core": os.path.join(self.assets_dir, "sample_core.gif"),
                "matrix_rain": os.path.join(self.assets_dir, "presets", "matrix_rain.gif"),
                "synthwave": os.path.join(self.assets_dir, "presets", "synthwave.gif"),
                "radar_telemetry": os.path.join(self.assets_dir, "presets", "radar_telemetry.gif"),
            }
            target = mapping.get(preset_id)
            if target and os.path.exists(target):
                self._load_file(target)
                return {"status": "ok", "file": target}
            return {"status": "error", "message": "Preset not found"}

        @app.route("/api/browse_file", method="POST")
        def browse_file():
            # Run tkinter file dialog in a helper thread to avoid COM/threading blocks
            result = {"path": None}
            def _ask():
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                p = filedialog.askopenfilename(
                    title="Chọn GIF hoặc Ảnh cho tản nhiệt Warframe 360",
                    filetypes=[
                        ("Hình ảnh & GIF", "*.gif;*.png;*.jpg;*.jpeg;*.webp;*.bmp"),
                        ("Ảnh GIF động", "*.gif"),
                        ("Tất cả tệp", "*.*")
                    ]
                )
                root.destroy()
                result["path"] = p

            t = threading.Thread(target=_ask)
            t.start()
            t.join()

            if result["path"]:
                self._load_file(result["path"])
                return {"status": "ok", "path": result["path"], "filename": os.path.basename(result["path"])}
            return {"status": "cancelled"}

        @app.route("/api/upload_file", method="POST")
        def upload_file():
            upload = request.files.get("file")
            if not upload:
                return {"status": "error", "message": "No file uploaded"}
            
            user_dir = os.path.join(self.base_dir, "assets", "user_uploads")
            os.makedirs(user_dir, exist_ok=True)
            save_path = os.path.join(user_dir, upload.filename)
            upload.save(save_path, overwrite=True)
            self._load_file(save_path)
            return {"status": "ok", "path": save_path, "filename": upload.filename}

        @app.route("/api/kill_trcc", method="POST")
        def kill_trcc():
            killed = self.config.kill_trcc_processes()
            return {"status": "ok", "killed_count": killed}

        @app.route("/api/set_autostart", method="POST")
        def set_autostart():
            data = request.json or {}
            enabled = bool(data.get("enabled", False))
            self.config.set_autostart(enabled)
            return {"status": "ok", "autostart": enabled}

    def _load_file(self, path: str):
        rot = self.config.get("rotation", 0)
        fit = self.config.get("fit_mode", "fill")
        fps = self.config.get("fps_override", 20)
        bri = self.config.get("brightness", 1.0)
        if self.processor.load_file(path, rotation=rot, fit_mode=fit, brightness=bri, fps_override=fps):
            self.config.set("last_file", path)

    def start(self):
        t = threading.Thread(target=lambda: self.app.run(host="127.0.0.1", port=self.port, quiet=True), daemon=True)
        t.start()
        return t
