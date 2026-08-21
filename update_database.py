"""
Скрипт для обновления существующей базы данных
Добавляет новое поле sort_order в таблицу equipment
"""
import sqlite3
import os

def update_database():
    """Обновление структуры базы данных"""
    db_path = "maintenance.db"
    
    if not os.path.exists(db_path):
        print("❌ База данных не найдена!")
        print("Запустите main.py для создания новой базы данных.")
        return
    
    print("🔄 Обновление базы данных...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли уже поле sort_order
        cursor.execute("PRAGMA table_info(equipment)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'sort_order' not in columns:
            print("  Добавление поля sort_order...")
            cursor.execute("ALTER TABLE equipment ADD COLUMN sort_order INTEGER DEFAULT 0")
            conn.commit()
            print("  ✅ Поле sort_order добавлено")
        else:
            print("  ℹ️ Поле sort_order уже существует")
        
        print("\n✅ База данных обновлена!")
        print("Теперь можно запустить программу: python main.py")
        
    except Exception as e:
        print(f"\n❌ Ошибка при обновлении: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    update_database()
    input("\nНажмите Enter для выхода...")
