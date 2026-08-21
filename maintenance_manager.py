"""
Модуль для управления техническим обслуживанием
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import os
from keyboard_shortcuts import bind_entry_shortcuts, bind_all_entries


class MaintenanceManager:
    def __init__(self, db):
        self.db = db


class MaintenanceDialog:
    """Диалог регистрации прохождения ТО"""
    
    def __init__(self, parent, db, equipment_id=None, maintenance_id=None, initial_data=None):
        self.db = db
        self.equipment_id = equipment_id
        self.maintenance_id = maintenance_id
        self.initial_data = initial_data or {}
        self.is_edit_mode = maintenance_id is not None
        self.result = None
        self.invoice_source_path = None
        self.invoice_action = 'clear'
        self.current_invoice_path = self.initial_data.get('invoice_path', '') if self.is_edit_mode else ''

        if self.is_edit_mode and self.current_invoice_path:
            self.invoice_action = 'keep'
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Редактирование ТО" if self.is_edit_mode else "Регистрация ТО")
        self.dialog.geometry("550x450")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Центрирование окна
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (550 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (450 // 2)
        self.dialog.geometry(f"+{x}+{y}")
        
        self.create_widgets()
        
        # Применение горячих клавиш ко всем полям ввода
        bind_all_entries(self.dialog)
    
    def create_widgets(self):
        """Создание виджетов диалога"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Выбор техники
        ttk.Label(main_frame, text="Техника:", font=('Arial', 10)).grid(row=0, column=0, sticky='w', pady=10)
        
        self.equipment_combo = ttk.Combobox(main_frame, state='readonly', width=40, font=('Arial', 10))
        self.equipment_combo.grid(row=0, column=1, pady=10, sticky='ew')
        
        # Загрузка списка техники
        equipment_list = self.db.get_all_equipment()
        self.equipment_data = {f"{eq['name']} ({eq['reg_number']})": eq for eq in equipment_list}
        self.equipment_combo['values'] = list(self.equipment_data.keys())
        
        if self.equipment_id:
            # Если передан ID техники, выбираем её
            for key, eq in self.equipment_data.items():
                if str(eq['id']) == str(self.equipment_id):
                    self.equipment_combo.set(key)
                    break

        if self.is_edit_mode:
            self.equipment_combo.configure(state='disabled')
        
        # Пробег/моточасы при ТО
        ttk.Label(main_frame, text="Счетчик ТО:", font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=10)
        self.counter_type_combo = ttk.Combobox(
            main_frame,
            state='readonly',
            width=40,
            values=['Шасси (км)', 'КМУ (м/ч)'],
            font=('Arial', 10),
        )
        self.counter_type_combo.grid(row=1, column=1, pady=10, sticky='ew')
        self.counter_type_combo.set('Шасси (км)')
        self.counter_type_combo.bind('<<ComboboxSelected>>', self.on_counter_type_selected)

        ttk.Label(main_frame, text="Пробег/моточасы при ТО:", font=('Arial', 10)).grid(row=2, column=0, sticky='w', pady=10)
        self.mileage_entry = ttk.Entry(main_frame, width=40, font=('Arial', 10))
        self.mileage_entry.grid(row=2, column=1, pady=10, sticky='ew')
        bind_entry_shortcuts(self.mileage_entry)
        
        # Автозаполнение текущим значением
        self.equipment_combo.bind('<<ComboboxSelected>>', self.on_equipment_selected)
        
        # Дата ТО
        ttk.Label(main_frame, text="Дата ТО:", font=('Arial', 10)).grid(row=3, column=0, sticky='w', pady=10)
        self.date_entry = ttk.Entry(main_frame, width=40, font=('Arial', 10))
        self.date_entry.grid(row=3, column=1, pady=10, sticky='ew')
        bind_entry_shortcuts(self.date_entry)

        if self.is_edit_mode:
            self.mileage_entry.insert(0, str(self.initial_data.get('maintenance_value', '')))
            self.date_entry.insert(0, str(self.initial_data.get('maintenance_date_display', '')))
        else:
            self.date_entry.insert(0, datetime.now().strftime('%d.%m.%Y %H:%M'))
        
        # Комментарий
        ttk.Label(main_frame, text="Комментарий:", font=('Arial', 10)).grid(row=4, column=0, sticky='nw', pady=10)
        self.comment_text = tk.Text(main_frame, width=40, height=6, font=('Arial', 10))
        self.comment_text.grid(row=4, column=1, pady=10, sticky='ew')
        bind_entry_shortcuts(self.comment_text)

        if self.is_edit_mode:
            self.comment_text.insert('1.0', str(self.initial_data.get('comment', '')))
        
        # Счет
        ttk.Label(main_frame, text="Счет:", font=('Arial', 10)).grid(row=5, column=0, sticky='w', pady=10)
        
        invoice_frame = ttk.Frame(main_frame)
        invoice_frame.grid(row=5, column=1, pady=10, sticky='ew')
        
        self.invoice_label = ttk.Label(invoice_frame, text="Файл не выбран", foreground='gray')
        self.invoice_label.pack(side='left')

        if self.current_invoice_path:
            self.invoice_label.config(text=os.path.basename(self.current_invoice_path), foreground='black')

        if self.is_edit_mode:
            initial_counter = str(self.initial_data.get('counter_type', 'primary')).strip().lower()
            self.counter_type_combo.set('КМУ (м/ч)' if initial_counter == 'kmu' else 'Шасси (км)')
            selected_eq = self.equipment_data.get(self.equipment_combo.get())
            if selected_eq:
                self._apply_counter_options(selected_eq, keep_selected=True)
        
        ttk.Button(invoice_frame, text="Выбрать файл", command=self.select_invoice).pack(side='right', padx=5)
        ttk.Button(invoice_frame, text="Очистить", command=self.clear_invoice).pack(side='right')
        
        # Настройка растягивания столбцов
        main_frame.columnconfigure(1, weight=1)
        
        # Кнопки
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Сохранить", command=self.save, width=15).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Отмена", command=self.dialog.destroy, width=15).pack(side='left', padx=5)

        # Инициализируем выбор только после создания всех полей (чтобы форма не обрывалась).
        if self.equipment_combo.get():
            try:
                selected_eq = self.equipment_data.get(self.equipment_combo.get())
                if selected_eq:
                    self._apply_counter_options(selected_eq, keep_selected=True)
                if not self.is_edit_mode:
                    self.on_equipment_selected(None)
            except Exception:
                pass
    
    def on_equipment_selected(self, event):
        """Обработчик выбора техники"""
        selected = self.equipment_combo.get()
        if selected in self.equipment_data:
            equipment = self.equipment_data[selected]
            self._apply_counter_options(equipment)
            self.mileage_entry.delete(0, tk.END)
            prefer_kmu = bool(equipment.get('has_kmu')) and int(equipment.get('secondary_current_value') or 0) > 0
            if prefer_kmu and 'КМУ (м/ч)' in self.counter_type_combo.cget('values'):
                self.counter_type_combo.set('КМУ (м/ч)')
                self.mileage_entry.insert(0, str(equipment.get('secondary_current_value', 0)))
            else:
                self.counter_type_combo.set('Шасси (км)')
                self.mileage_entry.insert(0, str(equipment.get('current_value', 0)))

    def _apply_counter_options(self, equipment, keep_selected=False):
        """Показывает КМУ только для техники, где включен узел."""
        if isinstance(equipment, dict):
            has_kmu = bool(equipment.get('has_kmu'))
        else:
            try:
                has_kmu = bool(equipment['has_kmu'])
            except Exception:
                has_kmu = False
        values = ['Шасси (км)', 'КМУ (м/ч)'] if has_kmu else ['Шасси (км)']
        previous = self.counter_type_combo.get()
        self.counter_type_combo.configure(values=values)
        if keep_selected and previous in values:
            self.counter_type_combo.set(previous)
        elif self.counter_type_combo.get() not in values:
            self.counter_type_combo.set('Шасси (км)')

    def on_counter_type_selected(self, event=None):
        """Подставляет актуальное значение выбранного счетчика."""
        selected = self.equipment_combo.get()
        if selected not in self.equipment_data:
            return
        equipment = self.equipment_data[selected]
        self.mileage_entry.delete(0, tk.END)
        if self.counter_type_combo.get() == 'КМУ (м/ч)':
            self.mileage_entry.insert(0, str(equipment.get('secondary_current_value', 0)))
        else:
            self.mileage_entry.insert(0, str(equipment.get('current_value', 0)))
    
    def select_invoice(self):
        """Выбор файла счета"""
        file_path = filedialog.askopenfilename(
            parent=self.dialog,
            title="Выберите файл счета",
            filetypes=[
                ('Все файлы', '*.*'),
                ('PDF', '*.pdf'),
                ('Изображения', '*.jpg'),
                ('Изображения PNG', '*.png'),
                ('Документы Word', '*.doc'),
                ('Документы Word', '*.docx'),
            ],
        )
        
        if file_path:
            self.invoice_source_path = file_path
            self.invoice_action = 'replace'
            filename = os.path.basename(file_path)
            self.invoice_label.config(text=filename, foreground='black')
    
    def clear_invoice(self):
        """Очистка выбранного счета"""
        self.invoice_source_path = None
        self.invoice_action = 'clear'
        self.invoice_label.config(text="Файл не выбран", foreground='gray')
    
    def save(self):
        """Сохранение данных ТО"""
        # Валидация
        selected = self.equipment_combo.get()
        if not selected:
            messagebox.showerror("Ошибка", "Выберите технику")
            return
        
        equipment = self.equipment_data[selected]
        
        try:
            mileage = int(self.mileage_entry.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Пробег/моточасы должны быть числом")
            return

        maintenance_date_raw = self.date_entry.get().strip()
        try:
            maintenance_date = datetime.strptime(maintenance_date_raw, '%d.%m.%Y %H:%M').isoformat()
        except ValueError:
            messagebox.showerror("Ошибка", "Неверный формат даты ТО. Используйте: ДД.ММ.ГГГГ ЧЧ:ММ")
            return
        
        comment = self.comment_text.get('1.0', tk.END).strip()
        counter_type = 'kmu' if self.counter_type_combo.get() == 'КМУ (м/ч)' else 'primary'
        if counter_type == 'kmu' and not bool(equipment.get('has_kmu')):
            messagebox.showerror("Ошибка", "Для выбранной техники не включен узел КМУ")
            return
        
        # Сохранение/обновление файла счета
        if self.invoice_action == 'keep':
            saved_invoice_path = self.current_invoice_path
        elif self.invoice_action == 'clear':
            if hasattr(self.db, 'delete_storage_file'):
                self.db.delete_storage_file(self.current_invoice_path)
            saved_invoice_path = ''
        else:
            saved_invoice_path = ''
            if self.invoice_source_path:
                try:
                    old_invoice = self.current_invoice_path
                    if hasattr(self.db, 'upload_invoice_file'):
                        # Cloud-режим: файл хранится в Supabase Storage
                        saved_invoice_path = self.db.upload_invoice_file(
                            self.invoice_source_path,
                            equipment['reg_number']
                        )
                    else:
                        # Local-режим: сохраняем в локальную папку invoices
                        from pdf_compress import read_file_bytes_for_upload

                        invoices_dir = os.path.join(os.path.dirname(__file__), 'invoices')
                        os.makedirs(invoices_dir, exist_ok=True)

                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        filename = f"{equipment['reg_number']}_{timestamp}{os.path.splitext(self.invoice_source_path)[1]}"
                        saved_invoice_path = os.path.join(invoices_dir, filename)
                        data = read_file_bytes_for_upload(self.invoice_source_path)
                        with open(saved_invoice_path, 'wb') as f:
                            f.write(data)
                    if (
                        old_invoice
                        and saved_invoice_path
                        and old_invoice != saved_invoice_path
                        and hasattr(self.db, 'delete_storage_file')
                    ):
                        self.db.delete_storage_file(old_invoice)
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Ошибка копирования файла:\n{str(e)}")
                    return
        
        try:
            if self.is_edit_mode:
                self.db.update_maintenance(
                    maintenance_id=self.maintenance_id,
                    maintenance_value=mileage,
                    maintenance_date=maintenance_date,
                    comment=comment,
                    invoice_path=saved_invoice_path,
                    counter_type=counter_type,
                )
                messagebox.showinfo("Успех", "ТО обновлено")
            else:
                # Добавление записи о ТО
                self.db.add_maintenance(
                    equipment_id=equipment['id'],
                    maintenance_value=mileage,
                    maintenance_date=maintenance_date,
                    comment=comment,
                    invoice_path=saved_invoice_path,
                    counter_type=counter_type,
                )

                messagebox.showinfo("Успех", "ТО зарегистрировано")

            self.result = True
            self.dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при сохранении:\n{str(e)}")
