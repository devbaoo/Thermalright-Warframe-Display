"""
GIF and Image Processor for Thermalright Frozen Warframe LCD.
Handles frame extraction, transparency blending, resizing, rotation,
caching, and hardware metric overlays.
Thread-safe and guaranteed true WYSIWYG preview matching physical cooler display.
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
        self.rotation: int = 0          # 0, 90, 180, 270 degrees
        self.fit_mode: str = "fill"     # "fill", "fit", "stretch"
        self.brightness: float = 1.0    # 0.1 to 1.0
        self.fps_override: Optional[int] = 20

    def load_file(self, filepath: str, rotation: int = 0, fit_mode: str = "fill", brightness: float = 1.0, fps_override: Optional[int] = 20) -> bool:
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
        if rotation in (0, 90, 180, 270):
            with self._lock:
                if self.rotation == rotation:
                    return
                self.rotation = rotation
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

    def _get_logical_dimensions(self) -> Tuple[int, int]:
        """
        Returns (view_w, view_h) of what the user physically sees:
        0° and 180°: Landscape (320, 240)
        90° and 270°: Portrait (240, 320)
        """
        if self.rotation in (90, 270):
            return 240, 320
        return 320, 240

    def _scale_to_view(self, img: Image.Image, view_w: int, view_h: int) -> Image.Image:
        """Scales source image to logical viewable canvas according to fit_mode."""
        src_w, src_h = img.size

        if self.fit_mode == "stretch":
            return img.resize((view_w, view_h), Image.Resampling.BILINEAR)

        elif self.fit_mode == "fit":
            ratio = min(view_w / src_w, view_h / src_h)
            new_w = max(1, int(src_w * ratio))
            new_h = max(1, int(src_h * ratio))
            scaled = img.resize((new_w, new_h), Image.Resampling.BILINEAR)
            canvas = Image.new("RGB", (view_w, view_h), (0, 0, 0))
            ox = (view_w - new_w) // 2
            oy = (view_h - new_h) // 2
            canvas.paste(scaled, (ox, oy))
            return canvas

        else:  # "fill" (Center crop to prevent black bars)
            ratio = max(view_w / src_w, view_h / src_h)
            new_w = max(1, int(src_w * ratio))
            new_h = max(1, int(src_h * ratio))
            scaled = img.resize((new_w, new_h), Image.Resampling.BILINEAR)
            cx = (new_w - view_w) // 2
            cy = (new_h - view_h) // 2
            return scaled.crop((cx, cy, cx + view_w, cy + view_h))

    def _map_view_to_hardware(self, view_img: Image.Image) -> Image.Image:
        """
        Maps the logical viewable image (what user sees) to the physical 240x320 panel raster.
        Panel physical scanline order is 240x320 portrait:
          - At 0° (Landscape standard): rotate 270° (90° clockwise) -> (240, 320)
          - At 180° (Landscape inverted): rotate 90° (90° counter-clockwise) -> (240, 320)
          - At 90° (Portrait standard): image is (240, 320) -> no rotation
          - At 270° (Portrait inverted): image is (240, 320) -> rotate 180° -> (240, 320)
        """
        if self.rotation == 0:
            hw = view_img.rotate(270, expand=True)
        elif self.rotation == 180:
            hw = view_img.rotate(90, expand=True)
        elif self.rotation == 90:
            hw = view_img
        elif self.rotation == 270:
            hw = view_img.rotate(180)
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
        """Thread-safe batch pre-processing of all frames."""
        with self._lock:
            orig_frames = list(self.original_frames)
            durations = list(self.frame_durations)
            fps_override = self.fps_override

        if not orig_frames:
            return

        view_w, view_h = self._get_logical_dimensions()
        override_dur_ms = int(1000 / fps_override) if fps_override and fps_override > 0 else None

        new_frames = []
        for idx, orig in enumerate(orig_frames):
            # 1. Scale into logical viewable size
            view_img = self._scale_to_view(orig, view_w, view_h)

            # 2. Map logical viewable to physical 240x320 panel
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

    def render_overlay_frame(self, index: int, cpu_usage: float = 0.0, cpu_temp: Optional[float] = None, ram_usage: float = 0.0, position: str = "bottom") -> Tuple[Image.Image, bytes]:
        """
        Renders hardware overlay on top of logical frame, then maps to hardware raster.
        Guarantees text is right-side up and positioned identically on preview and LCD.
        Returns: (wysiwyg_preview_image, rgb565_bytes)
        """
        frame = self.get_frame(index)
        if not frame:
            blank = Image.new("RGB", (PANEL_W, PANEL_H), (0, 0, 0))
            return blank, self._pil_to_rgb565(blank)

        # Clone logical viewable image
        preview_img = frame.preview_image.copy()
        draw = ImageDraw.Draw(preview_img)
        view_w, view_h = preview_img.size

        # Build stats text
        parts = [f"CPU: {cpu_usage:.0f}%"]
        if cpu_temp is not None and cpu_temp > 0:
            parts.append(f"{cpu_temp:.0f}°C")
        parts.append(f"RAM: {ram_usage:.0f}%")
        stats_text = " | ".join(parts)

        # Calculate banner positioning in logical viewable coordinates
        banner_h = 24
        pad_x = 12
        if position == "top":
            banner_y = 8
        elif position == "center":
            banner_y = (view_h - banner_h) // 2
        else:  # "bottom"
            banner_y = view_h - banner_h - 8

        pill_rect = [pad_x, banner_y, view_w - pad_x, banner_y + banner_h]

        # Draw clean dark pill with subtle border
        draw.rounded_rectangle(pill_rect, radius=6, fill=(12, 16, 24, 215), outline=(59, 130, 246, 230), width=1)
        
        # Draw centered stats text
        # PIL text size approximation
        text_bbox = draw.textbbox((0, 0), stats_text)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
        text_x = (view_w - text_w) // 2
        text_y = banner_y + (banner_h - text_h) // 2 - 1
        draw.text((text_x, text_y), stats_text, fill=(245, 247, 250))

        # Map composite logical image to hardware LCD raster
        hw_img = self._map_view_to_hardware(preview_img)
        rgb565 = self._pil_to_rgb565(hw_img)

        return preview_img, rgb565
