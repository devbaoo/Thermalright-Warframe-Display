"""
Display Driver for Thermalright Frozen Warframe 360 SE / HID Type 2 Displays (VID 0x0416, PID 0x5302)
Connects directly via WinUSB / libusb-package bulk transfers.
"""

import struct
import time
import logging
import ctypes
import numpy as np
from PIL import Image

try:
    import libusb_package
    import usb.core
    import usb.util
except ImportError:
    libusb_package = None
    usb = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DisplayDriver")

VID = 0x0416
PID = 0x5302
EP_WRITE = 0x02
EP_READ = 0x81
USB_CHUNK_SIZE = 512
PANEL_WIDTH = 240
PANEL_HEIGHT = 320
PAYLOAD_SIZE = PANEL_WIDTH * PANEL_HEIGHT * 2  # 153,600 bytes RGB565
TOTAL_PACKET_SIZE = 154112

# Type 2 magic bytes
MAGIC_HEADER = bytes([0xDA, 0xDB, 0xDC, 0xDD])

class WarframeDisplayDriver:
    def __init__(self):
        self.device = None
        self.connected = False
        self.last_send_time = 0
        
        # Direct ctypes fast-path handles
        self._dev_handle = None
        self._fn_interrupt = None
        self._c_transferred = ctypes.c_long(0)
        self._c_transferred_ptr = ctypes.byref(self._c_transferred)
        
        # Pre-allocate reusable 154,112-byte C buffer and chunk pointers for zero GC overhead
        self._c_buf = (ctypes.c_ubyte * TOTAL_PACKET_SIZE)()
        base_addr = ctypes.addressof(self._c_buf)
        self._c_ptrs = [
            ctypes.cast(base_addr + offset, ctypes.POINTER(ctypes.c_ubyte))
            for offset in range(0, TOTAL_PACKET_SIZE, USB_CHUNK_SIZE)
        ]

    def connect(self) -> bool:
        """Find and initialize the USB device."""
        if libusb_package is None or usb is None:
            logger.error("libusb_package or pyusb is not installed.")
            return False

        try:
            self.device = libusb_package.find(idVendor=VID, idProduct=PID)
            if self.device is None:
                logger.warning(f"Device {hex(VID)}:{hex(PID)} not found.")
                self.connected = False
                return False

            try:
                self.device.set_configuration()
            except Exception as e:
                logger.debug(f"set_configuration info: {e}")

            # Extract underlying libusb C handle for fast zero-overhead transfers
            try:
                self._dev_handle = self.device._ctx.handle.handle
                self._fn_interrupt = self.device._ctx.backend.lib.libusb_interrupt_transfer
            except Exception as e:
                logger.warning(f"Fast-path handle extraction failed: {e}")
                self._dev_handle = None
                self._fn_interrupt = None

            self.connected = True
            logger.info(f"Connected to Thermalright Frozen Warframe (VID:{hex(VID)} PID:{hex(PID)}) [FastPath: {self._dev_handle is not None}]")
            return True
        except Exception as e:
            logger.error(f"Error connecting to display: {e}")
            self.device = None
            self.connected = False
            return False

    def is_connected(self) -> bool:
        return self.connected and self.device is not None

    def disconnect(self):
        if self.device:
            try:
                usb.util.dispose_resources(self.device)
            except Exception:
                pass
            self.device = None
        self.connected = False
        logger.info("Disconnected from display.")

    @staticmethod
    def pil_to_rgb565(pil_image: Image.Image, brightness: float = 1.0) -> bytes:
        """
        Convert PIL Image (240x320) into RGB565 Little Endian bytes.
        Fast NumPy implementation (< 0.5 ms).
        """
        if pil_image.size != (PANEL_WIDTH, PANEL_HEIGHT):
            pil_image = pil_image.resize((PANEL_WIDTH, PANEL_HEIGHT), Image.Resampling.BILINEAR)

        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        arr = np.asarray(pil_image, dtype=np.float32)
        if brightness < 1.0:
            arr = arr * max(0.1, min(1.0, brightness))
        arr = arr.astype(np.uint16)

        # 16-bit RGB565: (R >> 3) << 11 | (G >> 2) << 5 | (B >> 3)
        r = (arr[:, :, 0] >> 3) << 11
        g = (arr[:, :, 1] >> 2) << 5
        b = (arr[:, :, 2] >> 3)
        rgb565 = (r | g | b).astype("<u2").tobytes()
        return rgb565

    def build_frame_packet(self, rgb565_data: bytes) -> bytes:
        """
        Build 20-byte Type-2 header + payload, padded to 512-byte boundary.
        Header format:
          0..3: DA DB DC DD (Magic)
          4..5: 02 00 (cmd = PICTURE)
          6..7: 01 00 (RGB565 mode)
          8..9: 240 (Width LE uint16)
          10..11: 320 (Height LE uint16)
          12..15: 02 00 00 00 (Sub-mode)
          16..19: payload length LE uint32 (153600)
        """
        header = bytearray(MAGIC_HEADER)
        header += struct.pack("<H", 0x0002)  # CMD_TYPE_PICTURE
        header += struct.pack("<H", 0x0001)  # RGB565 mode
        header += struct.pack("<HH", PANEL_WIDTH, PANEL_HEIGHT)
        header += struct.pack("<I", 0x00000002)
        header += struct.pack("<I", len(rgb565_data))

        raw_packet = bytes(header) + rgb565_data
        aligned_len = (len(raw_packet) + USB_CHUNK_SIZE - 1) // USB_CHUNK_SIZE * USB_CHUNK_SIZE
        return raw_packet.ljust(aligned_len, b"\x00")

    def send_frame(self, rgb565_data: bytes) -> bool:
        """
        Send an RGB565 frame to the display.
        Uses direct C ctypes fast-path when available for near-zero CPU usage.
        """
        if not self.is_connected():
            if not self.connect():
                return False

        packet = self.build_frame_packet(rgb565_data)
        packet_len = len(packet)

        # FAST-PATH: Direct C interrupt transfer
        if self._dev_handle and self._fn_interrupt:
            try:
                ctypes.memmove(self._c_buf, packet, packet_len)
                fn = self._fn_interrupt
                handle = self._dev_handle
                transferred = self._c_transferred_ptr

                for ptr in self._c_ptrs:
                    fn(handle, EP_WRITE, ptr, USB_CHUNK_SIZE, transferred, 100)

                self.last_send_time = time.time()
                return True
            except Exception as e:
                logger.warning(f"Fast-path write failed, falling back: {e}")

        # SLOW-PATH: Standard pyusb chunked write
        view = memoryview(packet)
        try:
            for offset in range(0, packet_len, USB_CHUNK_SIZE):
                chunk = view[offset:offset + USB_CHUNK_SIZE]
                self.device.write(EP_WRITE, chunk, timeout=100)
            self.last_send_time = time.time()
            return True
        except Exception as e:
            logger.warning(f"Failed to write frame: {e}")
            self.connected = False
            return False

    def send_pil_image(self, pil_image: Image.Image, brightness: float = 1.0) -> bool:
        """Helper to convert and send PIL Image in one step."""
        rgb565 = self.pil_to_rgb565(pil_image, brightness=brightness)
        return self.send_frame(rgb565)

