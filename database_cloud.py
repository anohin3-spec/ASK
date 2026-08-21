"""
Модуль для работы с облачной базой данных Supabase
"""
from supabase import create_client, Client
from dotenv import load_dotenv
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from collections import defaultdict
from uuid import uuid4
import time
from app_config import (
    DEFAULT_SUPABASE_URL,
    DEFAULT_SUPABASE_KEY,
    DEFAULT_SUPABASE_INVOICES_BUCKET,
)

# Загружаем переменные окружения
load_dotenv()

class DatabaseCloud:
    """Адаптер для работы с Supabase (облачной PostgreSQL базой)"""
    
    def __init__(self):
        """Инициализация подключения к Supabase"""
        self.supabase_url = os.getenv('SUPABASE_URL', DEFAULT_SUPABASE_URL)
        self.supabase_key = os.getenv('SUPABASE_KEY', DEFAULT_SUPABASE_KEY)
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL и SUPABASE_KEY должны быть указаны в .env или app_config.py")

        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        self.company_id = '00000000-0000-0000-0000-000000000001'  # Тестовая компания по умолчанию
        self.user_id = None  # Будет установлен после авторизации
        self.invoices_bucket = os.getenv('SUPABASE_INVOICES_BUCKET', DEFAULT_SUPABASE_INVOICES_BUCKET)
    
    def set_company(self, company_id: str):
        """Установить текущую компанию"""
        self.company_id = company_id

    def set_user(self, user_id: str):
        """Установить текущего пользователя"""
        self.user_id = user_id
    
    # ===== Методы для работы с техникой =====
    
    def add_equipment(self, name, sts_pts, reg_number, measurement_type='mileage', 
                     last_maintenance=0, current_value=0, maintenance_interval_summer=10000,
                     maintenance_interval_winter=7500, situation='', service='', 
                     insurance_date='', insurance_file_path='', diagnostic_card_date='',
                     diagnostic_card_file_path='', mkad_pass_date='', current_value_updated_at='',
                     sts_certificate='', sts_file_path='',
                     secondary_last_maintenance=0, secondary_current_value=0,
                     secondary_current_value_updated_at='', secondary_maintenance_interval=250,
                     has_kmu=False):
        """Добавление новой техники"""
        try:
            data = {
                'company_id': self.company_id,
                'name': name,
                'sts_pts': sts_pts,
                'reg_number': reg_number,
                'measurement_type': measurement_type,
                'last_maintenance': last_maintenance,
                'current_value': current_value,
                'maintenance_interval_summer': maintenance_interval_summer,
                'maintenance_interval_winter': maintenance_interval_winter,
                'situation': situation,
                'service': service,
                'insurance_date': insurance_date,
                'insurance_file_path': insurance_file_path,
                'diagnostic_card_date': diagnostic_card_date,
                'diagnostic_card_file_path': diagnostic_card_file_path,
                'mkad_pass_date': mkad_pass_date,
                'current_value_updated_at': current_value_updated_at,
                'secondary_last_maintenance': secondary_last_maintenance,
                'secondary_current_value': secondary_current_value,
                'secondary_current_value_updated_at': secondary_current_value_updated_at,
                'secondary_maintenance_interval': secondary_maintenance_interval,
                'has_kmu': bool(has_kmu),
                'sts_certificate': sts_certificate,
                'sts_file_path': sts_file_path,
            }
            
            try:
                result = self.client.table('equipment').insert(data).execute()
            except Exception as insert_error:
                err = str(insert_error).lower()
                retry = False
                if "current_value_updated_at" in err:
                    raise RuntimeError(
                        "В таблице equipment отсутствует поле current_value_updated_at. "
                        "Выполните миграцию: migration_add_equipment_current_value_updated_at.sql"
                    ) from insert_error
                if "secondary_" in err:
                    raise RuntimeError(
                        "В таблице equipment отсутствуют поля для доп. счетчика (КМУ). "
                        "Выполните миграцию: migration_add_equipment_secondary_counter.sql"
                    ) from insert_error
                if "sts_certificate" in err or "sts_file_path" in err:
                    data.pop('sts_certificate', None)
                    data.pop('sts_file_path', None)
                    retry = True
                if retry:
                    result = self.client.table('equipment').insert(data).execute()
                else:
                    raise insert_error
            return result.data[0]['id'] if result.data else None
        except Exception as e:
            if 'duplicate key' in str(e).lower():
                raise ValueError(f"Техника с номером {reg_number} уже существует")
            raise e
    
    def update_equipment(self, equipment_id, **kwargs):
        """Обновление данных техники"""
        allowed_fields = ['name', 'sts_pts', 'reg_number', 'measurement_type',
                         'last_maintenance', 'current_value', 'maintenance_interval_summer',
                         'maintenance_interval_winter', 'next_maintenance', 'situation', 
                         'sort_order',
                         'service', 'insurance_date', 'insurance_file_path',
                         'diagnostic_card_date', 'diagnostic_card_file_path', 'mkad_pass_date',
                         'current_value_updated_at', 'sts_certificate', 'sts_file_path',
                         'secondary_last_maintenance', 'secondary_current_value',
                         'secondary_current_value_updated_at', 'secondary_maintenance_interval',
                         'has_kmu']
        
        fields_to_update = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not fields_to_update:
            return
        
        fields_to_update['updated_at'] = datetime.now().isoformat()
        
        try:
            self.client.table('equipment').update(fields_to_update).eq('id', equipment_id).execute()
        except Exception as update_error:
            err = str(update_error).lower()
            retry = False
            if 'current_value_updated_at' in err and 'current_value_updated_at' in fields_to_update:
                raise RuntimeError(
                    "В таблице equipment отсутствует поле current_value_updated_at. "
                    "Выполните миграцию: migration_add_equipment_current_value_updated_at.sql"
                ) from update_error
            if 'secondary_' in err and (
                'secondary_last_maintenance' in fields_to_update
                or 'secondary_current_value' in fields_to_update
                or 'secondary_current_value_updated_at' in fields_to_update
                or 'secondary_maintenance_interval' in fields_to_update
            ):
                raise RuntimeError(
                    "В таблице equipment отсутствуют поля для доп. счетчика (КМУ). "
                    "Выполните миграцию: migration_add_equipment_secondary_counter.sql"
                ) from update_error
            if ('sts_certificate' in err or 'sts_file_path' in err) and (
                'sts_certificate' in fields_to_update or 'sts_file_path' in fields_to_update
            ):
                fields_to_update.pop('sts_certificate', None)
                fields_to_update.pop('sts_file_path', None)
                retry = True
            if retry and fields_to_update:
                fields_to_update['updated_at'] = datetime.now().isoformat()
                self.client.table('equipment').update(fields_to_update).eq('id', equipment_id).execute()
            else:
                raise update_error
    
    def get_equipment(self, equipment_id):
        """Получение техники по ID"""
        result = self.client.table('equipment').select('*').eq('id', equipment_id).single().execute()
        return result.data if result.data else None
    
    def get_all_equipment(self):
        """Получение всей техники текущей компании"""
        result = self.client.table('equipment')\
            .select('*')\
            .eq('company_id', self.company_id)\
            .order('sort_order', desc=True)\
            .order('id')\
            .execute()
        return result.data if result.data else []
    
    def delete_equipment(self, equipment_id):
        """Удаление техники"""
        self.client.table('equipment').delete().eq('id', equipment_id).execute()
    
    def move_equipment_up(self, equipment_id):
        """Переместить технику вверх в списке"""
        equipment = self.get_equipment(equipment_id)
        if equipment:
            current_order = equipment.get('sort_order', 0)
            self.update_equipment(equipment_id, sort_order=current_order + 1)
    
    def move_equipment_down(self, equipment_id):
        """Переместить технику вниз в списке"""
        equipment = self.get_equipment(equipment_id)
        if equipment:
            current_order = equipment.get('sort_order', 0)
            self.update_equipment(equipment_id, sort_order=current_order - 1)
    
    # ===== Методы для работы с компанией =====
    
    def get_company(self, company_id: str = None) -> Optional[Dict[str, Any]]:
        """Получение данных компании по ID"""
        if company_id is None:
            company_id = self.company_id
        
        try:
            result = self.client.table('companies').select('*').eq('id', company_id).single().execute()
            company_data = result.data if result.data else None
            print(f"DEBUG: get_company('{company_id}') = {company_data}")
            return company_data
        except Exception as e:
            error_msg = str(e).lower()
            # Для старой схемы БД: колонок phone/email может не быть
            if 'column' in error_msg and ('phone' in error_msg or 'email' in error_msg):
                try:
                    # Пробуем получить только основные поля
                    result = self.client.table('companies').select(
                        'id, name, license_valid_until, max_vehicles'
                    ).eq('id', company_id).single().execute()
                    company_data = result.data if result.data else None
                    print(f"DEBUG: get_company fallback('{company_id}') = {company_data}")
                    return company_data
                except Exception as fallback_error:
                    print(f"Ошибка при fallback получении компании: {fallback_error}")
                    return None
            print(f"Ошибка при получении данных компании: {e}")
            return None
    
    def update_company(self, company_id: str, **kwargs):
        """Обновление данных компании"""
        allowed_fields = ['name', 'phone', 'email', 'license_valid_until', 'max_vehicles']
        
        fields_to_update = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        print(f"DEBUG: update_company('{company_id}') с полями: {fields_to_update}")
        
        if not fields_to_update:
            print("DEBUG: Нет полей для обновления")
            return False
        
        try:
            self.client.table('companies').update(fields_to_update).eq('id', company_id).execute()
            print(f"DEBUG: Компания успешно обновлена")
            return True
        except Exception as e:
            error_msg = str(e).lower()
            # Для старой схемы БД: колонок phone/email может не быть
            if 'column' in error_msg and ('phone' in error_msg or 'email' in error_msg):
                # Пробуем обновить только name, если есть
                fallback_fields = {k: v for k, v in fields_to_update.items() if k == 'name'}
                if fallback_fields:
                    try:
                        self.client.table('companies').update(fallback_fields).eq('id', company_id).execute()
                        print("DEBUG: Обновлено только название компании (старая схема БД без phone/email)")
                        return True
                    except Exception as fallback_error:
                        print(f"Ошибка при fallback обновлении: {fallback_error}")
                        return False
            print(f"Ошибка при обновлении данных компании: {e}")
            return False
    
    # ===== Методы для работы с водителями =====
    
    def add_driver(self, name, phone, fuel_card=''):
        """Добавление нового водителя"""
        data = {
            'company_id': self.company_id,
            'name': name,
            'phone': phone,
            'fuel_card': fuel_card
        }
        result = self.client.table('drivers').insert(data).execute()
        return result.data[0]['id'] if result.data else None
    
    def update_driver(self, driver_id, name, phone, fuel_card=''):
        """Обновление водителя"""
        data = {'name': name, 'phone': phone, 'fuel_card': fuel_card}
        self.client.table('drivers').update(data).eq('id', driver_id).execute()
    
    def get_driver(self, driver_id):
        """Получение водителя по ID"""
        result = self.client.table('drivers').select('*').eq('id', driver_id).single().execute()
        return result.data if result.data else None
    
    def get_all_drivers(self):
        """Получение всех водителей текущей компании"""
        result = self.client.table('drivers')\
            .select('*')\
            .eq('company_id', self.company_id)\
            .order('id')\
            .execute()
        return result.data if result.data else []
    
    def delete_driver(self, driver_id):
        """Удаление водителя"""
        self.client.table('drivers').delete().eq('id', driver_id).execute()
    
    # ===== Методы для привязки водителей к технике =====
    
    def assign_driver_to_equipment(self, equipment_id, driver_id, is_primary=False):
        """Привязка водителя к технике"""
        try:
            data = {
                'equipment_id': equipment_id,
                'driver_id': driver_id,
                'is_primary': is_primary
            }
            self.client.table('equipment_drivers').insert(data).execute()
        except Exception as e:
            if 'duplicate key' in str(e).lower():
                # Уже привязан, игнорируем
                pass
            else:
                raise e
    
    def remove_driver_from_equipment(self, equipment_id, driver_id):
        """Отвязка водителя от техники"""
        self.client.table('equipment_drivers')\
            .delete()\
            .eq('equipment_id', equipment_id)\
            .eq('driver_id', driver_id)\
            .execute()
    
    def get_equipment_drivers(self, equipment_id):
        """Получение водителей техники"""
        result = self.client.table('equipment_drivers')\
            .select('*, drivers(*)')\
            .eq('equipment_id', equipment_id)\
            .execute()
        
        drivers = []
        if result.data:
            for item in result.data:
                driver_data = item.get('drivers', {})
                if driver_data:
                    driver_data['is_primary'] = item.get('is_primary', False)
                    drivers.append(driver_data)
        return drivers
    
    def get_driver_equipment(self, driver_id):
        """Получение техники водителя"""
        result = self.client.table('equipment_drivers')\
            .select('*, equipment(*)')\
            .eq('driver_id', driver_id)\
            .execute()
        
        equipment_list = []
        if result.data:
            for item in result.data:
                eq_data = item.get('equipment', {})
                if eq_data:
                    equipment_list.append(eq_data)
        return equipment_list

    def get_equipment_names_by_driver_id(self):
        """Словарь driver_id -> [\"Техника (Номер)\", ...] одним запросом по компании."""
        result = self.client.table('equipment_drivers').select(
            'driver_id, equipment!inner(name,reg_number,company_id)'
        ).eq('equipment.company_id', self.company_id).execute()
        mapping = defaultdict(list)
        for row in result.data or []:
            eq = row.get('equipment') or {}
            if not eq:
                continue
            mapping[str(row.get('driver_id'))].append(f"{eq.get('name', '-')}" + f" ({eq.get('reg_number', '-')})")
        return dict(mapping)
    
    def clear_equipment_drivers(self, equipment_id):
        """Удаление всех водителей техники"""
        self.client.table('equipment_drivers')\
            .delete()\
            .eq('equipment_id', equipment_id)\
            .execute()
    
    def set_driver_shift(self, equipment_id, driver_id, shift_half=None):
        """Установка смены для водителя (1 - первая половина, 2 - вторая, None - весь месяц)"""
        try:
            # Проверяем, существует ли связь
            existing = self.client.table('equipment_drivers')\
                .select('*')\
                .eq('equipment_id', equipment_id)\
                .eq('driver_id', driver_id)\
                .execute()
            
            if existing.data:
                # Обновляем существующую запись
                self.client.table('equipment_drivers')\
                    .update({'shift_half': shift_half})\
                    .eq('equipment_id', equipment_id)\
                    .eq('driver_id', driver_id)\
                    .execute()
            else:
                # Создаём новую запись
                data = {
                    'equipment_id': equipment_id,
                    'driver_id': driver_id,
                    'shift_half': shift_half,
                    'is_primary': False
                }
                self.client.table('equipment_drivers').insert(data).execute()
        except Exception as e:
            print(f"Ошибка установки смены: {e}")
            raise e
    
    def get_current_shift_half(self):
        """Определение текущей половины месяца"""
        import calendar
        from datetime import datetime
        
        today = datetime.now().day
        year = datetime.now().year
        month = datetime.now().month
        days_in_month = calendar.monthrange(year, month)[1]
        
        # Середина месяца
        mid_day = days_in_month // 2
        
        return 1 if today <= mid_day else 2
    
    def get_current_driver_for_equipment(self, equipment_id):
        """Получение текущего активного водителя с учётом смены"""
        current_shift = self.get_current_shift_half()
        
        # Получаем всех водителей техники
        result = self.client.table('equipment_drivers')\
            .select('*, drivers(*)')\
            .eq('equipment_id', equipment_id)\
            .execute()
        
        if not result.data:
            return None
        
        # Ищем водителя текущей смены или без смены (весь месяц)
        current_driver = None
        full_month_driver = None
        
        for item in result.data:
            driver_data = item.get('drivers', {})
            shift_half = item.get('shift_half')
            
            if shift_half == current_shift:
                current_driver = driver_data
                current_driver['shift_half'] = shift_half
                current_driver['is_active'] = True
            elif shift_half is None:
                full_month_driver = driver_data
                full_month_driver['shift_half'] = None
                full_month_driver['is_active'] = True
        
        return current_driver or full_month_driver
    
    def get_all_drivers_for_equipment_with_shifts(self, equipment_id):
        """Получение всех водителей техники с указанием текущего активного"""
        current_shift = self.get_current_shift_half()
        
        result = self.client.table('equipment_drivers')\
            .select('*, drivers(*)')\
            .eq('equipment_id', equipment_id)\
            .execute()
        
        drivers = []
        if result.data:
            for item in result.data:
                driver_data = item.get('drivers', {})
                if driver_data:
                    shift_half = item.get('shift_half')
                    driver_data['shift_half'] = shift_half
                    driver_data['is_primary'] = item.get('is_primary', False)
                    
                    # Определяем, активен ли водитель сейчас
                    if shift_half == current_shift or shift_half is None:
                        driver_data['is_active'] = True
                    else:
                        driver_data['is_active'] = False
                    
                    drivers.append(driver_data)
        
        return drivers

    
    # ===== Методы для работы с ТО =====

    def upload_invoice_file(self, source_file_path: str, reg_number: str) -> str:
        """Загрузка файла счета в Supabase Storage и возврат cloud-пути"""
        extension = os.path.splitext(source_file_path)[1].lower()
        if not extension:
            extension = '.bin'

        normalized_reg = str(reg_number or '').lower()
        safe_reg_number = ''.join(ch if ('a' <= ch <= 'z') or ('0' <= ch <= '9') else '_' for ch in normalized_reg)
        safe_reg_number = safe_reg_number.strip('_') or 'invoice'

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        object_path = f"{self.company_id}/{safe_reg_number}_{timestamp}_{uuid4().hex[:8]}{extension}"

        from pdf_compress import read_file_bytes_for_upload

        file_bytes = read_file_bytes_for_upload(source_file_path)

        bucket = self.client.storage.from_(self.invoices_bucket)
        try:
            bucket.upload(
                path=object_path,
                file=file_bytes,
                file_options={"upsert": "false", "content-type": "application/octet-stream"}
            )
        except TypeError:
            bucket.upload(
                object_path,
                file_bytes,
                {"upsert": "false", "content-type": "application/octet-stream"}
            )

        return f"supabase://{self.invoices_bucket}/{object_path}"

    def delete_storage_file(self, supabase_uri: str) -> None:
        """Удаляет объект в Supabase Storage по пути supabase://bucket/ключ/внутри/бакета."""
        if not supabase_uri or not str(supabase_uri).startswith('supabase://'):
            return
        try:
            path_without_schema = str(supabase_uri)[len('supabase://'):]
            if '/' not in path_without_schema:
                return
            bucket_name, object_path = path_without_schema.split('/', 1)
            if not object_path:
                return
            self.client.storage.from_(bucket_name).remove([object_path])
        except Exception:
            pass

    def _invoice_bucket_object_key(self, supabase_uri: str) -> Optional[str]:
        """Ключ объекта в бакете счетов (company_id/...), только для текущей компании."""
        if not supabase_uri or not str(supabase_uri).startswith('supabase://'):
            return None
        rest = str(supabase_uri)[len('supabase://') :]
        if '/' not in rest:
            return None
        bucket_name, object_path = rest.split('/', 1)
        if bucket_name != self.invoices_bucket or not object_path:
            return None
        cid = str(self.company_id)
        if not object_path.startswith(cid + '/'):
            return None
        return object_path

    def collect_referenced_invoice_storage_keys(self) -> set[str]:
        """Все ключи объектов в бакете счетов, на которые есть ссылки в БД (текущая компания)."""
        refs: set[str] = set()
        bucket = self.invoices_bucket

        def add_uri(u: Any) -> None:
            if not u:
                return
            p = self._invoice_bucket_object_key(str(u))
            if p:
                refs.add(p)

        for eq in self.get_all_equipment():
            add_uri(eq.get('insurance_file_path'))
            add_uri(eq.get('diagnostic_card_file_path'))
            add_uri(eq.get('sts_file_path'))

        eq_ids = [e['id'] for e in self.get_all_equipment()]
        if eq_ids:
            for i in range(0, len(eq_ids), 80):
                chunk = eq_ids[i : i + 80]
                r = self.client.table('maintenance_history').select('invoice_path').in_('equipment_id', chunk).execute()
                for row in r.data or []:
                    add_uri(row.get('invoice_path'))

        eq_set = set(eq_ids)
        iss = self.client.table('issues').select('resolution_invoice_path, equipment_id').execute()
        for row in iss.data or []:
            if row.get('equipment_id') in eq_set:
                add_uri(row.get('resolution_invoice_path'))

        return refs

    def cleanup_orphan_invoice_storage(self) -> Dict[str, Any]:
        """
        Удаляет в бакете счетов объекты с префиксом company_id/, на которые нет ссылок в БД
        (осиротевшие после смены файлов и т.п.).
        """
        refs = self.collect_referenced_invoice_storage_keys()
        cid = str(self.company_id)
        prefix = f"{cid}/"
        bucket = self.client.storage.from_(self.invoices_bucket)

        to_delete: List[str] = []
        offset = 0
        limit = 100

        while True:
            try:
                items = bucket.list(
                    prefix,
                    {
                        'limit': limit,
                        'offset': offset,
                        'sortBy': {'column': 'name', 'order': 'asc'},
                    },
                )
            except Exception as e:
                return {'deleted': 0, 'errors': [str(e)[:300]], 'orphans_found': 0}

            if not items:
                break

            for item in items:
                if not item.get('metadata'):
                    continue
                name = (item.get('name') or '').lstrip('/')
                if not name:
                    continue
                if name.startswith(cid + '/'):
                    key = name
                else:
                    key = f"{cid}/{name}".replace('//', '/')

                if key not in refs:
                    to_delete.append(key)

            if len(items) < limit:
                break
            offset += limit

        deleted = 0
        errors: List[str] = []
        batch_size = 50
        for i in range(0, len(to_delete), batch_size):
            batch = to_delete[i : i + batch_size]
            try:
                bucket.remove(batch)
                deleted += len(batch)
            except Exception:
                for path in batch:
                    try:
                        bucket.remove([path])
                        deleted += 1
                    except Exception as e2:
                        errors.append(f'{path}: {str(e2)[:120]}')

        return {
            'deleted': deleted,
            'orphans_found': len(to_delete),
            'referenced_in_db': len(refs),
            'errors': errors[:15],
        }

    def resolve_invoice_path(self, invoice_path: str) -> str:
        """Преобразование cloud-пути счета в ссылку для открытия"""
        if not invoice_path or not str(invoice_path).startswith('supabase://'):
            return invoice_path

        path_without_schema = str(invoice_path)[len('supabase://'):]
        if '/' not in path_without_schema:
            return ''

        bucket_name, object_path = path_without_schema.split('/', 1)
        bucket = self.client.storage.from_(bucket_name)

        try:
            signed = bucket.create_signed_url(object_path, 3600)
            if isinstance(signed, dict):
                return signed.get('signedURL') or signed.get('signedUrl') or signed.get('data', {}).get('signedUrl') or ''
            if isinstance(signed, str):
                return signed
        except Exception:
            pass

        try:
            public = bucket.get_public_url(object_path)
            if isinstance(public, dict):
                return public.get('publicURL') or public.get('publicUrl') or public.get('data', {}).get('publicUrl') or ''
            return public
        except Exception:
            return ''

    def _recalculate_equipment_maintenance(self, equipment_id):
        """Пересчет последнего ТО и текущего значения по истории ТО"""
        result_all = self.client.table('maintenance_history')\
            .select('maintenance_value,counter_type')\
            .eq('equipment_id', equipment_id)\
            .order('maintenance_date', desc=True)\
            .order('id', desc=True)\
            .limit(200)\
            .execute()
        result_secondary = self.client.table('maintenance_history')\
            .select('maintenance_value')\
            .eq('equipment_id', equipment_id)\
            .eq('counter_type', 'kmu')\
            .order('maintenance_date', desc=True)\
            .order('id', desc=True)\
            .limit(1)\
            .execute()

        latest_primary = next(
            (
                row
                for row in (result_all.data or [])
                if str(row.get('counter_type') or '').strip().lower() in ('', 'primary')
            ),
            None,
        )
        latest_secondary = result_secondary.data[0] if result_secondary.data else None
        latest_primary_value = int(latest_primary['maintenance_value']) if latest_primary else 0
        latest_secondary_value = int(latest_secondary['maintenance_value']) if latest_secondary else 0

        self.client.table('equipment').update({
            'last_maintenance': latest_primary_value,
            'current_value': latest_primary_value,
            'secondary_last_maintenance': latest_secondary_value,
            'secondary_current_value': latest_secondary_value,
        }).eq('id', equipment_id).execute()
    
    def add_maintenance(
        self,
        equipment_id,
        maintenance_value,
        maintenance_date=None,
        comment='',
        invoice_path='',
        counter_type='primary',
    ):
        """Добавление записи о ТО"""
        if maintenance_date is None:
            maintenance_date = datetime.now().isoformat()
        normalized_counter_type = 'kmu' if str(counter_type).strip().lower() == 'kmu' else 'primary'

        data = {
            'equipment_id': equipment_id,
            'maintenance_value': maintenance_value,
            'counter_type': normalized_counter_type,
            'maintenance_date': maintenance_date,
            'comment': comment,
            'invoice_path': invoice_path,
            'created_by': self.user_id
        }
        result = self.client.table('maintenance_history').insert(data).execute()
        maintenance_id = result.data[0]['id'] if result.data else None
        self._recalculate_equipment_maintenance(equipment_id)
        return maintenance_id

    def update_maintenance(
        self,
        maintenance_id,
        maintenance_value,
        maintenance_date,
        comment='',
        invoice_path='',
        counter_type='primary',
    ):
        """Обновление записи о ТО"""
        existing = self.client.table('maintenance_history')\
            .select('id, equipment_id')\
            .eq('id', maintenance_id)\
            .single()\
            .execute()

        if not existing.data:
            raise ValueError('Запись ТО не найдена')

        equipment_id = existing.data['equipment_id']
        normalized_counter_type = 'kmu' if str(counter_type).strip().lower() == 'kmu' else 'primary'
        self.client.table('maintenance_history').update({
            'maintenance_value': maintenance_value,
            'counter_type': normalized_counter_type,
            'maintenance_date': maintenance_date,
            'comment': comment,
            'invoice_path': invoice_path
        }).eq('id', maintenance_id).execute()

        self._recalculate_equipment_maintenance(equipment_id)
        return maintenance_id
    
    def get_equipment_maintenance_history(self, equipment_id):
        """Получение истории ТО техники"""
        result = self.client.table('maintenance_history')\
            .select('*')\
            .eq('equipment_id', equipment_id)\
            .order('maintenance_date', desc=True)\
            .execute()
        return result.data if result.data else []
    
    def get_all_maintenance(self):
        """Получение всей истории ТО для текущей компании"""
        # Получаем через JOIN с equipment
        result = self.client.table('maintenance_history')\
            .select('*, equipment!inner(*)')\
            .eq('equipment.company_id', self.company_id)\
            .order('maintenance_date', desc=True)\
            .execute()

        maintenance_list = result.data if result.data else []

        # Совместимость с локальной БД: добавляем плоские поля equipment_name/reg_number
        normalized = []
        for maint in maintenance_list:
            item = dict(maint)
            equipment = item.get('equipment') or {}
            item['equipment_name'] = equipment.get('name', '-')
            item['reg_number'] = equipment.get('reg_number', '-')
            normalized.append(item)

        return normalized
    
    def get_all_maintenance_history(self):
        """Алиас для get_all_maintenance (для совместимости)"""
        return self.get_all_maintenance()
    
    # ===== Методы для работы с неисправностями =====
    
    def add_issue(self, equipment_id, description, driver_id=None, resolution_invoice_path=''):
        """Добавление неисправности"""
        data = {
            'equipment_id': equipment_id,
            'driver_id': driver_id,
            'description': description,
            'resolution_invoice_path': resolution_invoice_path,
            'created_by': self.user_id
        }
        result = self.client.table('issues').insert(data).execute()
        return result.data[0]['id'] if result.data else None

    def get_issue(self, issue_id):
        """Получение одной неисправности текущей компании."""
        result = self.client.table('issues')\
            .select('*, equipment!inner(company_id)')\
            .eq('id', issue_id)\
            .eq('equipment.company_id', self.company_id)\
            .limit(1)\
            .execute()
        if not result.data:
            return None
        row = dict(result.data[0])
        row.pop('equipment', None)
        return row

    def update_issue(self, issue_id, equipment_id, description, driver_id=None, resolution_invoice_path=''):
        """Редактирование неисправности (без смены статуса)."""
        data = {
            'equipment_id': equipment_id,
            'driver_id': driver_id,
            'description': description,
            'resolution_invoice_path': resolution_invoice_path,
        }
        self.client.table('issues').update(data).eq('id', issue_id).execute()
    
    def update_issue_status(self, issue_id, status, resolution_comment='', resolution_invoice_path=''):
        """Обновление статуса неисправности"""
        data = {
            'status': status,
            'resolution_comment': resolution_comment,
            'resolution_invoice_path': resolution_invoice_path
        }
        if status == 'resolved':
            data['resolved_date'] = datetime.now().isoformat()
        
        self.client.table('issues').update(data).eq('id', issue_id).execute()
    
    def get_equipment_issues(self, equipment_id, status=None):
        """Получение неисправностей техники"""
        query = self.client.table('issues')\
            .select('*, drivers(name, phone)')\
            .eq('equipment_id', equipment_id)
        
        if status:
            query = query.eq('status', status)
        
        query = query.order('reported_date', desc=True)
        result = query.execute()
        
        # Преобразуем вложенные данные
        issues = []
        if result.data:
            for issue in result.data:
                driver_data = issue.pop('drivers', None)
                if driver_data:
                    issue['driver_name'] = driver_data.get('name')
                    issue['driver_phone'] = driver_data.get('phone')
                else:
                    issue['driver_name'] = None
                    issue['driver_phone'] = None
                issues.append(issue)
        return issues

    def get_open_issues_grouped_by_equipment_id(self) -> Dict[str, List[Dict[str, Any]]]:
        """Все открытые неисправности одним запросом (для таблицы техники без N+1)."""
        result = self.client.table('issues').select(
            'equipment_id, description, equipment!inner(company_id)'
        ).eq('status', 'open').eq('equipment.company_id', self.company_id).execute()
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in result.data or []:
            eid = row.get('equipment_id')
            if eid is not None:
                grouped[str(eid)].append(row)
        return dict(grouped)

    def get_active_driver_name_by_equipment_id(self) -> Dict[str, str]:
        """Активный водитель по смене для каждой техники — один запрос вместо N вызовов."""
        current_shift = self.get_current_shift_half()
        result = self.client.table('equipment_drivers').select(
            'equipment_id, shift_half, is_primary, drivers(name,id), equipment!inner(company_id)'
        ).eq('equipment.company_id', self.company_id).execute()
        by_eq: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for item in result.data or []:
            dd = item.get('drivers') or {}
            if not dd:
                continue
            name = dd.get('name') or '-'
            shift_half = item.get('shift_half')
            by_eq[str(item['equipment_id'])].append({
                'name': name,
                'shift_half': shift_half,
                'is_active': (shift_half == current_shift or shift_half is None),
            })
        out: Dict[str, str] = {}
        for eid, drivers in by_eq.items():
            active = next((d for d in drivers if d.get('is_active')), None)
            out[eid] = active['name'] if active else (drivers[0]['name'] if drivers else '-')
        return out
    
    def get_all_issues(self, status=None):
        """Получение всех неисправностей для текущей компании"""
        query = self.client.table('issues')\
            .select('*, equipment!inner(name, reg_number, company_id), drivers(name, phone)')\
            .eq('equipment.company_id', self.company_id)
        
        if status:
            query = query.eq('status', status)
        
        query = query.order('reported_date', desc=True)
        
        # Повторные попытки при таймауте с увеличивающейся задержкой
        max_retries = 5
        for attempt in range(max_retries):
            try:
                result = query.execute()
                break
            except Exception as e:
                error_msg = str(e).lower()
                if ('timeout' in error_msg or 'timed out' in error_msg) and attempt < max_retries - 1:
                    time.sleep(1 + attempt)  # Задержка 1, 2, 3, 4 секунды
                    continue
                raise
        
        # Преобразуем данные
        issues = []
        if result.data:
            for issue in result.data:
                eq_data = issue.pop('equipment', {})
                driver_data = issue.pop('drivers', None)
                
                issue['equipment_name'] = eq_data.get('name')
                issue['reg_number'] = eq_data.get('reg_number')
                
                if driver_data:
                    issue['driver_name'] = driver_data.get('name')
                    issue['driver_phone'] = driver_data.get('phone')
                else:
                    issue['driver_name'] = None
                    issue['driver_phone'] = None
                
                issues.append(issue)
        return issues
    
    def delete_issue(self, issue_id):
        """Удаление неисправности"""
        self.client.table('issues').delete().eq('id', issue_id).execute()
    
    # ===== Методы для настроек =====
    
    def set_setting(self, key, value):
        """Установка настройки"""
        try:
            print(f"DEBUG: set_setting('{key}', '{value}') для company_id={self.company_id}")
            
            # Проверяем, существует ли настройка
            existing = self.client.table('settings')\
                .select('id')\
                .eq('company_id', self.company_id)\
                .eq('key', key)\
                .execute()
            
            data = {
                'company_id': self.company_id,
                'key': key,
                'value': value
            }
            
            if existing.data and len(existing.data) > 0:
                # Обновляем существующую запись
                print(f"DEBUG: Обновление существующей записи для ключа '{key}'")
                self.client.table('settings')\
                    .update({'value': value})\
                    .eq('company_id', self.company_id)\
                    .eq('key', key)\
                    .execute()
            else:
                # Вставляем новую запись
                print(f"DEBUG: Вставка новой записи для ключа '{key}'")
                self.client.table('settings').insert(data).execute()
            
            print(f"DEBUG: set_setting успешно выполнен для '{key}'")
                
        except Exception as e:
            print(f"Ошибка при сохранении настройки {key}: {e}")
            raise
    
    def get_setting(self, key, default=None):
        """Получение настройки"""
        try:
            result = self.client.table('settings')\
                .select('value')\
                .eq('company_id', self.company_id)\
                .eq('key', key)\
                .execute()
            
            if result.data and len(result.data) > 0:
                value = result.data[0]['value']
                print(f"DEBUG: get_setting('{key}') = '{value}'")
                return value
            
            print(f"DEBUG: get_setting('{key}') not found, returning default: '{default}'")
            return default
        except Exception as e:
            print(f"Ошибка при получении настройки {key}: {e}")
            return default
    
    def close(self):
        """Закрытие соединения (для совместимости с SQLite версией)"""
        pass  # Supabase не требует явного закрытия
