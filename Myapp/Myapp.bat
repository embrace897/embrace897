@echo off
rem Wrapper that behaves like Myapp.exe: pass all arguments to main.py
rem (Keep this file ASCII-only and CRLF-terminated so cmd.exe parses it correctly.)
setlocal
set "MYAPP_DIR=%~dp0"
where python >nul 2>nul
if errorlevel 1 goto :use_py_launcher
python "%MYAPP_DIR%main.py" %*
exit /b %ERRORLEVEL%

:use_py_launcher
py -3 "%MYAPP_DIR%main.py" %*
exit /b %ERRORLEVEL%
