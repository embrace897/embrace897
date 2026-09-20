@echo off
rem Optional step: build Myapp.exe with PyInstaller.
rem After building:  dist\Myapp.exe -n 10 -r 10
python -m pip install --upgrade pyinstaller
python -m PyInstaller --onefile --console --name Myapp --paths . main.py
echo.
echo Build finished. The executable is at dist\Myapp.exe
