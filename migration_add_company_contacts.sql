-- ===============================================
-- МИГРАЦИЯ: Добавление полей phone и email в таблицу companies
-- ===============================================
-- Выполните этот запрос в Supabase SQL Editor
-- если у вас уже создана база данных

-- Добавляем поля phone и email если их еще нет
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='companies' AND column_name='phone') THEN
        ALTER TABLE companies ADD COLUMN phone TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='companies' AND column_name='email') THEN
        ALTER TABLE companies ADD COLUMN email TEXT;
    END IF;
END $$;

-- Готово!
