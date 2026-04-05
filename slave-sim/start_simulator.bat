@echo off
chcp 65001 >nul
echo 正在启动机器人模拟器控制台...
cd /d "%~dp0"
start pythonw src/core/simulator_gui.py
