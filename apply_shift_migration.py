"""
Скрипт применения миграции для добавления колонки shift_half в equipment_drivers
"""
from database import get_database
from app_config import DEFAULT_MODE

def apply_migration():
    db = get_database()
    
    if DEFAULT_MODE != 'cloud':
        print("Миграция предназначена только для облачной базы данных")
        return False
    
    try:
        # SQL для добавления колонки shift_half
        migration_sql = """
        ALTER TABLE equipment_drivers 
        ADD COLUMN IF NOT EXISTS shift_half INTEGER CHECK (shift_half IN (1, 2) OR shift_half IS NULL);
        """
        
        # Применяем миграцию через Supabase API (используем метод rpc или прямой SQL)
        # Supabase клиент не поддерживает прямой execute SQL, поэтому используем альтернативный способ
        
        print("❌ Автоматическое применение миграции недоступно через Supabase API")
        print("\n📋 Выполните следующий SQL вручную в Supabase Dashboard:")
        print("=" * 70)
        print(migration_sql)
        print("=" * 70)
        print("\n1. Откройте https://supabase.com/dashboard")
        print("2. Выберите ваш проект")
        print("3. Перейдите в SQL Editor")
        print("4. Скопируйте и выполните SQL выше")
        
        return None
        
    except Exception as e:
        print(f"Ошибка: {e}")
        return False

if __name__ == '__main__':
    apply_migration()
