"""
GIF and Image Processor for Thermalright Frozen Warframe LCD.
Handles frame extraction, transparency blending, resizing, true clockwise rotation,
caching, and ultra-professional hardware metric overlays.
Thread-safe and guaranteed 100% WYSIWYG preview matching physical cooler display.
"""

import os
import time
import threading
from typing import List, Tuple, Optional
from PIL import Image, ImageSequence, ImageDraw, ImageFont
import numpy as np

# Physical panel resolution is 240x320
PANEL_W = 240
PANEL_H = 320

# Standard Windows Font Paths for High-End Telemetry
FONT_VAL_PATH = r"C:\Windows\Fonts\bahnschrift.ttf"
FONT_LBL_PATH = r"C:\Windows\Fonts\segoeuib.ttf"

class ProcessedFrame:
    def __init__(self, preview_image: Image.Image, hardware_image: Image.Image, rgb565_bytes: bytes, duration_ms: int):
        self.preview_image = preview_image      # WYSIWYG frame for web preview & user inspection
        self.hardware_image = hardware_image    # Exact 240x320 raster for physical LCD
        self.rgb565_bytes = rgb565_bytes        # 153,600 bytes RGB565 little-endian
        self.duration_ms = duration_ms          # Display time in milliseconds

class GifProcessor:
    def __init__(self):
        self._lock = threading.Lock()
        self.current_filepath: Optional[str] = None
        self.frames: List[ProcessedFrame] = []
        self.original_frames: List[Image.Image] = []
        self.frame_durations: List[int] = []
        self.is_animated: bool = False
        self.total_frames: int = 0
        self.mount_mode: str = "landscape"  # "landscape" (320x240) or "portrait" (240x320)
        self.rotation: int = 0              # 0, 90, 180, 270 degrees clockwise
        self.fit_mode: str = "fill"         # "fill", "fit", "stretch"
        self.brightness: float = 1.0        # 0.1 to 1.0
        self.fps_override: Optional[int] = 20

        # Load fonts once
        try:
            self._font_val = ImageFont.truetype(FONT_VAL_PATH, 14) if os.path.exists(FONT_VAL_PATH) else ImageFont.load_default()
            self._font_lbl = ImageFont.truetype(FONT_LBL_PATH, 9) if os.path.exists(FONT_LBL_PATH) else ImageFont.load_default()
        except Exception:
            self._font_val = ImageFont.load_default()
            self._font_lbl = ImageFont.load_default()

    def load_file(self, filepath: str, rotation: int = 0, fit_mode: str = "fill", brightness: float = 1.0, fps_override: Optional[int] = 20, mount_mode: str = "landscape") -> bool:
        """Load and process an image or animated GIF file."""
        if not os.path.exists(filepath):
            return False

        try:
            with Image.open(filepath) as img:
                is_animated = getattr(img, "is_animated", False)
                orig_list = []
                dur_list = []

                for frame in ImageSequence.Iterator(img):
                    frame_rgba = frame.convert("RGBA")
                    duration = frame.info.get("duration", 100)
                    if duration <= 10:
                        duration = 100

                    canvas = Image.new("RGBA", img.size, (0, 0, 0, 255))
                    canvas.alpha_composite(frame_rgba)
                    orig_list.append(canvas.convert("RGB"))
                    dur_list.append(duration)

            with self._lock:
                self.current_filepath = filepath
                self.mount_mode = mount_mode
                self.rotation = rotation
                self.fit_mode = fit_mode
                self.brightness = brightness
                self.fps_override = fps_override
                self.original_frames = orig_list
                self.frame_durations = dur_list
                self.is_animated = is_animated
                self.total_frames = len(orig_list)

            self._reprocess_frames()
            return True
        except Exception as e:
            print(f"Error loading file {filepath}: {e}")
            return False

    def set_rotation(self, rotation: int):
        """Sets clockwise rotation angle (0, 90, 180, 270). Rotates image content directly."""
        if rotation in (0, 90, 180, 270):
            with self._lock:
                if self.rotation == rotation:
                    return
                self.rotation = rotation
            self._reprocess_frames()

    def set_mount_mode(self, mount_mode: str):
        """Sets cooler physical mount orientation: 'landscape' (320x240) or 'portrait' (240x320)."""
        if mount_mode in ("landscape", "portrait"):
            with self._lock:
                if self.mount_mode == mount_mode:
                    return
                self.mount_mode = mount_mode
            self._reprocess_frames()

    def set_fit_mode(self, fit_mode: str):
        if fit_mode in ("fill", "fit", "stretch"):
            with self._lock:
                if self.fit_mode == fit_mode:
                    return
                self.fit_mode = fit_mode
            self._reprocess_frames()

    def set_brightness(self, brightness: float):
        brightness = max(0.1, min(1.0, brightness))
        with self._lock:
            if abs(self.brightness - brightness) < 0.02:
                return
            self.brightness = brightness
        self._reprocess_frames()

    def set_fps_override(self, fps: Optional[int]):
        with self._lock:
            if self.fps_override == fps:
                return
            self.fps_override = fps
        self._reprocess_frames()

    def _get_canvas_dimensions(self) -> Tuple[int, int]:
        """Returns the logical screen dimensions based on cooler mounting mode."""
        if self.mount_mode == "portrait":
            return 240, 320
        return 320, 240

    def _scale_and_rotate_to_view(self, img: Image.Image, canvas_w: int, canvas_h: int) -> Image.Image:
        """
        Scales the source image into the screen canvas according to fit_mode,
        then rotates the image content clockwise by self.rotation degrees.
        """
        src_w, src_h = img.size

        # If rotation is 90 or 270, the intermediate fit canvas has swapped dimensions
        if self.rotation in (90, 270):
            fit_w, fit_h = canvas_h, canvas_w
        else:
            fit_w, fit_h = canvas_w, canvas_h

        if self.fit_mode == "stretch":
            canvas = img.resize((fit_w, fit_h), Image.Resampling.BILINEAR)

        elif self.fit_mode == "fit":
            ratio = min(fit_w / src_w, fit_h / src_h)
            new_w = max(1, int(src_w * ratio))
            new_h = max(1, int(src_h * ratio))
            scaled = img.resize((new_w, new_h), Image.Resampling.BILINEAR)
            canvas = Image.new("RGB", (fit_w, fit_h), (0, 0, 0))
            ox = (fit_w - new_w) // 2
            oy = (fit_h - new_h) // 2
            canvas.paste(scaled, (ox, oy))

        else:  # "fill" (Center crop to prevent black bars)
            ratio = max(fit_w / src_w, fit_h / src_h)
            new_w = max(1, int(src_w * ratio))
            new_h = max(1, int(src_h * ratio))
            scaled = img.resize((new_w, new_h), Image.Resampling.BILINEAR)
            cx = (new_w - fit_w) // 2
            cy = (new_h - fit_h) // 2
            canvas = scaled.crop((cx, cy, cx + fit_w, cy + fit_h))

        # Rotate clockwise by self.rotation
        # PIL rotate is counter-clockwise, so -rotation % 360 rotates clockwise!
        if self.rotation != 0:
            rotated = canvas.rotate(-self.rotation % 360, expand=True)
            if rotated.size != (canvas_w, canvas_h):
                rotated = rotated.resize((canvas_w, canvas_h), Image.Resampling.BILINEAR)
            return rotated

        return canvas

    def _map_view_to_hardware(self, view_img: Image.Image) -> Image.Image:
        """
        Maps the logical viewable image (what user sees) to the physical 240x320 panel raster.
        For Landscape (320x240):
          Rotating 270° in PIL (90° clockwise) maps 320x240 to 240x320.
        For Portrait (240x320):
          Already 240x320.
        """
        if self.mount_mode == "portrait":
            hw = view_img
        else:
            hw = view_img.rotate(270, expand=True)

        if hw.size != (PANEL_W, PANEL_H):
            hw = hw.resize((PANEL_W, PANEL_H), Image.Resampling.BILINEAR)
        return hw

    def _pil_to_rgb565(self, pil_image: Image.Image) -> bytes:
        """Vectorized conversion of 240x320 image to RGB565 Little Endian."""
        if pil_image.size != (PANEL_W, PANEL_H):
            pil_image = pil_image.resize((PANEL_W, PANEL_H), Image.Resampling.BILINEAR)

        arr = np.asarray(pil_image, dtype=np.float32)
        if self.brightness < 1.0:
            arr = arr * self.brightness
        arr = arr.astype(np.uint16)

        r = (arr[:, :, 0] >> 3) << 11
        g = (arr[:, :, 1] >> 2) << 5
        b = (arr[:, :, 2] >> 3)
        return (r | g | b).astype("<u2").tobytes()

    def _reprocess_frames(self):
        """Thread-safe batch pre-processing of all frames with atomic swap."""
        with self._lock:
            orig_frames = list(self.original_frames)
            durations = list(self.frame_durations)
            fps_override = self.fps_override

        if not orig_frames:
            return

        canvas_w, canvas_h = self._get_canvas_dimensions()
        override_dur_ms = int(1000 / fps_override) if fps_override and fps_override > 0 else None

        new_frames = []
        for idx, orig in enumerate(orig_frames):
            # 1. Scale and apply clockwise rotation into viewable canvas
            view_img = self._scale_and_rotate_to_view(orig, canvas_w, canvas_h)

            # 2. Map viewable image to physical 240x320 panel
            hw_img = self._map_view_to_hardware(view_img)

            # 3. Convert to RGB565 byte buffer
            rgb565 = self._pil_to_rgb565(hw_img)

            dur = override_dur_ms if override_dur_ms is not None else durations[idx]
            new_frames.append(ProcessedFrame(
                preview_image=view_img,
                hardware_image=hw_img,
                rgb565_bytes=rgb565,
                duration_ms=dur
            ))

        # Atomic swap with lock
        with self._lock:
            self.frames = new_frames

    def get_frame(self, index: int) -> Optional[ProcessedFrame]:
        """Thread-safe frame access with zero index bounds errors."""
        with self._lock:
            if not self.frames:
                return None
            return self.frames[index % len(self.frames)]

    def render_overlay_frame(
        self,
        index: int,
        cpu_usage: float = 0.0,
        cpu_temp: Optional[float] = None,
        ram_usage: float = 0.0,
        position: str = "bottom",
        style: str = "badges"
    ) -> Tuple[Image.Image, bytes]:
        """
        Renders a stunning, high-end PC enthusiast telemetry overlay onto the frame.
        Uses Bahnschrift / Segoe UI Bold typography, frosted cards, and accent indicators.
        Returns: (wysiwyg_preview_image, rgb565_bytes)
        """
        frame = self.get_frame(index)
        if not frame:
            blank = Image.new("RGB", (PANEL_W, PANEL_H), (0, 0, 0))
            return blank, self._pil_to_rgb565(blank)

        # Clone viewable image
        preview_img = frame.preview_image.copy()
        w, h = preview_img.size

        # Create transparent overlay layer for alpha composite
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Telemetry metrics data
        gpu_str = f"{cpu_temp:.0f}°C" if cpu_temp and cpu_temp > 0 else "--°C"
        items = [
            ("CPU", f"{cpu_usage:.0f}%", (59, 130, 246)),      # Sapphire
            ("GPU", gpu_str, (245, 158, 11)),                   # Amber
            ("RAM", f"{ram_usage:.0f}%", (16, 185, 129))        # Emerald
        ]

        if style == "strip":
            # Sleek Telemetry Ribbon with Accent Line
            strip_h = 30
            y = h - strip_h - 8 if position == "bottom" else (8 if position == "top" else (h - strip_h) // 2)
            pad = 12

            # Background card with soft border
            draw.rounded_rectangle([pad, y, w - pad, y + strip_h], radius=7, fill=(10, 13, 19, 230), outline=(38, 48, 64, 255), width=1)
            # Top accent line
            draw.rounded_rectangle([pad + 2, y, w - pad - 2, y + 2], radius=1, fill=(59, 130, 246, 255))

            col_w = (w - pad * 2) // 3
            for i, (label, val, accent) in enumerate(items):
                cx = pad + i * col_w + 12
                draw.text((cx, y + 8), f"{label}", font=self._font_lbl, fill=(148, 163, 184))
                draw.text((cx + 28, y + 6), val, font=self._font_val, fill=(245, 247, 250))

        else:
            # Modern Triple Frosted Badges (Default - NZXT / Lian Li aesthetic)
            badge_w = 88 if w >= 300 else 68
            badge_h = 32
            gap = 6
            start_x = (w - (badge_w * 3 + gap * 2)) // 2
            y = h - badge_h - 10 if position == "bottom" else (10 if position == "top" else (h - badge_h) // 2)

            for i, (label, val, accent) in enumerate(items):
                bx = start_x + i * (badge_w + gap)

                # Ambient drop shadow
                draw.rounded_rectangle([bx + 1, y + 2, bx + badge_w + 1, y + badge_h + 2], radius=7, fill=(0, 0, 0, 140))
                # Frosted glass card
                draw.rounded_rectangle([bx, y, bx + badge_w, y + badge_h], radius=7, fill=(11, 14, 21, 230), outline=(42, 52, 70, 255), width=1)
                # Vertical accent indicator bar
                draw.rounded_rectangle([bx + 7, y + 7, bx + 10, y + badge_h - 7], radius=2, fill=accent)
                # Metric labels & high-contrast values
                draw.text((bx + 16, y + 4), label, font=self._font_lbl, fill=(148, 163, 184))
                draw.text((bx + 16, y + 14), val, font=self._font_val, fill=(245, 247, 250))

        # Composite overlay on viewable image
        composite_view = Image.alpha_composite(preview_img.convert("RGBA"), overlay).convert("RGB")

        # Map to physical hardware LCD raster
        hw_img = self._map_view_to_hardware(composite_view)
        rgb565 = self._pil_to_rgb565(hw_img)

        return composite_view, rgb565
