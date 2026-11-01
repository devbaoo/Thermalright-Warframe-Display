"""
Configuration Manager & TRCC Process Controller for Warframe Display.
"""

import os
import json
import subprocess
import winreg
from typing import Dict, Any

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
RUN_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "WarframeAIO_Display"

DEFAULT_CONFIG: Dict[str, Any] = {
    "last_file": "",
    "rotation": 0,
    "mount_mode": "landscape",
    "fit_mode": "fill",
    "brightness": 1.0,
    "fps_override": 20,
    "overlay_enabled": False,
    "overlay_position": "bottom",
    "overlay_style": "badges",
    "minimize_to_tray": True,
    "autostart": False
}

class ConfigManager:
    def __init__(self):
        self.config: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.config.update(data)
            except Exception as e:
                print(f"Error loading config.json: {e}")

    def save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config.json: {e}")

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value
        self.save()

    @staticmethod
    def is_trcc_running() -> bool:
        """Check if any official TRCC process is running."""
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                name = proc.info['name'].lower()
                if any(k in name for k in ['trcc.exe', 'hwinfo.exe', 'usblcd.exe', 'usblcdnew.exe']):
                    return True
        except Exception:
            pass
        return False

    @staticmethod
    def kill_trcc_processes() -> int:
        """Terminate bloated TRCC and HWINFO background processes to free CPU/RAM."""
        killed_count = 0
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                name = (proc.info['name'] or '').lower()
                if any(k in name for k in ['trcc.exe', 'hwinfo.exe', 'usblcd.exe', 'usblcdnew.exe']):
                    try:
                        proc.terminate()
                        killed_count += 1
                    except Exception:
                        try:
                            proc.kill()
                            killed_count += 1
                        except Exception:
                            pass
        except Exception as e:
            print(f"Error killing TRCC processes: {e}")
        return killed_count

    @staticmethod
    def set_trcc_task_enabled(enable: bool) -> bool:
        """Enable or disable official TRCCAppStartup scheduled task."""
        try:
            action = "Enable" if enable else "Disable"
            cmd = ["schtasks", "/Change", "/TN", "TRCCAppStartup", f"/{action}"]
            subprocess.run(cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
            return True
        except Exception:
            return False

    def set_autostart(self, enable: bool) -> bool:
        """Register / unregister this app in Windows Registry Startup."""
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_hidden.vbs")
        cmd_val = f'wscript.exe "{script_path}"'
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_REG_KEY, 0, winreg.KEY_SET_VALUE)
            if enable:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd_val)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            self.set("autostart", enable)
            return True
        except Exception as e:
            print(f"Failed to update registry autostart: {e}")
            return False

