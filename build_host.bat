@echo off
echo Building Host Application...
cd host-app
npm install
npm run build
echo Build complete! Installer is in host-app/dist
pause