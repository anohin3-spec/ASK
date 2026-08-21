-- Добавляет поддержку второго счетчика (КМУ) и типа счетчика в истории ТО.
-- Выполнить один раз в Supabase SQL Editor.

ALTER TABLE equipment
ADD COLUMN IF NOT EXISTS secondary_last_maintenance INTEGER DEFAULT 0;

ALTER TABLE equipment
ADD COLUMN IF NOT EXISTS secondary_current_value INTEGER DEFAULT 0;

ALTER TABLE equipment
ADD COLUMN IF NOT EXISTS secondary_current_value_updated_at TEXT;

ALTER TABLE equipment
ADD COLUMN IF NOT EXISTS secondary_maintenance_interval INTEGER DEFAULT 250;

ALTER TABLE equipment
ADD COLUMN IF NOT EXISTS has_kmu BOOLEAN DEFAULT FALSE;

ALTER TABLE maintenance_history
ADD COLUMN IF NOT EXISTS counter_type TEXT DEFAULT 'primary';

UPDATE maintenance_history
SET counter_type = 'primary'
WHERE counter_type IS NULL OR counter_type = '';

ALTER TABLE maintenance_history
ALTER COLUMN counter_type SET DEFAULT 'primary';
