@echo off
echo Building Simulator...
python -m pip install -r requirements.txt
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name "RobotSimulator" --add-data "assets;assets" simulator.py
echo Build complete! Executable is in dist/RobotSimulator.exe
pause