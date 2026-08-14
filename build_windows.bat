@echo off
REM build_windows.bat - build yclicker on Windows using PyInstaller
REM Run this from the project folder in CMD (not PowerShell) as administrator if needed.

python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install PySide6 pynput pyinstaller

REM Ensure yclicker.ico and config.json are present in the project root
pyinstaller --onefile --windowed --name yclicker --icon=yclicker.ico --add-data "config.json;." --add-data "yclicker.ico;." --add-data "steel.png;." --add-data "style.qss;." main.py

echo Build finished. See dist\yclicker.exe
