"""
Creates Desktop shortcut and Start Menu shortcut for Thermalright Warframe Display.
Uses Windows Script Host (.vbs) with Chr(34) to guarantee clean, uncorrupted paths and arguments.
"""

import os
import sys
import tempfile
import subprocess
from PIL import Image

def build_shortcuts():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    start_menu = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs")
    
    icon_png = os.path.join(script_dir, "assets", "app_icon.png")
    icon_ico = os.path.join(script_dir, "assets", "app_icon.ico")

    # 1. Ensure high-res multi-size .ico exists
    if os.path.exists(icon_png):
        try:
            img = Image.open(icon_png)
            img.save(
                icon_ico,
                format="ICO",
                sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
            )
            print(f"Generated multi-size icon: {icon_ico}")
        except Exception as e:
            print(f"Icon generation note: {e}")

    go_exe = os.path.join(script_dir, "ThermalrightWarframe.exe")
    dist_exe = os.path.join(script_dir, "dist", "ThermalrightWarframe", "ThermalrightWarframe.exe")
    use_compiled_exe = os.path.exists(go_exe) or os.path.exists(dist_exe)
    target_exe = go_exe if os.path.exists(go_exe) else dist_exe

    # Find pythonw.exe fallback
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    main_script = os.path.join(script_dir, "main.py")
    
    shortcut_targets = [
        os.path.join(desktop, "Thermalright Warframe Display.lnk"),
        os.path.join(start_menu, "Thermalright Warframe Display.lnk")
    ]

    for shortcut_path in shortcut_targets:
        if use_compiled_exe:
            vbs_content = (
                'Set WshShell = CreateObject("WScript.Shell")\n'
                f'Set Shortcut = WshShell.CreateShortcut("{shortcut_path}")\n'
                f'Shortcut.TargetPath = "{target_exe}"\n'
                'Shortcut.Arguments = ""\n'
                f'Shortcut.WorkingDirectory = "{os.path.dirname(target_exe)}"\n'
                'Shortcut.Description = "Thermalright Warframe AIO Display Controller (Native Go)"\n'
            )
            if os.path.exists(icon_ico):
                vbs_content += f'Shortcut.IconLocation = "{icon_ico},0"\n'
            vbs_content += 'Shortcut.Save\n'
        else:
            # Build clean VBS script using Chr(34) to escape double quotes
            vbs_content = (
                'Set WshShell = CreateObject("WScript.Shell")\n'
                f'Set Shortcut = WshShell.CreateShortcut("{shortcut_path}")\n'
                f'Shortcut.TargetPath = "{pythonw}"\n'
                f'Shortcut.Arguments = Chr(34) & "{main_script}" & Chr(34)\n'
                f'Shortcut.WorkingDirectory = "{script_dir}"\n'
                'Shortcut.Description = "Thermalright Warframe AIO Display Controller"\n'
            )
            if os.path.exists(icon_ico):
                vbs_content += f'Shortcut.IconLocation = "{icon_ico},0"\n'
            vbs_content += 'Shortcut.Save\n'

        vbs_file = os.path.join(tempfile.gettempdir(), "create_warframe_lnk.vbs")
        with open(vbs_file, "w", encoding="utf-8") as f:
            f.write(vbs_content)

        res = subprocess.run(["cscript", "//nologo", vbs_file], capture_output=True, text=True)
        try:
            os.remove(vbs_file)
        except Exception:
            pass

        if res.returncode == 0:
            print(f"Successfully created shortcut: {shortcut_path}")
        else:
            print(f"Failed to create shortcut {shortcut_path}: {res.stderr}")

if __name__ == "__main__":
    build_shortcuts()
