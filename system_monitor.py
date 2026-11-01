"""
Lightweight Hardware Monitor for Warframe Display.
Polls CPU, RAM, and GPU stats with zero-impact on performance.
"""

import threading
import time
import subprocess
import psutil

class SystemMonitor:
    def __init__(self, interval: float = 1.5):
        self.interval = interval
        self.cpu_usage: float = 0.0
        self.ram_usage: float = 0.0
        self.gpu_temp: float = 0.0
        self.gpu_usage: float = 0.0
        self.running: bool = False
        self._thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def _query_gpu(self):
        """Query NVIDIA GPU temp and utilization via nvidia-smi."""
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu", "--format=csv,noheader,nounits"],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                timeout=1.0,
                text=True
            ).strip()
            if out:
                parts = [p.strip() for p in out.split(",")]
                self.gpu_temp = float(parts[0])
                self.gpu_usage = float(parts[1])
        except Exception:
            pass

    def _update_loop(self):
        # Initial non-blocking call
        psutil.cpu_percent(interval=None)
        
        while self.running:
            try:
                self.cpu_usage = psutil.cpu_percent(interval=None)
                self.ram_usage = psutil.virtual_memory().percent
                self._query_gpu()
            except Exception:
                pass
            time.sleep(self.interval)

    def get_stats(self) -> dict:
        return {
            "cpu_usage": self.cpu_usage,
            "ram_usage": self.ram_usage,
            "gpu_temp": self.gpu_temp,
            "gpu_usage": self.gpu_usage,
            "time_str": time.strftime("%H:%M"),
            "date_str": time.strftime("%m/%d"),
        }

