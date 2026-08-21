"""
Менеджер сохранения учетных данных
Безопасное хранение логина и пароля для автоматического входа
"""
import os
import json
import base64
from cryptography.fernet import Fernet
from pathlib import Path


class CredentialsManager:
    """Управление сохраненными учетными данными"""
    
    def __init__(self):
        """Инициализация менеджера"""
        self.credentials_file = os.path.join(os.path.expanduser('~'), '.ask_credentials')
        self.key_file = os.path.join(os.path.expanduser('~'), '.ask_key')
        self._ensure_key()
    
    def _ensure_key(self):
        """Создание или загрузка ключа шифрования"""
        if not os.path.exists(self.key_file):
            # Создаем новый ключ
            key = Fernet.generate_key()
            
            # Удаляем старый файл если существует (для безопасности)
            if os.path.exists(self.key_file):
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetFileAttributesW(self.key_file, 128)  # FILE_ATTRIBUTE_NORMAL
                except:
                    pass
                os.remove(self.key_file)
            
            with open(self.key_file, 'wb') as f:
                f.write(key)
            
            # Скрываем файл (Windows)
            try:
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(self.key_file, 2)  # FILE_ATTRIBUTE_HIDDEN
            except:
                pass
        
        # Загружаем ключ
        with open(self.key_file, 'rb') as f:
            self.key = f.read()
        
        self.cipher = Fernet(self.key)
    
    def save_credentials(self, username: str, password: str, auto_login: bool = False):
        """
        Сохранение учетных данных
        
        Args:
            username: Имя пользователя
            password: Пароль
            auto_login: Флаг автоматического входа
        """
        try:
            data = {
                'username': username,
                'password': password,
                'auto_login': auto_login
            }
            
            # Конвертируем в JSON и шифруем
            json_data = json.dumps(data).encode('utf-8')
            encrypted_data = self.cipher.encrypt(json_data)
            
            # Удаляем старый файл если существует
            if os.path.exists(self.credentials_file):
                try:
                    # Снимаем атрибут "только чтение" (Windows)
                    import ctypes
                    ctypes.windll.kernel32.SetFileAttributesW(self.credentials_file, 128)  # FILE_ATTRIBUTE_NORMAL
                except:
                    pass
                os.remove(self.credentials_file)
            
            # Сохраняем в файл
            with open(self.credentials_file, 'wb') as f:
                f.write(encrypted_data)
            
            # Скрываем файл (Windows)
            try:
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(self.credentials_file, 2)  # FILE_ATTRIBUTE_HIDDEN
            except:
                pass
            
            return True
        except Exception as e:
            print(f"Ошибка сохранения учетных данных: {e}")
            return False
    
    def load_credentials(self):
        """
        Загрузка сохраненных учетных данных
        
        Returns:
            dict или None: {'username': str, 'password': str, 'auto_login': bool}
        """
        try:
            if not os.path.exists(self.credentials_file):
                return None
            
            # Читаем зашифрованные данные
            with open(self.credentials_file, 'rb') as f:
                encrypted_data = f.read()
            
            # Расшифровываем
            decrypted_data = self.cipher.decrypt(encrypted_data)
            data = json.loads(decrypted_data.decode('utf-8'))
            
            return data
        except Exception as e:
            print(f"Ошибка загрузки учетных данных: {e}")
            return None
    
    def clear_credentials(self):
        """Удаление сохраненных учетных данных"""
        try:
            if os.path.exists(self.credentials_file):
                # Снимаем атрибут "только чтение" (Windows)
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetFileAttributesW(self.credentials_file, 128)  # FILE_ATTRIBUTE_NORMAL
                except:
                    pass
                os.remove(self.credentials_file)
            return True
        except Exception as e:
            print(f"Ошибка удаления учетных данных: {e}")
            return False
    
    def has_saved_credentials(self) -> bool:
        """Проверка наличия сохраненных учетных данных"""
        return os.path.exists(self.credentials_file)
