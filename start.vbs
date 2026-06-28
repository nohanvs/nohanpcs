Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "%USERPROFILE%\testemipo"
WshShell.Run """%LOCALAPPDATA%\Python\bin\pythonw.exe"" -B %USERPROFILE%\testemipo\app.py", 0, False
