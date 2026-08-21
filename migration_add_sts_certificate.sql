-- Выполните в Supabase SQL Editor (один раз), если таблица equipment уже создана без полей СТС.

ALTER TABLE equipment ADD COLUMN IF NOT EXISTS sts_certificate TEXT;
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS sts_file_path TEXT;
