"""
GIF and Image Processor for Thermalright Frozen Warframe LCD.
Handles frame extraction, transparency blending, resizing, rotation,
caching, and hardware metric overlays.
"""

import os
import time
from typing import List, Tuple, Optional
from PIL import Image, ImageSequence, ImageDraw, ImageFont
import numpy as np

# Physical panel resolution is 240x320
PANEL_W = 240
PANEL_H = 320

# Standard logical display resolution (Landscape) is 320x240
LOGICAL_W = 320
LOGICAL_H = 240

class ProcessedFrame:
    def __init__(self, pil_image: Image.Image, rgb565_bytes: bytes, duration_ms: int):
        self.pil_image = pil_image          # 240x320 rotated image for preview or overlays
        self.rgb565_bytes = rgb565_bytes    # 153,600 bytes RGB565
        self.duration_ms = duration_ms      # Frame display time in milliseconds

class GifProcessor:
    def __init__(self):
        self.current_filepath: Optional[str] = None
        self.frames: List[ProcessedFrame] = []
        self.original_frames: List[Image.Image] = []
        self.frame_durations: List[int] = []
        self.is_animated: bool = False
        self.total_frames: int = 0
        self.rotation: int = 0          # 0, 90, 180, 270 degrees
        self.fit_mode: str = "fill"     # "fill", "fit", "stretch"
        self.brightness: float = 1.0    # 0.1 to 1.0
        self.fps_override: Optional[int] = None # None or 10, 15, 20, 24, 30

    def load_file(self, filepath: str, rotation: int = 0, fit_mode: str = "fill", brightness: float = 1.0, fps_override: Optional[int] = None) -> bool:
        """Load and process an image or animated GIF file."""
        if not os.path.exists(filepath):
            return False

        self.current_filepath = filepath
        self.rotation = rotation
        self.fit_mode = fit_mode
        self.brightness = brightness
        self.fps_override = fps_override
        self.original_frames.clear()
        self.frame_durations.clear()

        try:
            with Image.open(filepath) as img:
                self.is_animated = getattr(img, "is_animated", False)
                
                # Extract all frames, handling GIF palette and disposal
                last_frame = None
                for frame_idx, frame in enumerate(ImageSequence.Iterator(img)):
                    frame_rgba = frame.convert("RGBA")
                    
                    # GIF duration in ms
                    duration = frame.info.get("duration", 100)
                    if duration <= 10:  # Fix invalid durations
                        duration = 100
                    
                    # Create blank background canvas to compose onto
                    canvas = Image.new("RGBA", img.size, (0, 0, 0, 255))
                    canvas.alpha_composite(frame_rgba)
                    
                    self.original_frames.append(canvas.convert("RGB"))
                    self.frame_durations.append(duration)

            self.total_frames = len(self.original_frames)
            self._reprocess_frames()
            return True
        except Exception as e:
            print(f"Error loading file {filepath}: {e}")
            return False

    def set_rotation(self, rotation: int):
        if rotation in (0, 90, 180, 270) and rotation != self.rotation:
            self.rotation = rotation
            self._reprocess_frames()

    def set_fit_mode(self, fit_mode: str):
        if fit_mode in ("fill", "fit", "stretch") and fit_mode != self.fit_mode:
            self.fit_mode = fit_mode
            self._reprocess_frames()

    def set_brightness(self, brightness: float):
        brightness = max(0.1, min(1.0, brightness))
        if abs(self.brightness - brightness) > 0.02:
            self.brightness = brightness
            self._reprocess_frames()

    def set_fps_override(self, fps: Optional[int]):
        self.fps_override = fps
        self._reprocess_frames()

    def _transform_image(self, img: Image.Image) -> Image.Image:
        """
        Scales the source image into 320x240 logical canvas based on fit_mode,
        then rotates into 240x320 physical panel orientation.
        """
        src_w, src_h = img.size
        target_w, target_h = LOGICAL_W, LOGICAL_H  # 320 x 240

        if self.fit_mode == "stretch":
            canvas = img.resize((target_w, target_h), Image.Resampling.BILINEAR)
        elif self.fit_mode == "fit":
            # Letterbox: fit entirely inside 320x240, pad black borders
            ratio = min(target_w / src_w, target_h / src_h)
            new_w = max(1, int(src_w * ratio))
            new_h = max(1, int(src_h * ratio))
            scaled = img.resize((new_w, new_h), Image.Resampling.BILINEAR)
            canvas = Image.new("RGB", (target_w, target_h), (0, 0, 0))
            offset_x = (target_w - new_w) // 2
            offset_y = (target_h - new_h) // 2
            canvas.paste(scaled, (offset_x, offset_y))
        else:  # "fill" (Center crop)
            ratio = max(target_w / src_w, target_h / src_h)
            new_w = max(1, int(src_w * ratio))
            new_h = max(1, int(src_h * ratio))
            scaled = img.resize((new_w, new_h), Image.Resampling.BILINEAR)
            crop_x = (new_w - target_w) // 2
            crop_y = (new_h - target_h) // 2
            canvas = scaled.crop((crop_x, crop_y, crop_x + target_w, crop_y + target_h))

        # Rotate from 320x240 landscape to 240x320 physical panel
        # Base panel orientation requires 90 deg clockwise (-90 in PIL) to map 320x240 to 240x320
        total_rotation = (-90 - self.rotation) % 360
        rotated = canvas.rotate(total_rotation, expand=True)
        if rotated.size != (PANEL_W, PANEL_H):
            rotated = rotated.resize((PANEL_W, PANEL_H), Image.Resampling.NEAREST)

        return rotated

    def _pil_to_rgb565(self, pil_image: Image.Image) -> bytes:
        """Fast vectorized conversion of 240x320 image to RGB565."""
        arr = np.asarray(pil_image, dtype=np.float32)
        if self.brightness < 1.0:
            arr = arr * self.brightness
        arr = arr.astype(np.uint16)

        r = (arr[:, :, 0] >> 3) << 11
        g = (arr[:, :, 1] >> 2) << 5
        b = (arr[:, :, 2] >> 3)
        return (r | g | b).astype("<u2").tobytes()

    def _reprocess_frames(self):
        """Pre-processes and caches all frames in memory."""
        self.frames.clear()
        
        override_dur_ms = int(1000 / self.fps_override) if self.fps_override and self.fps_override > 0 else None

        for idx, orig_img in enumerate(self.original_frames):
            transformed = self._transform_image(orig_img)
            rgb565 = self._pil_to_rgb565(transformed)
            dur = override_dur_ms if override_dur_ms is not None else self.frame_durations[idx]
            self.frames.append(ProcessedFrame(transformed, rgb565, dur))

    def get_frame(self, index: int) -> Optional[ProcessedFrame]:
        if not self.frames:
            return None
        return self.frames[index % len(self.frames)]

    def render_overlay_frame(self, index: int, cpu_usage: float = 0.0, cpu_temp: Optional[float] = None, ram_usage: float = 0.0, position: str = "bottom") -> Tuple[Image.Image, bytes]:
        """
        Renders hardware overlay on top of frame dynamically.
        Returns: (display_pil_image, rgb565_bytes)
        """
        frame = self.get_frame(index)
        if not frame:
            blank = Image.new("RGB", (PANEL_W, PANEL_H), (0, 0, 0))
            return blank, self._pil_to_rgb565(blank)

        # Clone image to draw overlay
        img = frame.pil_image.copy()
        draw = ImageDraw.Draw(img)

        # Build stats text
        parts = [f"CPU: {cpu_usage:.0f}%"]
        if cpu_temp is not None and cpu_temp > 0:
            parts.append(f"{cpu_temp:.0f}°C")
        parts.append(f"RAM: {ram_usage:.0f}%")
        stats_text = " | ".join(parts)

        # Draw semi-transparent pill banner
        # Position mapping
        text_y = 280 if position == "bottom" else (20 if position == "top" else 150)
        pill_rect = [10, text_y - 4, PANEL_W - 10, text_y + 20]
        
        # Draw background pill
        draw.rounded_rectangle(pill_rect, radius=6, fill=(10, 10, 15, 200), outline=(0, 200, 255))
        draw.text((25, text_y), stats_text, fill=(255, 255, 255))

        rgb565 = self._pil_to_rgb565(img)
        return img, rgb565

