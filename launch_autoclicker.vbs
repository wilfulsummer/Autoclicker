Option Explicit

Dim shell, fso, scriptDir, appPath, pythonCommand
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
appPath = fso.BuildPath(scriptDir, "app.pyw")

If Not fso.FileExists(appPath) Then
    MsgBox "AutoClicker could not find app.pyw next to the launcher." & vbCrLf & vbCrLf & appPath, vbCritical, "AutoClicker Launch Error"
    WScript.Quit 1
End If

shell.CurrentDirectory = scriptDir
pythonCommand = ResolvePythonLauncher(shell)

If pythonCommand = "" Then
    MsgBox "Python was not found." & vbCrLf & vbCrLf & _
           "Install Python and enable the Python Launcher or add Python to PATH, then try again.", _
           vbCritical, "AutoClicker Launch Error"
    WScript.Quit 1
End If

shell.Run pythonCommand & " " & Quote(appPath), 0, False

Function ResolvePythonLauncher(sh)
    If CommandWorks(sh, "pythonw --version") Then
        ResolvePythonLauncher = "pythonw"
        Exit Function
    End If

    If CommandWorks(sh, "pyw --version") Then
        ResolvePythonLauncher = "pyw"
        Exit Function
    End If

    If CommandWorks(sh, "py -3w --version") Then
        ResolvePythonLauncher = "py -3w"
        Exit Function
    End If

    If CommandWorks(sh, "python --version") Then
        ResolvePythonLauncher = "python"
        Exit Function
    End If

    ResolvePythonLauncher = ""
End Function

Function CommandWorks(sh, command)
    Dim exitCode
    On Error Resume Next
    exitCode = sh.Run("%ComSpec% /c " & command & " >nul 2>&1", 0, True)
    CommandWorks = (Err.Number = 0 And exitCode = 0)
    Err.Clear
    On Error GoTo 0
End Function

Function Quote(value)
    Quote = Chr(34) & value & Chr(34)
End Function
