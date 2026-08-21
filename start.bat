@echo off
chcp 65001 > nul
echo ========================================
echo   Maintenance Helper
echo ========================================
echo.
echo Проверка зависимостей...
python -c "import openpyxl" 2>nul
if %errorlevel% neq 0 (
    echo ⚠ Библиотека openpyxl не установлена!
    echo Устанавливаю зависимости...
    pip install -r requirements.txt
    echo.
)

echo Запуск программы...
echo.
python main.py

if %errorlevel% neq 0 (
    echo.
    echo ❌ Ошибка при запуске программы!
    pause
)
