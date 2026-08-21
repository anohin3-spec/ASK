"""
Модуль для работы с базой данных SQLite
"""
import calendar
import sqlite3
import os
from datetime import datetime
from collections import defaultdict


class Database:
    def __init__(self, db_path="maintenance.db"):
        """Инициализация базы данных"""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        """Подключение к базе данных"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
    
    def create_tables(self):
        """Создание таблиц базы данных"""
        # Таблица техники
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                sts_pts TEXT,
                reg_number TEXT UNIQUE NOT NULL,
                measurement_type TEXT NOT NULL DEFAULT 'mileage',
                last_maintenance INTEGER DEFAULT 0,
                current_value INTEGER DEFAULT 0,
                current_value_updated_at TEXT,
                secondary_last_maintenance INTEGER DEFAULT 0,
                secondary_current_value INTEGER DEFAULT 0,
                secondary_current_value_updated_at TEXT,
                secondary_maintenance_interval INTEGER DEFAULT 250,
                has_kmu INTEGER DEFAULT 0,
                maintenance_interval_summer INTEGER DEFAULT 10000,
                maintenance_interval_winter INTEGER DEFAULT 7500,
                next_maintenance INTEGER DEFAULT 0,
                situation TEXT,
                service TEXT,
                insurance_date TEXT,
                insurance_file_path TEXT,
                diagnostic_card_date TEXT,
                diagnostic_card_file_path TEXT,
                mkad_pass_date TEXT,
                sts_certificate TEXT,
                sts_file_path TEXT,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self._ensure_equipment_columns()
        
        # Таблица водителей
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS drivers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                fuel_card TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица привязки водителей к технике
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS equipment_drivers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id INTEGER NOT NULL,
                driver_id INTEGER NOT NULL,
                is_primary BOOLEAN DEFAULT 0,
                shift_half INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE CASCADE,
                FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE CASCADE,
                UNIQUE(equipment_id, driver_id)
            )
        ''')
        
        # Таблица истории ТО
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS maintenance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id INTEGER NOT NULL,
                maintenance_value INTEGER NOT NULL,
                counter_type TEXT NOT NULL DEFAULT 'primary',
                maintenance_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                comment TEXT,
                invoice_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE CASCADE
            )
        ''')
        
        # Таблица неисправностей
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id INTEGER NOT NULL,
                driver_id INTEGER,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                reported_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_date TIMESTAMP,
                resolution_comment TEXT,
                resolution_invoice_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE CASCADE,
                FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE SET NULL
            )
        ''')
        self._ensure_driver_and_issue_columns()
        self._ensure_equipment_drivers_shift_half()
        self._ensure_maintenance_columns()
        
        # Таблица настроек
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT
            )
        ''')
        
        self.conn.commit()

    def _ensure_equipment_columns(self):
        """Добавляет недостающие колонки в equipment для старых БД."""
        self.cursor.execute("PRAGMA table_info(equipment)")
        existing_columns = {row["name"] for row in self.cursor.fetchall()}

        required_columns = {
            "insurance_file_path": "TEXT",
            "diagnostic_card_date": "TEXT",
            "diagnostic_card_file_path": "TEXT",
            "current_value_updated_at": "TEXT",
            "sts_certificate": "TEXT",
            "sts_file_path": "TEXT",
            "secondary_last_maintenance": "INTEGER DEFAULT 0",
            "secondary_current_value": "INTEGER DEFAULT 0",
            "secondary_current_value_updated_at": "TEXT",
            "secondary_maintenance_interval": "INTEGER DEFAULT 250",
            "has_kmu": "INTEGER DEFAULT 0",
        }

        for column_name, column_type in required_columns.items():
            if column_name not in existing_columns:
                self.cursor.execute(
                    f"ALTER TABLE equipment ADD COLUMN {column_name} {column_type}"
                )

    def _ensure_driver_and_issue_columns(self):
        """Добавляет недостающие колонки в drivers/issues для старых БД."""
        self.cursor.execute("PRAGMA table_info(drivers)")
        driver_columns = {row["name"] for row in self.cursor.fetchall()}
        if "fuel_card" not in driver_columns:
            self.cursor.execute("ALTER TABLE drivers ADD COLUMN fuel_card TEXT")

        self.cursor.execute("PRAGMA table_info(issues)")
        issue_columns = {row["name"] for row in self.cursor.fetchall()}
        if "resolution_invoice_path" not in issue_columns:
            self.cursor.execute("ALTER TABLE issues ADD COLUMN resolution_invoice_path TEXT")

    def _ensure_equipment_drivers_shift_half(self):
        """Колонка смены (1/2 половина месяца или NULL — весь месяц) для старых БД."""
        self.cursor.execute("PRAGMA table_info(equipment_drivers)")
        cols = {row["name"] for row in self.cursor.fetchall()}
        if "shift_half" not in cols:
            self.cursor.execute("ALTER TABLE equipment_drivers ADD COLUMN shift_half INTEGER")

    def _ensure_maintenance_columns(self):
        """Добавляет недостающие колонки в maintenance_history для старых БД."""
        self.cursor.execute("PRAGMA table_info(maintenance_history)")
        cols = {row["name"] for row in self.cursor.fetchall()}
        if "counter_type" not in cols:
            self.cursor.execute("ALTER TABLE maintenance_history ADD COLUMN counter_type TEXT")
            self.cursor.execute(
                "UPDATE maintenance_history SET counter_type = 'primary' WHERE counter_type IS NULL OR counter_type = ''"
            )
    
    # ===== Методы для работы с техникой =====
    
    def add_equipment(self, name, sts_pts, reg_number, measurement_type='mileage', 
                     last_maintenance=0, current_value=0, maintenance_interval_summer=10000,
                     maintenance_interval_winter=7500, situation='', service='', insurance_date='',
                     insurance_file_path='', diagnostic_card_date='', diagnostic_card_file_path='',
                     mkad_pass_date='', current_value_updated_at='', sts_certificate='',
                     sts_file_path='', secondary_last_maintenance=0, secondary_current_value=0,
                     secondary_current_value_updated_at='', secondary_maintenance_interval=250, has_kmu=False):
        """Добавление новой техники"""
        try:
            self.cursor.execute('''
                INSERT INTO equipment (name, sts_pts, reg_number, measurement_type, 
                    last_maintenance, current_value, maintenance_interval_summer,
                    maintenance_interval_winter, situation, service, insurance_date,
                    insurance_file_path, diagnostic_card_date, diagnostic_card_file_path, mkad_pass_date,
                    current_value_updated_at, sts_certificate, sts_file_path,
                    secondary_last_maintenance, secondary_current_value, secondary_current_value_updated_at,
                    secondary_maintenance_interval, has_kmu)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, sts_pts, reg_number, measurement_type, last_maintenance, 
                  current_value, maintenance_interval_summer, maintenance_interval_winter,
                  situation, service, insurance_date, insurance_file_path, diagnostic_card_date,
                  diagnostic_card_file_path, mkad_pass_date, current_value_updated_at,
                  sts_certificate, sts_file_path, secondary_last_maintenance, secondary_current_value,
                  secondary_current_value_updated_at, secondary_maintenance_interval, int(bool(has_kmu))))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError(f"Техника с номером {reg_number} уже существует")
    
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
        
        set_clause = ', '.join([f"{k} = ?" for k in fields_to_update.keys()])
        values = list(fields_to_update.values()) + [equipment_id]
        
        self.cursor.execute(f'''
            UPDATE equipment SET {set_clause} WHERE id = ?
        ''', values)
        self.conn.commit()
    
    def get_equipment(self, equipment_id):
        """Получение техники по ID"""
        self.cursor.execute('SELECT * FROM equipment WHERE id = ?', (equipment_id,))
        return self.cursor.fetchone()
    
    def get_all_equipment(self):
        """Получение всей техники"""
        self.cursor.execute('SELECT * FROM equipment ORDER BY sort_order DESC, id')
        return self.cursor.fetchall()
    
    def delete_equipment(self, equipment_id):
        """Удаление техники"""
        self.cursor.execute('DELETE FROM equipment WHERE id = ?', (equipment_id,))
        self.conn.commit()
    
    def move_equipment_up(self, equipment_id):
        """Переместить технику вверх в списке"""
        # Получаем текущий sort_order
        self.cursor.execute('SELECT sort_order FROM equipment WHERE id = ?', (equipment_id,))
        result = self.cursor.fetchone()
        if not result:
            return
        
        current_order = result['sort_order']
        # Увеличиваем sort_order (выше в списке)
        self.cursor.execute('UPDATE equipment SET sort_order = ? WHERE id = ?', 
                          (current_order + 1, equipment_id))
        self.conn.commit()
    
    def move_equipment_down(self, equipment_id):
        """Переместить технику вниз в списке"""
        # Получаем текущий sort_order
        self.cursor.execute('SELECT sort_order FROM equipment WHERE id = ?', (equipment_id,))
        result = self.cursor.fetchone()
        if not result:
            return
        
        current_order = result['sort_order']
        # Уменьшаем sort_order (ниже в списке)
        new_order = max(0, current_order - 1)
        self.cursor.execute('UPDATE equipment SET sort_order = ? WHERE id = ?', 
                          (new_order, equipment_id))
        self.conn.commit()
    
    # ===== Методы для работы с водителями =====
    
    def add_driver(self, name, phone, fuel_card=''):
        """Добавление водителя"""
        self.cursor.execute('''
            INSERT INTO drivers (name, phone, fuel_card)
            VALUES (?, ?, ?)
        ''', (name, phone, fuel_card))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def update_driver(self, driver_id, name, phone, fuel_card=''):
        """Обновление данных водителя"""
        self.cursor.execute('''
            UPDATE drivers SET name = ?, phone = ?, fuel_card = ? WHERE id = ?
        ''', (name, phone, fuel_card, driver_id))
        self.conn.commit()
    
    def get_driver(self, driver_id):
        """Получение водителя по ID"""
        self.cursor.execute('SELECT * FROM drivers WHERE id = ?', (driver_id,))
        return self.cursor.fetchone()
    
    def get_all_drivers(self):
        """Получение всех водителей"""
        self.cursor.execute('SELECT * FROM drivers ORDER BY name')
        return self.cursor.fetchall()
    
    def delete_driver(self, driver_id):
        """Удаление водителя"""
        self.cursor.execute('DELETE FROM drivers WHERE id = ?', (driver_id,))
        self.conn.commit()
    
    # ===== Методы для привязки водителей к технике =====
    
    def assign_driver_to_equipment(self, equipment_id, driver_id, is_primary=False):
        """Привязка водителя к технике"""
        try:
            self.cursor.execute('''
                INSERT INTO equipment_drivers (equipment_id, driver_id, is_primary)
                VALUES (?, ?, ?)
            ''', (equipment_id, driver_id, is_primary))
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Водитель уже привязан к этой технике
            pass
    
    def remove_driver_from_equipment(self, equipment_id, driver_id):
        """Удаление привязки водителя от техники"""
        self.cursor.execute('''
            DELETE FROM equipment_drivers 
            WHERE equipment_id = ? AND driver_id = ?
        ''', (equipment_id, driver_id))
        self.conn.commit()
    
    def get_equipment_drivers(self, equipment_id):
        """Получение водителей техники"""
        self.cursor.execute('''
            SELECT d.* FROM drivers d
            JOIN equipment_drivers ed ON d.id = ed.driver_id
            WHERE ed.equipment_id = ?
            ORDER BY ed.is_primary DESC, d.name
        ''', (equipment_id,))
        return self.cursor.fetchall()
    
    def get_driver_equipment(self, driver_id):
        """Получение техники водителя"""
        self.cursor.execute('''
            SELECT e.* FROM equipment e
            JOIN equipment_drivers ed ON e.id = ed.equipment_id
            WHERE ed.driver_id = ?
            ORDER BY e.name
        ''', (driver_id,))
        return self.cursor.fetchall()

    def get_equipment_names_by_driver_id(self):
        """Словарь driver_id -> [\"Техника (Номер)\", ...] одним запросом."""
        self.cursor.execute('''
            SELECT ed.driver_id, e.name, e.reg_number
            FROM equipment_drivers ed
            JOIN equipment e ON e.id = ed.equipment_id
            ORDER BY e.name
        ''')
        mapping = defaultdict(list)
        for row in self.cursor.fetchall():
            text = f"{row['name']} ({row['reg_number']})"
            mapping[str(row['driver_id'])].append(text)
        return dict(mapping)

    def get_current_shift_half(self):
        """Текущая половина месяца: 1 — с 1 по середину, 2 — до конца месяца (как в облаке)."""
        today = datetime.now().day
        year = datetime.now().year
        month = datetime.now().month
        days_in_month = calendar.monthrange(year, month)[1]
        mid_day = days_in_month // 2
        return 1 if today <= mid_day else 2

    def set_driver_shift(self, equipment_id, driver_id, shift_half=None):
        """Установка смены водителя (1 / 2 / None — весь месяц). Создаёт связь, если её ещё нет."""
        self.cursor.execute(
            'SELECT 1 FROM equipment_drivers WHERE equipment_id = ? AND driver_id = ?',
            (equipment_id, driver_id),
        )
        if self.cursor.fetchone():
            self.cursor.execute(
                'UPDATE equipment_drivers SET shift_half = ? WHERE equipment_id = ? AND driver_id = ?',
                (shift_half, equipment_id, driver_id),
            )
        else:
            self.cursor.execute(
                '''
                INSERT INTO equipment_drivers (equipment_id, driver_id, shift_half, is_primary)
                VALUES (?, ?, ?, 0)
                ''',
                (equipment_id, driver_id, shift_half),
            )
        self.conn.commit()

    def get_all_drivers_for_equipment_with_shifts(self, equipment_id):
        """Все водители техники с полями shift_half и is_active (как в Supabase)."""
        current_shift = self.get_current_shift_half()
        self.cursor.execute(
            '''
            SELECT d.id, d.name, d.phone, d.fuel_card, ed.shift_half, ed.is_primary
            FROM equipment_drivers ed
            JOIN drivers d ON d.id = ed.driver_id
            WHERE ed.equipment_id = ?
            ORDER BY ed.is_primary DESC, d.name
            ''',
            (equipment_id,),
        )
        drivers = []
        for row in self.cursor.fetchall():
            shift_half = row['shift_half']
            drivers.append({
                'id': row['id'],
                'name': row['name'],
                'phone': row['phone'],
                'fuel_card': row['fuel_card'],
                'shift_half': shift_half,
                'is_primary': bool(row['is_primary']) if row['is_primary'] is not None else False,
                'is_active': (shift_half == current_shift or shift_half is None),
            })
        return drivers
    
    # ===== Методы для работы с ТО =====

    def _recalculate_equipment_maintenance(self, equipment_id):
        """Пересчет последнего ТО и текущего значения по истории ТО"""
        self.cursor.execute('''
            SELECT maintenance_value
            FROM maintenance_history
            WHERE equipment_id = ?
              AND (counter_type IS NULL OR counter_type = '' OR counter_type = 'primary')
            ORDER BY maintenance_date DESC, id DESC
            LIMIT 1
        ''', (equipment_id,))
        latest_primary = self.cursor.fetchone()
        self.cursor.execute('''
            SELECT maintenance_value
            FROM maintenance_history
            WHERE equipment_id = ? AND counter_type = 'kmu'
            ORDER BY maintenance_date DESC, id DESC
            LIMIT 1
        ''', (equipment_id,))
        latest_secondary = self.cursor.fetchone()

        latest_primary_value = int(latest_primary['maintenance_value']) if latest_primary else 0
        latest_secondary_value = int(latest_secondary['maintenance_value']) if latest_secondary else 0
        self.cursor.execute('''
            UPDATE equipment
            SET last_maintenance = ?, current_value = ?,
                secondary_last_maintenance = ?, secondary_current_value = ?
            WHERE id = ?
        ''', (latest_primary_value, latest_primary_value, latest_secondary_value, latest_secondary_value, equipment_id))
    
    def add_maintenance(
        self,
        equipment_id,
        maintenance_value,
        maintenance_date=None,
        comment='',
        invoice_path='',
        counter_type='primary',
    ):
        """Добавление записи о прохождении ТО"""
        if maintenance_date is None:
            maintenance_date = datetime.now().isoformat()
        normalized_counter_type = 'kmu' if str(counter_type).strip().lower() == 'kmu' else 'primary'

        self.cursor.execute('''
            INSERT INTO maintenance_history (equipment_id, maintenance_value, counter_type, maintenance_date, comment, invoice_path)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (equipment_id, maintenance_value, normalized_counter_type, maintenance_date, comment, invoice_path))
        
        # Обновляем данные техники по самой свежей записи ТО
        self._recalculate_equipment_maintenance(equipment_id)

        self.conn.commit()
        return self.cursor.lastrowid

    def update_maintenance(
        self,
        maintenance_id,
        maintenance_value,
        maintenance_date,
        comment='',
        invoice_path='',
        counter_type='primary',
    ):
        """Обновление записи о прохождении ТО"""
        self.cursor.execute('SELECT equipment_id FROM maintenance_history WHERE id = ?', (maintenance_id,))
        record = self.cursor.fetchone()
        if not record:
            raise ValueError("Запись ТО не найдена")

        equipment_id = record['equipment_id']

        normalized_counter_type = 'kmu' if str(counter_type).strip().lower() == 'kmu' else 'primary'
        self.cursor.execute('''
            UPDATE maintenance_history
            SET maintenance_value = ?, counter_type = ?, maintenance_date = ?, comment = ?, invoice_path = ?
            WHERE id = ?
        ''', (maintenance_value, normalized_counter_type, maintenance_date, comment, invoice_path, maintenance_id))

        # Пересчитываем данные техники по истории ТО
        self._recalculate_equipment_maintenance(equipment_id)
        
        self.conn.commit()
        return maintenance_id
    
    def get_maintenance_history(self, equipment_id):
        """Получение истории ТО для техники"""
        self.cursor.execute('''
            SELECT * FROM maintenance_history 
            WHERE equipment_id = ? 
            ORDER BY maintenance_date DESC
        ''', (equipment_id,))
        return self.cursor.fetchall()
    
    def get_all_maintenance_history(self):
        """Получение всей истории ТО"""
        self.cursor.execute('''
            SELECT mh.*, e.name as equipment_name, e.reg_number
            FROM maintenance_history mh
            JOIN equipment e ON mh.equipment_id = e.id
            ORDER BY mh.maintenance_date DESC
        ''')
        return self.cursor.fetchall()
    
    # ===== Методы для работы с неисправностями =====
    
    def add_issue(self, equipment_id, description, driver_id=None, resolution_invoice_path=''):
        """Добавление неисправности"""
        self.cursor.execute('''
            INSERT INTO issues (equipment_id, driver_id, description, resolution_invoice_path)
            VALUES (?, ?, ?, ?)
        ''', (equipment_id, driver_id, description, resolution_invoice_path))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_issue(self, issue_id):
        """Получение одной неисправности по ID."""
        self.cursor.execute('SELECT * FROM issues WHERE id = ?', (issue_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def update_issue(self, issue_id, equipment_id, description, driver_id=None, resolution_invoice_path=''):
        """Редактирование неисправности (без смены статуса)."""
        self.cursor.execute('''
            UPDATE issues
            SET equipment_id = ?, driver_id = ?, description = ?, resolution_invoice_path = ?
            WHERE id = ?
        ''', (equipment_id, driver_id, description, resolution_invoice_path, issue_id))
        self.conn.commit()
    
    def update_issue_status(self, issue_id, status, resolution_comment='', resolution_invoice_path=''):
        """Обновление статуса неисправности"""
        resolved_date = datetime.now().isoformat() if status == 'resolved' else None
        self.cursor.execute('''
            UPDATE issues 
            SET status = ?, resolution_comment = ?, resolved_date = ?, resolution_invoice_path = ?
            WHERE id = ?
        ''', (status, resolution_comment, resolved_date, resolution_invoice_path, issue_id))
        self.conn.commit()
    
    def get_equipment_issues(self, equipment_id, status=None):
        """Получение неисправностей техники"""
        if status:
            self.cursor.execute('''
                SELECT i.*, d.name as driver_name, d.phone as driver_phone
                FROM issues i
                LEFT JOIN drivers d ON i.driver_id = d.id
                WHERE i.equipment_id = ? AND i.status = ?
                ORDER BY i.reported_date DESC
            ''', (equipment_id, status))
        else:
            self.cursor.execute('''
                SELECT i.*, d.name as driver_name, d.phone as driver_phone
                FROM issues i
                LEFT JOIN drivers d ON i.driver_id = d.id
                WHERE i.equipment_id = ?
                ORDER BY i.reported_date DESC
            ''', (equipment_id,))
        return self.cursor.fetchall()

    def get_open_issues_grouped_by_equipment_id(self):
        """Все открытые неисправности одним запросом."""
        self.cursor.execute('''
            SELECT equipment_id, description FROM issues
            WHERE status = 'open'
            ORDER BY reported_date DESC
        ''')
        grouped = defaultdict(list)
        for row in self.cursor.fetchall():
            r = dict(row)
            grouped[str(r['equipment_id'])].append(r)
        return dict(grouped)

    def get_active_driver_name_by_equipment_id(self):
        """Активный водитель по текущей смене — один запрос (логика как в облаке)."""
        current_shift = self.get_current_shift_half()
        self.cursor.execute('''
            SELECT ed.equipment_id, ed.shift_half, d.name
            FROM equipment_drivers ed
            JOIN drivers d ON ed.driver_id = d.id
        ''')
        by_eq = defaultdict(list)
        for row in self.cursor.fetchall():
            eid = str(row['equipment_id'])
            shift_half = row['shift_half']
            by_eq[eid].append({
                'name': row['name'] or '-',
                'shift_half': shift_half,
                'is_active': (shift_half == current_shift or shift_half is None),
            })
        out = {}
        for eid, drivers in by_eq.items():
            active = next((d for d in drivers if d['is_active']), None)
            out[eid] = active['name'] if active else (drivers[0]['name'] if drivers else '-')
        return out
    
    def get_all_issues(self, status=None):
        """Получение всех неисправностей"""
        if status:
            self.cursor.execute('''
                SELECT i.*, e.name as equipment_name, e.reg_number,
                       d.name as driver_name, d.phone as driver_phone
                FROM issues i
                JOIN equipment e ON i.equipment_id = e.id
                LEFT JOIN drivers d ON i.driver_id = d.id
                WHERE i.status = ?
                ORDER BY i.reported_date DESC
            ''', (status,))
        else:
            self.cursor.execute('''
                SELECT i.*, e.name as equipment_name, e.reg_number,
                       d.name as driver_name, d.phone as driver_phone
                FROM issues i
                JOIN equipment e ON i.equipment_id = e.id
                LEFT JOIN drivers d ON i.driver_id = d.id
                ORDER BY i.reported_date DESC
            ''')
        return self.cursor.fetchall()
    
    def delete_issue(self, issue_id):
        """Удаление неисправности"""
        self.cursor.execute('DELETE FROM issues WHERE id = ?', (issue_id,))
        self.conn.commit()
    
    # ===== Методы для настроек =====
    
    def set_setting(self, key, value):
        """Установка настройки"""
        self.cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value)
            VALUES (?, ?)
        ''', (key, value))
        self.conn.commit()
    
    def get_setting(self, key, default=None):
        """Получение настройки"""
        self.cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        result = self.cursor.fetchone()
        return result['value'] if result else default

    def delete_storage_file(self, supabase_uri: str) -> None:
        """Локальный режим: файлы не в Supabase — заглушка для единообразия вызовов."""
        return

    def cleanup_orphan_invoice_storage(self):
        """Локальный режим: не применимо."""
        return {'deleted': 0, 'orphans_found': 0, 'referenced_in_db': 0, 'errors': [], 'skipped': True}
    
    def close(self):
        """Закрытие соединения с базой данных"""
        if self.conn:
            self.conn.close()
