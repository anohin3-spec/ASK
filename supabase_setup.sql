-- ===============================================
-- SUPABASE SETUP - Создание облачной базы данных
-- ===============================================
-- Скопируйте весь этот файл и выполните в Supabase SQL Editor

-- Включаем расширения
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================
-- ТАБЛИЦА: Организации (компании)
-- =============================================
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    license_key TEXT,
    license_valid_until DATE,
    max_vehicles INTEGER DEFAULT 50,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- ТАБЛИЦА: Пользователи
-- =============================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    role TEXT NOT NULL DEFAULT 'user', -- 'admin', 'manager', 'user'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- ТАБЛИЦА: Техника
-- =============================================
CREATE TABLE IF NOT EXISTS equipment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sts_pts TEXT,
    reg_number TEXT NOT NULL,
    measurement_type TEXT NOT NULL DEFAULT 'mileage',
    last_maintenance INTEGER DEFAULT 0,
    current_value INTEGER DEFAULT 0,
    current_value_updated_at TEXT,
    secondary_last_maintenance INTEGER DEFAULT 0,
    secondary_current_value INTEGER DEFAULT 0,
    secondary_current_value_updated_at TEXT,
    secondary_maintenance_interval INTEGER DEFAULT 250,
    has_kmu BOOLEAN DEFAULT FALSE,
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(company_id, reg_number)
);

-- =============================================
-- ТАБЛИЦА: Водители
-- =============================================
CREATE TABLE IF NOT EXISTS drivers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    fuel_card TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- ТАБЛИЦА: Привязка водителей к технике
-- =============================================
CREATE TABLE IF NOT EXISTS equipment_drivers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    equipment_id UUID REFERENCES equipment(id) ON DELETE CASCADE,
    driver_id UUID REFERENCES drivers(id) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(equipment_id, driver_id)
);

-- =============================================
-- ТАБЛИЦА: История ТО
-- =============================================
CREATE TABLE IF NOT EXISTS maintenance_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    equipment_id UUID REFERENCES equipment(id) ON DELETE CASCADE,
    maintenance_value INTEGER NOT NULL,
    counter_type TEXT NOT NULL DEFAULT 'primary',
    maintenance_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    comment TEXT,
    invoice_path TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- ТАБЛИЦА: Неисправности
-- =============================================
CREATE TABLE IF NOT EXISTS issues (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    equipment_id UUID REFERENCES equipment(id) ON DELETE CASCADE,
    driver_id UUID REFERENCES drivers(id) ON DELETE SET NULL,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    reported_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_date TIMESTAMP WITH TIME ZONE,
    resolution_comment TEXT,
    resolution_invoice_path TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- ТАБЛИЦА: Настройки
-- =============================================
CREATE TABLE IF NOT EXISTS settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT,
    UNIQUE(company_id, key)
);

-- =============================================
-- ИНДЕКСЫ для производительности
-- =============================================
CREATE INDEX IF NOT EXISTS idx_equipment_company ON equipment(company_id);
CREATE INDEX IF NOT EXISTS idx_drivers_company ON drivers(company_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_equipment ON maintenance_history(equipment_id);
CREATE INDEX IF NOT EXISTS idx_issues_equipment ON issues(equipment_id);
CREATE INDEX IF NOT EXISTS idx_users_company ON users(company_id);

-- =============================================
-- ROW LEVEL SECURITY (RLS)
-- Пользователи видят только данные своей компании
-- =============================================
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE equipment ENABLE ROW LEVEL SECURITY;
ALTER TABLE drivers ENABLE ROW LEVEL SECURITY;
ALTER TABLE equipment_drivers ENABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE issues ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;

-- Политики доступа (пока разрешаем все для anon - настроим позже)
CREATE POLICY "Enable all for anon" ON companies FOR ALL USING (true);
CREATE POLICY "Enable all for anon" ON users FOR ALL USING (true);
CREATE POLICY "Enable all for anon" ON equipment FOR ALL USING (true);
CREATE POLICY "Enable all for anon" ON drivers FOR ALL USING (true);
CREATE POLICY "Enable all for anon" ON equipment_drivers FOR ALL USING (true);
CREATE POLICY "Enable all for anon" ON maintenance_history FOR ALL USING (true);
CREATE POLICY "Enable all for anon" ON issues FOR ALL USING (true);
CREATE POLICY "Enable all for anon" ON settings FOR ALL USING (true);

-- =============================================
-- ТЕСТОВЫЕ ДАННЫЕ (первая компания и админ)
-- =============================================
-- Создаем тестовую компанию
INSERT INTO companies (id, name, license_key, license_valid_until, max_vehicles)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Тестовая организация',
    'TEST-0000-0000',
    '2027-12-31',
    100
) ON CONFLICT DO NOTHING;

-- Создаем админа (пароль: admin123)
-- Хеш для 'admin123': будет создан в программе
INSERT INTO users (company_id, username, password_hash, full_name, role)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'admin',
    'admin123', -- временно, программа зашифрует при первом входе
    'Администратор',
    'admin'
) ON CONFLICT DO NOTHING;

-- =============================================
-- ГОТОВО! Таблицы созданы!
-- =============================================
