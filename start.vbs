Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\nohanvs\testemipo"
WshShell.Run """C:\Users\nohanvs\AppData\Local\Python\bin\pythonw.exe"" app.py", 0, False
