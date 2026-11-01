Set WshShell = CreateObject("WScript.Shell")
strDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strDir
WshShell.Run "C:\Users\Admin\AppData\Local\Programs\Python\Python312\pythonw.exe main.py --minimized", 0, False

