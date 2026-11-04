@echo off
title OnTrack.AI - add a user
set /p UID=User ID (e.g. PT-0002): 
echo Roles: Patrol, SSE, ADEE, DEE, SrDEE, Admin
set /p ROLE=Role: 
set /p PIN=PIN (4-8 digits): 
set /p NAME=Name: 
set RVI_SECRET_KEY=
for /f "usebackq delims=" %%k in ("%LOCALAPPDATA%\OnTrack\secret.txt") do set RVI_SECRET_KEY=%%k
set RVI_USERS_FILE=%LOCALAPPDATA%\OnTrack\users.yaml
cd /d "%~dp0server\backend"
"%LOCALAPPDATA%\OnTrack\venv\Scripts\python.exe" -m app.ohe.auth add "%UID%" "%ROLE%" "%PIN%" "%NAME%"
pause
