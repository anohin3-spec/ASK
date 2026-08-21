@echo off
setlocal
cd /d %~dp0

echo Starting Telegram bot...
python telegram_bot.py

if errorlevel 1 (
  echo.
  echo Bot stopped with error.
  pause
)
