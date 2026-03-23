@echo off
REM ASCII-only: avoid cmd.exe misparsing UTF-8 on Chinese Windows
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-http.ps1"
