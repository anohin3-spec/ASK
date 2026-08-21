-- Добавляет дату последнего обновления текущего значения пробега/моточасов
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS current_value_updated_at TEXT;

