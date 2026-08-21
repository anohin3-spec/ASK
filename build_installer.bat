@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM --- Python: py -3 или python из PATH ---
set "PYEXE=py -3"
%PYEXE% -c "import sys" >nul 2>&1
if errorlevel 1 (
  set "PYEXE=python"
  %PYEXE% -c "import sys" >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] Не найден Python. Установите Python 3 и добавьте в PATH, либо установите «Python Launcher» (py).
    exit /b 1
  )
)

if not exist "assets\app.ico" (
  echo [ERROR] Нет файла assets\app.ico
  exit /b 1
)

echo [1/5] Зависимости для сборки (Pillow, PyInstaller)...
%PYEXE% -m pip install -q Pillow PyInstaller
if errorlevel 1 exit /b 1

echo [2/5] Нормализация иконки...
%PYEXE% normalize_icon.py assets\app.ico
if errorlevel 1 exit /b 1

echo [3/5] Очистка временных каталогов PyInstaller...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [4/5] Сборка ASK.exe (PyInstaller + ASK.spec)...
%PYEXE% -m PyInstaller --noconfirm --clean ASK.spec
if errorlevel 1 exit /b 1

if not exist release mkdir release
copy /y "dist\ASK.exe" "release\ASK.exe" >nul
copy /y "env.example" "release\.env.template" >nul
if errorlevel 1 (
  echo [ERROR] Не удалось скопировать dist\ASK.exe в release\
  exit /b 1
)

REM --- Inno Setup 6 ---
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
  echo [WARN] Inno Setup 6 не найден. Собран только release\ASK.exe
  echo Установите Inno Setup: https://jrsoftware.org/isinfo.php
  exit /b 0
)

echo [5/5] Сборка установщика Inno Setup...
"%ISCC%" "installer\ASK_Setup.iss"
if errorlevel 1 exit /b 1

echo.
echo Готово:
echo   - release\ASK.exe
echo   - release\ASK_Setup_Windows11.exe
exit /b 0
