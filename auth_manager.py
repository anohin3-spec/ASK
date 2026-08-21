"""
Менеджер аутентификации - управление входом, паролями и сессиями
"""
import bcrypt
from typing import Optional, Dict, Any, Tuple


class AuthManager:
    """Управление аутентификацией пользователей"""
    
    def __init__(self, db):
        """
        Инициализация менеджера аутентификации
        
        Args:
            db: Экземпляр базы данных (DatabaseCloud или Database)
        """
        self.db = db
        self.current_user = None  # Текущий авторизованный пользователь
        self.current_company = None  # Текущая компания
    
    def hash_password(self, password: str) -> str:
        """
        Хеширование пароля с использованием bcrypt
        
        Args:
            password: Пароль в открытом виде
            
        Returns:
            str: Хешированный пароль
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Проверка пароля против хеша
        
        Args:
            password: Пароль в открытом виде
            password_hash: Хешированный пароль из БД
            
        Returns:
            bool: True если пароль верный
        """
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                password_hash.encode('utf-8')
            )
        except Exception:
            return False
    
    def login(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Попытка входа в систему
        
        Args:
            username: Имя пользователя
            password: Пароль
            
        Returns:
            Dict с данными пользователя и компании или None при ошибке
        """
        try:
            username = username.strip()
            username_norm = username.lower()

            # Получаем пользователя по username
            result = self.db.client.table('users').select(
                'id, company_id, username, password_hash, full_name, role, is_active, '
                'companies:company_id(id, name, license_valid_until, max_vehicles)'
            ).ilike('username', username_norm).execute()
            
            if not result.data or len(result.data) == 0:
                return None  # Пользователь не найден
            
            user = result.data[0]
            
            # Проверка активности аккаунта
            if not user.get('is_active', True):
                return None  # Аккаунт деактивирован
            
            password_hash = user.get('password_hash', '')
            
            # Проверка пароля
            # Если пароль не зашифрован (для первого входа admin123)
            if password_hash == password:
                # Шифруем пароль и обновляем
                new_hash = self.hash_password(password)
                self.db.client.table('users').update({
                    'password_hash': new_hash
                }).eq('id', user['id']).execute()
                password_verified = True
            else:
                # Обычная проверка хеша
                password_verified = self.verify_password(password, password_hash)
            
            if not password_verified:
                return None  # Неверный пароль
            
            # Получаем данные компании
            company_data = user.get('companies')
            if not company_data:
                return None  # Нет компании
            
            # Сохраняем текущего пользователя и компанию
            self.current_user = {
                'id': user['id'],
                'username': user['username'],
                'full_name': user.get('full_name', username),
                'role': user.get('role', 'user')
            }
            
            self.current_company = {
                'id': company_data['id'],
                'name': company_data['name'],
                'license_valid_until': company_data.get('license_valid_until'),
                'max_vehicles': company_data.get('max_vehicles', 50)
            }
            
            # Устанавливаем company_id и user_id в базе данных
            self.db.set_company(self.current_company['id'])
            self.db.set_user(self.current_user['id'])
            
            return {
                'user': self.current_user,
                'company': self.current_company
            }
            
        except Exception as e:
            print(f"Ошибка при входе: {e}")
            return None
    
    def logout(self):
        """Выход из системы"""
        self.current_user = None
        self.current_company = None
        self.db.set_company(None)
        self.db.set_user(None)
    
    def is_authenticated(self) -> bool:
        """Проверка авторизации пользователя"""
        return self.current_user is not None
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Получить данные текущего пользователя"""
        return self.current_user
    
    def get_current_company(self) -> Optional[Dict[str, Any]]:
        """Получить данные текущей компании"""
        return self.current_company
    
    def has_permission(self, permission: str) -> bool:
        """
        Проверка прав доступа
        
        Args:
            permission: Требуемое право ('superadmin', 'admin', 'manager', 'user')
            
        Returns:
            bool: True если пользователь имеет право
        """
        if not self.current_user:
            return False
        
        role = self.current_user.get('role', 'user')
        
        # Иерархия прав: superadmin > admin > manager > user
        role_levels = {'superadmin': 4, 'admin': 3, 'manager': 2, 'user': 1}
        user_level = role_levels.get(role, 0)
        required_level = role_levels.get(permission, 0)
        
        return user_level >= required_level
    
    def change_password(self, old_password: str, new_password: str) -> bool:
        """
        Смена пароля текущего пользователя
        
        Args:
            old_password: Старый пароль
            new_password: Новый пароль
            
        Returns:
            bool: True при успешной смене
        """
        if not self.current_user:
            return False
        
        try:
            # Получаем текущий хеш пароля
            result = self.db.client.table('users').select('password_hash').eq(
                'id', self.current_user['id']
            ).execute()
            
            if not result.data:
                return False
            
            current_hash = result.data[0]['password_hash']
            
            # Проверяем старый пароль
            if not self.verify_password(old_password, current_hash):
                return False
            
            # Хешируем новый пароль
            new_hash = self.hash_password(new_password)
            
            # Обновляем пароль
            self.db.client.table('users').update({
                'password_hash': new_hash
            }).eq('id', self.current_user['id']).execute()
            
            return True
            
        except Exception as e:
            print(f"Ошибка при смене пароля: {e}")
            return False
    
    def create_user(self, username: str, password: str, full_name: str, 
                   role: str = 'user') -> Optional[str]:
        """
        Создание нового пользователя (только для admin)
        
        Args:
            username: Имя пользователя
            password: Пароль
            full_name: Полное имя
            role: Роль ('admin', 'manager', 'user')
            
        Returns:
            str: ID нового пользователя или None при ошибке
        """
        if not self.has_permission('admin'):
            return None
        
        try:
            username = username.strip().lower()
            # Хешируем пароль
            password_hash = self.hash_password(password)
            
            # Создаем пользователя
            result = self.db.client.table('users').insert({
                'company_id': self.current_company['id'],
                'username': username,
                'password_hash': password_hash,
                'full_name': full_name,
                'role': role,
                'is_active': True
            }).execute()
            
            if result.data:
                return result.data[0]['id']
            
            return None
            
        except Exception as e:
            print(f"Ошибка при создании пользователя: {e}")
            return None
    
    def reset_user_password(self, user_id: str, new_password: str) -> bool:
        """
        Сброс пароля пользователя администратором
        
        Args:
            user_id: ID пользователя
            new_password: Новый пароль
            
        Returns:
            bool: True при успешном сбросе
        """
        if not self.has_permission('admin'):
            return False
        
        try:
            # Проверяем, что пользователь из той же компании
            result = self.db.client.table('users').select('company_id').eq(
                'id', user_id
            ).execute()
            
            if not result.data:
                return False
            
            user_company = result.data[0]['company_id']
            is_superadmin = self.current_user and self.current_user.get('role') == 'superadmin'
            if not is_superadmin and user_company != self.current_company['id']:
                return False  # Нельзя сбросить пароль пользователя из другой компании
            
            # Хешируем новый пароль
            password_hash = self.hash_password(new_password)
            
            # Обновляем пароль
            self.db.client.table('users').update({
                'password_hash': password_hash
            }).eq('id', user_id).execute()
            
            return True
            
        except Exception as e:
            print(f"Ошибка при сбросе пароля: {e}")
            return False
    
    def register_company(self, company_name: str, phone: str, email: str,
                        admin_username: str, admin_password: str, admin_fullname: str) -> Tuple[bool, str]:
        """
        Регистрация новой компании с первым администратором
        
        Args:
            company_name: Название компании
            phone: Номер телефона
            email: Email компании
            admin_username: Логин администратора
            admin_password: Пароль администратора
            admin_fullname: Полное имя администратора
            
        Returns:
            tuple[bool, str]: (успех, сообщение)
        """
        company_id = None
        try:
            admin_username = admin_username.strip()
            admin_username_norm = admin_username.lower()

            # Проверяем уникальность username
            check_user = self.db.client.table('users').select('id').eq(
                'username', admin_username_norm
            ).execute()
            
            if check_user.data and len(check_user.data) > 0:
                return False, "Пользователь с таким логином уже существует"
            
            # Создаем компанию
            company_payload = {
                'name': company_name,
                'phone': phone,
                'email': email,
                'license_valid_until': '2027-12-31',  # 1 год с момента регистрации
                'max_vehicles': 50  # По умолчанию 50 единиц техники
            }

            try:
                company_result = self.db.client.table('companies').insert(company_payload).execute()
            except Exception as company_insert_error:
                # Для старой схемы БД: колонок phone/email может не быть
                company_error = str(company_insert_error).lower()
                if 'column' in company_error and ('phone' in company_error or 'email' in company_error):
                    fallback_payload = {
                        'name': company_name,
                        'license_valid_until': '2027-12-31',
                        'max_vehicles': 50
                    }
                    company_result = self.db.client.table('companies').insert(fallback_payload).execute()
                else:
                    raise
            
            if not company_result.data:
                return False, "Не удалось создать организацию"
            
            company_id = company_result.data[0]['id']
            
            # Хешируем пароль
            password_hash = self.hash_password(admin_password)
            
            # Создаем администратора
            user_result = self.db.client.table('users').insert({
                'company_id': company_id,
                'username': admin_username_norm,
                'password_hash': password_hash,
                'full_name': admin_fullname,
                'role': 'admin',
                'is_active': True
            }).execute()
            
            if not user_result.data:
                # Откатываем создание компании
                self.db.client.table('companies').delete().eq('id', company_id).execute()
                return False, "Не удалось создать пользователя администратора"
            
            return True, "Организация успешно зарегистрирована"
            
        except Exception as e:
            # Откат компании, если успели создать
            if company_id:
                try:
                    self.db.client.table('companies').delete().eq('id', company_id).execute()
                except Exception:
                    pass

            error_text = str(e).lower()
            if 'users_username_key' in error_text or 'duplicate key value violates unique constraint' in error_text:
                return False, "Пользователь с таким логином уже существует"
            if 'column' in error_text and ('phone' in error_text or 'email' in error_text):
                return False, "База данных не обновлена: отсутствуют поля phone/email в таблице companies. Выполните migration_add_company_contacts.sql"

            print(f"Ошибка при регистрации компании: {e}")
            return False, f"Ошибка регистрации: {e}"
