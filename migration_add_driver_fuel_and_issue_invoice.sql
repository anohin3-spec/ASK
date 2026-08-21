-- Добавляет топливную карту водителя и счет по устранению неисправности
ALTER TABLE drivers ADD COLUMN IF NOT EXISTS fuel_card TEXT;
ALTER TABLE issues ADD COLUMN IF NOT EXISTS resolution_invoice_path TEXT;

