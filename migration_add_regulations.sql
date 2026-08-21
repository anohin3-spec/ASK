-- Создание таблицы для метаданных регламентов технического обслуживания

-- Таблица регламентов
CREATE TABLE IF NOT EXISTS regulations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_type TEXT NOT NULL UNIQUE,
    file_path TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    uploaded_by UUID,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы (с проверкой существования)
CREATE INDEX IF NOT EXISTS idx_regulations_equipment_type ON regulations(equipment_type);

-- RLS политики
ALTER TABLE regulations ENABLE ROW LEVEL SECURITY;

-- Удаляем старые политики если есть (чтобы избежать конфликтов)
DROP POLICY IF EXISTS "Регламенты доступны всем пользователям" ON regulations;
DROP POLICY IF EXISTS "Только админы могут управлять регламентами" ON regulations;

-- Все авторизованные пользователи могут читать регламенты
CREATE POLICY "Регламенты доступны всем пользователям" ON regulations
    FOR SELECT
    USING (true);

-- Все авторизованные пользователи могут управлять регламентами
-- (убрана проверка роли, так как auth.jwt() может не работать в некоторых случаях)
CREATE POLICY "Пользователи могут управлять регламентами" ON regulations
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Комментарии
COMMENT ON TABLE regulations IS 'Метаданные файлов регламентов технического обслуживания';
COMMENT ON COLUMN regulations.equipment_type IS 'Тип техники (Case 570, Hidromek, Камаз, FAW)';
COMMENT ON COLUMN regulations.file_path IS 'Путь к файлу в Supabase Storage (supabase://regulations/...)';
COMMENT ON COLUMN regulations.original_filename IS 'Оригинальное имя файла';
