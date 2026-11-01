"""
Creates Desktop shortcut and Start Menu shortcut for Warframe Display.
"""

import os
import sys
from PIL import Image

def create_shortcuts():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    icon_png = os.path.join(script_dir, "assets", "app_icon.png")
    icon_ico = os.path.join(script_dir, "assets", "app_icon.ico")

    # Generate .ico file
    if os.path.exists(icon_png) and not os.path.exists(icon_ico):
        try:
            img = Image.open(icon_png)
            img.save(icon_ico, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            print("Generated app_icon.ico")
        except Exception as e:
            print("Error generating icon:", e)

    # Use PowerShell to create .lnk
    shortcut_path = os.path.join(desktop, "Thermalright Warframe Display.lnk")
    pythonw = r"C:\Users\Admin\AppData\Local\Programs\Python\Python312\pythonw.exe"
    target = os.path.join(script_dir, "main.py")

    ps_cmd = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
    $Shortcut.TargetPath = "{pythonw}"
    $Shortcut.Arguments = '"{target}"'
    $Shortcut.WorkingDirectory = "{script_dir}"
    $Shortcut.Description = "Thermalright Warframe AIO Display Controller"
    if (Test-Path "{icon_ico}") {{
        $Shortcut.IconLocation = "{icon_ico}, 0"
    }}
    $Shortcut.Save()
    """

    import subprocess
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
    print(f"Created shortcut at: {shortcut_path}")

if __name__ == "__main__":
    create_shortcuts()
