"""
Скрипт для обновления базы данных - добавление колонки mkad_pass_date
"""
import sqlite3

def update_database():
    """Добавляет колонку mkad_pass_date в таблицу equipment"""
    conn = sqlite3.connect('maintenance.db')
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли колонка
        cursor.execute("PRAGMA table_info(equipment)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'mkad_pass_date' not in columns:
            print("Добавление колонки mkad_pass_date...")
            cursor.execute('''
                ALTER TABLE equipment ADD COLUMN mkad_pass_date TEXT
            ''')
            conn.commit()
            print("✓ Колонка mkad_pass_date успешно добавлена!")
        else:
            print("✓ Колонка mkad_pass_date уже существует")
            
    except Exception as e:
        print(f"✗ Ошибка при обновлении: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    print("Обновление базы данных...")
    update_database()
    print("Готово!")
