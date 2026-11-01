"""
WarframeDisplay - Main Application Entrypoint.
A lightweight, native display controller for Thermalright Frozen Warframe 360 SE / ARGB Displays.
"""

import sys
import os

# Add script directory to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from display_driver import WarframeDisplayDriver
from gif_processor import GifProcessor
from system_monitor import SystemMonitor
from config_manager import ConfigManager
from ui import WarframeApp

def main():
    driver = WarframeDisplayDriver()
    processor = GifProcessor()
    monitor = SystemMonitor(interval=1.5)
    config = ConfigManager()

    # Start hardware sensors
    monitor.start()

    # Start main GUI application
    app = WarframeApp(driver, processor, monitor, config)
    
    # If launched with --minimized, start directly in tray
    if "--minimized" in sys.argv:
        app.after(100, app._minimize_to_tray)

    app.mainloop()

if __name__ == "__main__":
    main()

