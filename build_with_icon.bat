@echo off
REM Полная сборка: EXE + установщик Inno Setup (см. build_installer.bat)
call "%~dp0build_installer.bat"
exit /b %ERRORLEVEL%
