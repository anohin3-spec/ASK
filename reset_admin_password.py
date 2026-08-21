"""
Скрипт экстренного сброса пароля администратора
Используется когда админ забыл пароль и нужно восстановить доступ

ИСПОЛЬЗОВАНИЕ:
    python reset_admin_password.py

Скрипт запросит:
1. Username пользователя
2. Новый пароль
3. Подтверждение

После успешного выполнения можно войти с новым паролем.
"""
import os
import sys
from getpass import getpass
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Проверяем режим работы
MODE = os.getenv('MODE', 'local')

if MODE != 'cloud':
    print("❌ ОШИБКА: Скрипт работает только в режиме cloud")
    print("Убедитесь, что в файле .env установлено MODE=cloud")
    sys.exit(1)

try:
    from supabase import create_client
    import bcrypt
except ImportError:
    print("❌ ОШИБКА: Не установлены необходимые библиотеки")
    print("Выполните: pip install supabase bcrypt")
    sys.exit(1)


def hash_password(password: str) -> str:
    """Хеширование пароля"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def reset_password():
    """Основная функция сброса пароля"""
    print("=" * 60)
    print("🔧 ЭКСТРЕННЫЙ СБРОС ПАРОЛЯ")
    print("=" * 60)
    print()
    
    # Подключение к Supabase
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ ОШИБКА: Не найдены учетные данные Supabase в .env")
        print("Проверьте наличие SUPABASE_URL и SUPABASE_KEY")
        sys.exit(1)
    
    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Подключение к облачной базе данных установлено")
        print()
    except Exception as e:
        print(f"❌ ОШИБКА подключения к базе данных: {e}")
        sys.exit(1)
    
    # Запрашиваем username
    username = input("Введите username пользователя: ").strip()
    
    if not username:
        print("❌ Username не может быть пустым")
        sys.exit(1)
    
    # Проверяем существование пользователя
    try:
        result = client.table('users').select(
            'id, username, full_name, role, company_id'
        ).eq('username', username).execute()
        
        if not result.data or len(result.data) == 0:
            print(f"❌ Пользователь '{username}' не найден в базе данных")
            sys.exit(1)
        
        user = result.data[0]
        print()
        print("📋 Найден пользователь:")
        print(f"   Username: {user['username']}")
        print(f"   Полное имя: {user.get('full_name', 'Не указано')}")
        print(f"   Роль: {user['role']}")
        print()
        
    except Exception as e:
        print(f"❌ ОШИБКА при поиске пользователя: {e}")
        sys.exit(1)
    
    # Запрашиваем новый пароль
    while True:
        new_password = getpass("Введите новый пароль (минимум 6 символов): ")
        
        if len(new_password) < 6:
            print("❌ Пароль должен содержать минимум 6 символов")
            continue
        
        confirm_password = getpass("Подтвердите новый пароль: ")
        
        if new_password != confirm_password:
            print("❌ Пароли не совпадают. Попробуйте снова.")
            continue
        
        break
    
    # Подтверждение действия
    print()
    confirm = input("⚠️  Вы уверены, что хотите сбросить пароль? (да/нет): ").strip().lower()
    
    if confirm not in ['да', 'yes', 'y', 'д']:
        print("❌ Отменено пользователем")
        sys.exit(0)
    
    # Хешируем новый пароль
    try:
        password_hash = hash_password(new_password)
    except Exception as e:
        print(f"❌ ОШИБКА при хешировании пароля: {e}")
        sys.exit(1)
    
    # Обновляем пароль в базе данных
    try:
        client.table('users').update({
            'password_hash': password_hash
        }).eq('id', user['id']).execute()
        
        print()
        print("=" * 60)
        print("✅ УСПЕХ! Пароль успешно изменен")
        print("=" * 60)
        print()
        print(f"Теперь вы можете войти в систему с учетными данными:")
        print(f"   Username: {username}")
        print(f"   Пароль: {new_password}")
        print()
        print("⚠️  ВАЖНО: Запишите новый пароль в безопасном месте!")
        print()
        
    except Exception as e:
        print(f"❌ ОШИБКА при обновлении пароля: {e}")
        sys.exit(1)


if __name__ == '__main__':
    try:
        reset_password()
    except KeyboardInterrupt:
        print("\n\n❌ Операция прервана пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        sys.exit(1)
