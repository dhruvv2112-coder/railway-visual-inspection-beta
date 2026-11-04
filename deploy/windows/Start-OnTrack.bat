@echo off
title OnTrack.AI server
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup\OnTrack-Server.ps1" %*
if errorlevel 1 (
  echo.
  echo   The server stopped with an error. The log is in %LOCALAPPDATA%\OnTrack\server-setup.log
  pause
)
