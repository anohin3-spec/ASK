"""
Модуль для работы с базой данных (универсальный адаптер)
Поддерживает работу в локальном (SQLite) и облачном (Supabase) режимах
"""
import os
from dotenv import load_dotenv
from app_config import DEFAULT_MODE

# Загружаем переменные окружения
load_dotenv()

# Определяем режим работы
MODE = os.getenv('MODE', DEFAULT_MODE)  # local или cloud

print(f"Режим базы данных: {MODE.upper()}")

if MODE == 'cloud':
    from database_cloud import DatabaseCloud as Database
    print("Подключение к Supabase...")
else:
    from database_local import Database
    print("Использование локальной SQLite базы...")

# Экспортируем класс Database и режим (для UI: облако / локально)
__all__ = ['Database', 'MODE']
