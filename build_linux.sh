#!/bin/bash

# Clean previous builds
rm -rf build dist *.spec

# Run PyInstaller
./.venv/bin/python3 -m PyInstaller --onefile --windowed \
    --name yclicker \
    --icon=yclicker.ico \
    --hidden-import=wayland_support \
    --add-data "config.json:." \
    --add-data "yclicker.ico:." \
    --add-data "steel.png:." \
    --add-data "style.qss:." \
    main.py

echo "Build complete. The executable is in the 'dist' directory."

