Set shell = CreateObject("WScript.Shell")
shell.Run "pythonw """ & Replace(WScript.ScriptFullName, "launch_autoclicker.vbs", "app.pyw") & """", 0, False
