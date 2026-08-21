"""
Модуль для управления регламентами технического обслуживания
Поддерживает облачное хранение в Supabase
"""
import os
from typing import Dict, Optional, List


class RegulationsManager:
    """Менеджер для работы с файлами регламентов ТО в облаке"""
    
    EQUIPMENT_TYPES = [
        "Case 570",
        "Hidromek",
        "Камаз",
        "FAW"
    ]
    
    def __init__(self, db):
        """
        Инициализация менеджера регламентов
        
        Args:
            db: Экземпляр базы данных (DatabaseCloud)
        """
        self.db = db
        self.bucket_name = 'regulations'
        
        # Инициализация bucket в Supabase Storage (если используется облако)
        if hasattr(self.db, 'client'):
            self._init_storage_bucket()
    
    def _init_storage_bucket(self):
        """Инициализация bucket для регламентов в Supabase Storage"""
        try:
            buckets = self.db.client.storage.list_buckets()
            bucket_exists = any(b.name == self.bucket_name for b in buckets)
            
            if not bucket_exists:
                self.db.client.storage.create_bucket(
                    self.bucket_name,
                    options={'public': True}
                )
        except Exception:
            pass
    
    def add_regulation(self, equipment_type: str, file_path: str, user_id: str = None) -> bool:
        """
        Добавление файла регламента для типа техники
        
        Args:
            equipment_type: Тип техники
            file_path: Путь к файлу регламента
            user_id: ID пользователя, загружающего файл
            
        Returns:
            True если успешно добавлено
        """
        if not os.path.exists(file_path):
            return False
        
        if not hasattr(self.db, 'client'):
            return False
        
        # Получаем расширение и имя файла
        original_filename = os.path.basename(file_path)
        _, ext = os.path.splitext(file_path)
        
        # Создаем безопасное имя файла для хранения
        safe_name = equipment_type.replace(" ", "_").replace("/", "_")
        storage_filename = f"{safe_name}{ext}"
        
        try:
            bucket = self.db.client.storage.from_(self.bucket_name)
            
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Удаляем старый файл если существует
            try:
                bucket.remove([storage_filename])
            except:
                pass
            
            # Загружаем новый файл
            bucket.upload(
                path=storage_filename,
                file=file_data,
                file_options={"content-type": self._get_mime_type(ext), "upsert": "true"}
            )
            
            # Формируем путь к файлу
            cloud_path = f"supabase://{self.bucket_name}/{storage_filename}"
            
            # Сохраняем метаданные в таблицу regulations
            existing = self.db.client.table('regulations')\
                .select('id')\
                .eq('equipment_type', equipment_type)\
                .execute()
            
            regulation_data = {
                'equipment_type': equipment_type,
                'file_path': cloud_path,
                'original_filename': original_filename,
                'uploaded_by': user_id
            }
            
            if existing.data:
                self.db.client.table('regulations')\
                    .update(regulation_data)\
                    .eq('equipment_type', equipment_type)\
                    .execute()
            else:
                self.db.client.table('regulations')\
                    .insert(regulation_data)\
                    .execute()
            
            return True
            
        except Exception:
            return False
    
    def _get_mime_type(self, ext: str) -> str:
        """Определение MIME типа по расширению файла"""
        mime_types = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg'
        }
        return mime_types.get(ext.lower(), 'application/octet-stream')
    
    def get_regulation_path(self, equipment_type: str) -> Optional[str]:
        """
        Получение пути к файлу регламента
        
        Args:
            equipment_type: Тип техники
            
        Returns:
            Путь к файлу в Storage или None если не найден
        """
        if not hasattr(self.db, 'client'):
            return None
        
        try:
            result = self.db.client.table('regulations')\
                .select('file_path')\
                .eq('equipment_type', equipment_type)\
                .execute()
            
            if result.data:
                return result.data[0]['file_path']
            return None
            
        except Exception as e:
            print(f"Ошибка получения регламента: {e}")
            return None
    
    def delete_regulation(self, equipment_type: str) -> bool:
        """
        Удаление регламента для типа техники
        
        Args:
            equipment_type: Тип техники
            
        Returns:
            True если успешно удалено
        """
        if not hasattr(self.db, 'client'):
            return False
        
        try:
            # Получаем путь к файлу
            result = self.db.client.table('regulations')\
                .select('file_path')\
                .eq('equipment_type', equipment_type)\
                .execute()
            
            if not result.data:
                return False
            
            file_path = result.data[0]['file_path']
            
            # Удаляем файл из Storage
            if file_path and file_path.startswith(f'supabase://{self.bucket_name}/'):
                filename = file_path.split('/')[-1]
                bucket = self.db.client.storage.from_(self.bucket_name)
                try:
                    bucket.remove([filename])
                except:
                    pass
            
            # Удаляем запись из таблицы
            self.db.client.table('regulations')\
                .delete()\
                .eq('equipment_type', equipment_type)\
                .execute()
            
            return True
            
        except Exception as e:
            print(f"Ошибка удаления регламента: {e}")
            return False
    
    def has_regulation(self, equipment_type: str) -> bool:
        """
        Проверка наличия регламента для типа техники
        
        Args:
            equipment_type: Тип техники
            
        Returns:
            True если регламент существует
        """
        return self.get_regulation_path(equipment_type) is not None
    
    def get_all_regulations(self) -> Dict[str, bool]:
        """
        Получение статуса наличия регламентов для всех типов техники
        
        Returns:
            Словарь {тип_техники: есть_регламент}
        """
        result = {}
        for eq_type in self.EQUIPMENT_TYPES:
            result[eq_type] = self.has_regulation(eq_type)
        return result
    
    def resolve_regulation_url(self, file_path: str) -> Optional[str]:
        """
        Преобразование cloud-пути регламента в публичную ссылку
        
        Args:
            file_path: Путь в формате supabase://regulations/filename
            
        Returns:
            Публичная URL для скачивания или None
        """
        if not file_path or not file_path.startswith(f'supabase://{self.bucket_name}/'):
            return None
        
        if not hasattr(self.db, 'client'):
            return None
        
        filename = file_path.split('/')[-1]
        
        try:
            bucket = self.db.client.storage.from_(self.bucket_name)
            public_url = bucket.get_public_url(filename)
            
            if isinstance(public_url, dict):
                return public_url.get('publicURL') or public_url.get('publicUrl') or ''
            return public_url
            
        except Exception as e:
            print(f"Ошибка получения URL регламента: {e}")
            return None
