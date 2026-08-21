-- Политики для хранения счетов в Supabase Storage
-- Bucket: invoices (private)
--
-- ВАЖНО ДЛЯ ЭТОГО ПРОЕКТА:
-- Приложение использует собственную авторизацию (таблица users),
-- а в Supabase подключается через anon key (роль anon), без Supabase Auth JWT.
-- Поэтому политики должны разрешать роль anon, иначе будет 403 RLS.
--
-- Пример пути объекта: <company_id>/ABC123_20260223_120000.pdf

-- Включаем RLS для storage.objects (обычно уже включено по умолчанию)
alter table storage.objects enable row level security;

-- Удаляем старые политики с такими же именами (если перезапускаете скрипт)
drop policy if exists "invoices_select_own_company" on storage.objects;
drop policy if exists "invoices_insert_own_company" on storage.objects;
drop policy if exists "invoices_update_own_company" on storage.objects;
drop policy if exists "invoices_delete_own_company" on storage.objects;

-- READ: разрешаем чтение объектов bucket invoices
create policy "invoices_select_own_company"
on storage.objects
for select
to anon, authenticated
using (
  bucket_id = 'invoices'
);

-- INSERT: разрешаем загрузку объектов в bucket invoices
create policy "invoices_insert_own_company"
on storage.objects
for insert
to anon, authenticated
with check (
  bucket_id = 'invoices'
);

-- UPDATE: разрешаем обновление объектов bucket invoices
create policy "invoices_update_own_company"
on storage.objects
for update
to anon, authenticated
using (
  bucket_id = 'invoices'
)
with check (
  bucket_id = 'invoices'
);

-- DELETE: разрешаем удаление объектов bucket invoices
create policy "invoices_delete_own_company"
on storage.objects
for delete
to anon, authenticated
using (
  bucket_id = 'invoices'
);

-- Быстрая проверка:
-- select * from storage.objects where bucket_id = 'invoices' order by created_at desc;
