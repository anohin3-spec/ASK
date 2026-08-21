-- Миграция: добавление колонки shift_half в таблицу equipment_drivers для системы смен
-- Дата: 2026-02-24

-- Добавление колонки shift_half в существующую таблицу equipment_drivers
ALTER TABLE equipment_drivers 
ADD COLUMN IF NOT EXISTS shift_half INTEGER CHECK (shift_half IN (1, 2) OR shift_half IS NULL);

-- Индекс для поиска водителей по смене
CREATE INDEX IF NOT EXISTS idx_equipment_drivers_shift ON equipment_drivers(equipment_id, shift_half);

-- Комментарий к новой колонке
COMMENT ON COLUMN equipment_drivers.shift_half IS 'Половина месяца: 1 - первая половина (1-14/15 число), 2 - вторая половина (15/16-конец месяца), NULL - весь месяц';
