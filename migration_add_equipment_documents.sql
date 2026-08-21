-- Добавление полей файлов страховки и диагностической карты для облачной БД
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS insurance_file_path TEXT;
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS diagnostic_card_date TEXT;
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS diagnostic_card_file_path TEXT;

