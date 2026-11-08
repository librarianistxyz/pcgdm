@echo off
title TeleKey Windows Installer
echo ========================================================
echo      GodMode TeleKey - Windows Auto-Installer
echo ========================================================
echo.

set TARGET_DIR=%APPDATA%\pcGDM
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

echo [*] Copying TeleKey script to %TARGET_DIR%...
copy /Y "%~dp0tele_key_windows.ps1" "%TARGET_DIR%\tele_key_windows.ps1" >nul

echo [*] Registering Windows Startup task...
set VBS_RUNNER=%TARGET_DIR%\run_silent.vbs
echo Set WshShell = CreateObject("WScript.Shell") > "%VBS_RUNNER%"
echo WshShell.Run "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File ""%TARGET_DIR%\tele_key_windows.ps1""", 0, False >> "%VBS_RUNNER%"

copy /Y "%VBS_RUNNER%" "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\TeleKey.vbs" >nul

echo [*] Starting TeleKey background daemon now...
wscript.exe "%VBS_RUNNER%"

echo.
echo [OK] TeleKey installed and running in background!
echo Whenever you plug your 16GB USB key into this PC, it will
echo automatically connect to your Telegram Bot.
echo ========================================================
pause
