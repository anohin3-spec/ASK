"""
Модуль для управления техникой
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import os
from keyboard_shortcuts import bind_entry_shortcuts, bind_all_entries, bind_date_dd_mm_yyyy


class EquipmentManager:
    def __init__(self, db):
        self.db = db


class EquipmentDialog:
    """Диалог добавления/редактирования техники"""
    
    def __init__(self, parent, db, equipment_id=None, title="Техника", equipment_data=None, equipment_reg_number=None):
        self.db = db
        self.equipment_id = equipment_id
        self.prefilled_equipment = equipment_data
        self.equipment_reg_number = str(equipment_reg_number or '').strip()
        self.result = None
        self.insurance_source_path = None
        self.insurance_action = 'clear'
        self.current_insurance_file_path = ''
        self.diagnostic_source_path = None
        self.diagnostic_action = 'clear'
        self.current_diagnostic_file_path = ''
        self.sts_source_path = None
        self.sts_action = 'clear'
        self.current_sts_file_path = ''
        self.original_current_value = None
        self.current_value_updated_at = ''
        self.original_secondary_current_value = None
        self.secondary_current_value_updated_at = ''
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        screen_w = self.dialog.winfo_screenwidth()
        screen_h = self.dialog.winfo_screenheight()
        dialog_w = min(760, max(640, screen_w - 120))
        dialog_h = min(900, max(540, screen_h - 120))
        self.dialog.geometry(f"{dialog_w}x{dialog_h}")
        self.dialog.resizable(True, True)
        self.dialog.minsize(640, 540)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Центрирование окна
        self.dialog.update_idletasks()
        x = (screen_w // 2) - (dialog_w // 2)
        y = (screen_h // 2) - (dialog_h // 2)
        self.dialog.geometry(f"+{x}+{y}")
        
        self.create_widgets()
        
        # Если редактируем, загружаем данные
        if equipment_id is not None or equipment_data is not None:
            self.load_equipment_data()
        
        # Применение горячих клавиш ко всем полям ввода
        bind_all_entries(self.dialog)
    
    def create_widgets(self):
        """Создание виджетов диалога"""
        container = ttk.Frame(self.dialog)
        container.pack(fill='both', expand=True)

        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        main_frame = ttk.Frame(canvas, padding=20)
        canvas_window = canvas.create_window((0, 0), window=main_frame, anchor='nw')

        def _sync_scrollregion(_event=None):
            canvas.configure(scrollregion=canvas.bbox('all'))

        def _sync_width(event):
            canvas.itemconfigure(canvas_window, width=event.width)

        def _on_mousewheel(event):
            if event.delta:
                canvas.yview_scroll(int(-event.delta / 120), 'units')
            elif getattr(event, 'num', None) == 4:
                canvas.yview_scroll(-1, 'units')
            elif getattr(event, 'num', None) == 5:
                canvas.yview_scroll(1, 'units')

        main_frame.bind('<Configure>', _sync_scrollregion)
        canvas.bind('<Configure>', _sync_width)
        self.dialog.bind('<MouseWheel>', _on_mousewheel)
        self.dialog.bind('<Button-4>', _on_mousewheel)
        self.dialog.bind('<Button-5>', _on_mousewheel)
        
        # Название техники
        ttk.Label(main_frame, text="Название техники:").grid(row=0, column=0, sticky='w', pady=5)
        self.name_entry = ttk.Entry(main_frame, width=40)
        self.name_entry.grid(row=0, column=1, pady=5, sticky='ew')
        bind_entry_shortcuts(self.name_entry)
        
        ttk.Label(main_frame, text="VIN:").grid(row=1, column=0, sticky='w', pady=5)
        self.sts_entry = ttk.Entry(main_frame, width=40)
        self.sts_entry.grid(row=1, column=1, pady=5, sticky='ew')
        bind_entry_shortcuts(self.sts_entry)

        sts_box = ttk.LabelFrame(main_frame, text="СТС (свидетельство о регистрации)", padding=10)
        sts_box.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(0, 10))
        ttk.Label(sts_box, text="Серия, номер или реквизиты с документа:").pack(anchor='w')
        self.sts_certificate_entry = ttk.Entry(sts_box, width=52)
        self.sts_certificate_entry.pack(fill='x', pady=(2, 8))
        bind_entry_shortcuts(self.sts_certificate_entry)
        ttk.Label(sts_box, text="Скан или фото СТС:", font=('Arial', 9)).pack(anchor='w', pady=(4, 0))
        sts_btns = ttk.Frame(sts_box)
        sts_btns.pack(fill='x', pady=(2, 0))
        self.sts_file_label = ttk.Label(sts_btns, text="Файл не выбран", foreground='gray')
        self.sts_file_label.pack(side='left', fill='x', expand=True)
        ttk.Button(sts_btns, text="Выбрать", command=self.select_sts_file).pack(side='right', padx=(8, 4))
        ttk.Button(sts_btns, text="Просмотреть", command=self.preview_sts_file).pack(side='right', padx=4)
        ttk.Button(sts_btns, text="Очистить", command=self.clear_sts_file).pack(side='right')
        
        # Регистрационный номер
        ttk.Label(main_frame, text="Регистрационный номер:").grid(row=3, column=0, sticky='w', pady=5)
        self.reg_number_entry = ttk.Entry(main_frame, width=40)
        self.reg_number_entry.grid(row=3, column=1, pady=5, sticky='ew')
        bind_entry_shortcuts(self.reg_number_entry)
        
        # Тип учета
        ttk.Label(main_frame, text="Тип учета:").grid(row=4, column=0, sticky='w', pady=5)
        self.measurement_type = ttk.Combobox(main_frame, values=['Пробег (км)', 'Моточасы'], 
                                            state='readonly', width=37)
        self.measurement_type.set('Пробег (км)')
        self.measurement_type.grid(row=4, column=1, pady=5, sticky='ew')
        self.measurement_type.bind('<<ComboboxSelected>>', self.on_measurement_type_changed)
        
        # Последнее ТО
        self.last_maintenance_label = ttk.Label(main_frame, text="Последнее ТО на (км, прошлое значение):")
        self.last_maintenance_label.grid(row=5, column=0, sticky='w', pady=5)
        self.last_maintenance_entry = ttk.Entry(main_frame, width=40)
        self.last_maintenance_entry.insert(0, "0")
        self.last_maintenance_entry.grid(row=5, column=1, pady=5, sticky='ew')
        bind_entry_shortcuts(self.last_maintenance_entry)
        
        # Текущее значение
        self.current_value_label = ttk.Label(main_frame, text="Текущий пробег (км) — ВВОДИТЬ СЮДА:")
        self.current_value_label.grid(row=6, column=0, sticky='w', pady=5)
        self.current_value_entry = ttk.Entry(main_frame, width=40)
        self.current_value_entry.insert(0, "0")
        self.current_value_entry.grid(row=6, column=1, pady=5, sticky='ew')
        bind_entry_shortcuts(self.current_value_entry)
        
        # Интервал ТО летом
        self.interval_summer_label = ttk.Label(main_frame, text="Интервал ТО летом (км):")
        self.interval_summer_label.grid(row=7, column=0, sticky='w', pady=5)
        self.interval_summer_entry = ttk.Entry(main_frame, width=40)
        self.interval_summer_entry.insert(0, "10000")
        self.interval_summer_entry.grid(row=7, column=1, pady=5, sticky='ew')
        bind_entry_shortcuts(self.interval_summer_entry)
        
        # Интервал ТО зимой
        self.interval_winter_label = ttk.Label(main_frame, text="Интервал ТО зимой (км):")
        self.interval_winter_label.grid(row=8, column=0, sticky='w', pady=5)
        self.interval_winter_entry = ttk.Entry(main_frame, width=40)
        self.interval_winter_entry.insert(0, "7500")
        self.interval_winter_entry.grid(row=8, column=1, pady=5, sticky='ew')
        bind_entry_shortcuts(self.interval_winter_entry)

        self.has_kmu_var = tk.BooleanVar(value=False)
        self.has_kmu_check = ttk.Checkbutton(
            main_frame,
            text="Есть крановая установка (КМУ)",
            variable=self.has_kmu_var,
            command=self.on_has_kmu_toggled,
        )
        self.has_kmu_check.grid(row=9, column=0, columnspan=2, sticky='w', pady=(4, 4))

        self.kmu_box = ttk.LabelFrame(main_frame, text="Крановая установка (КМУ)", padding=10)
        self.kmu_box.grid(row=10, column=0, columnspan=2, sticky='ew', pady=(4, 10))
        ttk.Label(self.kmu_box, text="Последнее ТО КМУ (м/ч, прошлое, НЕ текущее):").grid(row=0, column=0, sticky='w', pady=4)
        self.secondary_last_maintenance_entry = ttk.Entry(self.kmu_box, width=40)
        self.secondary_last_maintenance_entry.insert(0, "0")
        self.secondary_last_maintenance_entry.grid(row=0, column=1, sticky='ew', pady=4)
        bind_entry_shortcuts(self.secondary_last_maintenance_entry)
        ttk.Label(self.kmu_box, text="Текущие моточасы КМУ — ВВОДИТЬ СЮДА:").grid(row=1, column=0, sticky='w', pady=4)
        self.secondary_current_value_entry = ttk.Entry(self.kmu_box, width=40)
        self.secondary_current_value_entry.insert(0, "0")
        self.secondary_current_value_entry.grid(row=1, column=1, sticky='ew', pady=4)
        bind_entry_shortcuts(self.secondary_current_value_entry)
        ttk.Label(self.kmu_box, text="Интервал ТО КМУ (м/ч):").grid(row=2, column=0, sticky='w', pady=4)
        self.secondary_interval_entry = ttk.Entry(self.kmu_box, width=40)
        self.secondary_interval_entry.insert(0, "250")
        self.secondary_interval_entry.grid(row=2, column=1, sticky='ew', pady=4)
        bind_entry_shortcuts(self.secondary_interval_entry)
        self.kmu_box.columnconfigure(1, weight=1)
        
        # Ситуация
        ttk.Label(main_frame, text="Ситуация:").grid(row=11, column=0, sticky='w', pady=5)
        self.situation_entry = ttk.Entry(main_frame, width=40)
        self.situation_entry.grid(row=11, column=1, pady=5, sticky='ew')
        bind_entry_shortcuts(self.situation_entry)
        
        # Сервис
        ttk.Label(main_frame, text="Сервис:").grid(row=12, column=0, sticky='w', pady=5)
        self.service_entry = ttk.Entry(main_frame, width=40)
        self.service_entry.grid(row=12, column=1, pady=5, sticky='ew')
        bind_entry_shortcuts(self.service_entry)
        
        insurance_box = ttk.LabelFrame(main_frame, text="Страховка", padding=10)
        insurance_box.grid(row=13, column=0, columnspan=2, sticky='ew', pady=(4, 14))
        ttk.Label(insurance_box, text="Дата окончания (ДД.ММ.ГГГГ):").pack(anchor='w')
        self.insurance_entry = ttk.Entry(insurance_box, width=52)
        self.insurance_entry.pack(fill='x', pady=(2, 4))
        bind_entry_shortcuts(self.insurance_entry)
        bind_date_dd_mm_yyyy(self.insurance_entry)
        ttk.Label(insurance_box, text="Вложение — полис или скан:", font=('Arial', 9)).pack(anchor='w', pady=(6, 0))
        insurance_file_frame = ttk.Frame(insurance_box)
        insurance_file_frame.pack(fill='x', pady=(2, 0))
        self.insurance_file_label = ttk.Label(insurance_file_frame, text="Файл не выбран", foreground='gray')
        self.insurance_file_label.pack(side='left', fill='x', expand=True)
        ttk.Button(insurance_file_frame, text="Выбрать", command=self.select_insurance_file).pack(side='right', padx=(8, 4))
        ttk.Button(insurance_file_frame, text="Просмотреть", command=self.preview_insurance_file).pack(side='right', padx=4)
        ttk.Button(insurance_file_frame, text="Очистить", command=self.clear_insurance_file).pack(side='right')

        diagnostic_box = ttk.LabelFrame(main_frame, text="Диагностическая карта", padding=10)
        diagnostic_box.grid(row=14, column=0, columnspan=2, sticky='ew', pady=(0, 14))
        ttk.Label(diagnostic_box, text="Дата (ДД.ММ.ГГГГ):").pack(anchor='w')
        self.diagnostic_card_entry = ttk.Entry(diagnostic_box, width=52)
        self.diagnostic_card_entry.pack(fill='x', pady=(2, 4))
        bind_entry_shortcuts(self.diagnostic_card_entry)
        bind_date_dd_mm_yyyy(self.diagnostic_card_entry)
        ttk.Label(diagnostic_box, text="Вложение — скан или фото карты:", font=('Arial', 9)).pack(anchor='w', pady=(6, 0))
        diagnostic_file_frame = ttk.Frame(diagnostic_box)
        diagnostic_file_frame.pack(fill='x', pady=(2, 0))
        self.diagnostic_file_label = ttk.Label(diagnostic_file_frame, text="Файл не выбран", foreground='gray')
        self.diagnostic_file_label.pack(side='left', fill='x', expand=True)
        ttk.Button(diagnostic_file_frame, text="Выбрать", command=self.select_diagnostic_file).pack(side='right', padx=(8, 4))
        ttk.Button(diagnostic_file_frame, text="Просмотреть", command=self.preview_diagnostic_file).pack(side='right', padx=4)
        ttk.Button(diagnostic_file_frame, text="Очистить", command=self.clear_diagnostic_file).pack(side='right')
        
        ttk.Label(main_frame, text="Пропуск МКАД (ДД.ММ.ГГГГ):").grid(row=15, column=0, sticky='nw', pady=5)
        mkad_col = ttk.Frame(main_frame)
        mkad_col.grid(row=15, column=1, sticky='ew', pady=5)
        self.mkad_pass_entry = ttk.Entry(mkad_col, width=40)
        self.mkad_pass_entry.pack(anchor='w', fill='x')
        bind_entry_shortcuts(self.mkad_pass_entry)
        bind_date_dd_mm_yyyy(self.mkad_pass_entry)
        ttk.Label(mkad_col, text="Можно оставить пустым", font=('Arial', 8), foreground='gray').pack(anchor='w')
        
        main_frame.columnconfigure(1, weight=1)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=16, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Сохранить", command=self.save, width=15).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Отмена", command=self.dialog.destroy, width=15).pack(side='left', padx=5)
        
        # Фокус на первое поле
        self.name_entry.focus()
        self.on_has_kmu_toggled()
    
    def on_measurement_type_changed(self, event=None):
        """Обработчик изменения типа учета - обновляет единицы измерения"""
        if self.measurement_type.get() == 'Пробег (км)':
            self.last_maintenance_label.config(text="Последнее ТО на (км, прошлое значение):")
            self.current_value_label.config(text="Текущий пробег (км) — ВВОДИТЬ СЮДА:")
            self.interval_summer_label.config(text="Интервал ТО летом (км):")
            self.interval_winter_label.config(text="Интервал ТО зимой (км):")
            # Устанавливаем стандартные значения для пробега
            if self.interval_summer_entry.get() == "500" or not self.interval_summer_entry.get():
                self.interval_summer_entry.delete(0, tk.END)
                self.interval_summer_entry.insert(0, "10000")
            if self.interval_winter_entry.get() == "300" or not self.interval_winter_entry.get():
                self.interval_winter_entry.delete(0, tk.END)
                self.interval_winter_entry.insert(0, "7500")
        else:  # Моточасы
            self.last_maintenance_label.config(text="Последнее ТО на (моточасы, прошлое значение):")
            self.current_value_label.config(text="Текущие моточасы — ВВОДИТЬ СЮДА:")
            self.interval_summer_label.config(text="Интервал ТО летом (м/ч):")
            self.interval_winter_label.config(text="Интервал ТО зимой (м/ч):")
            # Устанавливаем стандартные значения для моточасов
            if self.interval_summer_entry.get() == "10000" or not self.interval_summer_entry.get():
                self.interval_summer_entry.delete(0, tk.END)
                self.interval_summer_entry.insert(0, "500")
            if self.interval_winter_entry.get() == "7500" or not self.interval_winter_entry.get():
                self.interval_winter_entry.delete(0, tk.END)
                self.interval_winter_entry.insert(0, "300")

    def on_has_kmu_toggled(self):
        """Включает/отключает блок КМУ по чекбоксу."""
        # Поля КМУ не блокируем: галочка влияет на бизнес-логику,
        # но значения должны быть всегда видимы/редактируемы.
        state = 'normal'
        for widget in (
            self.secondary_last_maintenance_entry,
            self.secondary_current_value_entry,
            self.secondary_interval_entry,
        ):
            widget.configure(state=state)
    
    def _equipment_field(self, equipment, key, default=''):
        """Безопасное чтение поля из sqlite3.Row или dict."""
        if equipment is None:
            return default
        if isinstance(equipment, dict):
            v = equipment.get(key, default)
            return default if v is None else v
        try:
            v = equipment[key]
            return default if v is None else v
        except Exception:
            return default

    def _as_bool(self, value) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        text = str(value or '').strip().lower()
        return text in ('1', 'true', 't', 'yes', 'y', 'on')

    def load_equipment_data(self):
        """Загрузка данных техники для редактирования"""
        # Всегда стараемся брать СВЕЖИЕ данные из БД по ID,
        # чтобы после обновления через Telegram-бот не показывались старые значения.
        equipment = None
        if self.equipment_reg_number:
            try:
                for row in self.db.get_all_equipment() or []:
                    if str(self._equipment_field(row, 'reg_number', '') or '').strip() == self.equipment_reg_number:
                        equipment = row
                        break
            except Exception:
                equipment = None
        if self.equipment_id is not None:
            try:
                equipment = equipment or self.db.get_equipment(self.equipment_id)
            except Exception:
                equipment = None
        if not equipment:
            equipment = self.prefilled_equipment
        if not equipment and self.prefilled_equipment:
            # Доп. fallback: если ID не сработал, пробуем найти по рег. номеру.
            reg = str(self._equipment_field(self.prefilled_equipment, 'reg_number', '') or '').strip()
            if reg:
                for row in self.db.get_all_equipment() or []:
                    if str(self._equipment_field(row, 'reg_number', '') or '').strip() == reg:
                        equipment = row
                        break
        if equipment:
            self.name_entry.insert(0, str(self._equipment_field(equipment, 'name', '') or ''))
            self.sts_entry.insert(0, str(self._equipment_field(equipment, 'sts_pts', '') or ''))
            self.sts_certificate_entry.insert(0, self._equipment_field(equipment, 'sts_certificate', '') or '')
            self.reg_number_entry.insert(0, str(self._equipment_field(equipment, 'reg_number', '') or ''))
            
            measurement_type = 'Пробег (км)' if self._equipment_field(equipment, 'measurement_type', 'mileage') == 'mileage' else 'Моточасы'
            self.measurement_type.set(measurement_type)
            
            self.last_maintenance_entry.delete(0, tk.END)
            self.last_maintenance_entry.insert(0, str(self._equipment_field(equipment, 'last_maintenance', 0)))
            
            self.current_value_entry.delete(0, tk.END)
            self.current_value_entry.insert(0, str(self._equipment_field(equipment, 'current_value', 0)))
            self.original_current_value = int(self._equipment_field(equipment, 'current_value', 0) or 0)
            self.current_value_updated_at = self._equipment_field(equipment, 'current_value_updated_at', '')
            has_kmu = self._as_bool(self._equipment_field(equipment, 'has_kmu', 0))
            self.has_kmu_var.set(has_kmu)
            self.secondary_last_maintenance_entry.delete(0, tk.END)
            self.secondary_last_maintenance_entry.insert(0, str(self._equipment_field(equipment, 'secondary_last_maintenance', 0)))
            self.secondary_current_value_entry.delete(0, tk.END)
            self.secondary_current_value_entry.insert(0, str(self._equipment_field(equipment, 'secondary_current_value', 0)))
            self.original_secondary_current_value = int(self._equipment_field(equipment, 'secondary_current_value', 0) or 0)
            self.secondary_current_value_updated_at = self._equipment_field(equipment, 'secondary_current_value_updated_at', '')
            self.secondary_interval_entry.delete(0, tk.END)
            self.secondary_interval_entry.insert(0, str(self._equipment_field(equipment, 'secondary_maintenance_interval', 250)))
            self.on_has_kmu_toggled()
            
            self.interval_summer_entry.delete(0, tk.END)
            self.interval_summer_entry.insert(0, str(self._equipment_field(equipment, 'maintenance_interval_summer', 10000)))
            
            self.interval_winter_entry.delete(0, tk.END)
            self.interval_winter_entry.insert(0, str(self._equipment_field(equipment, 'maintenance_interval_winter', 7500)))
            
            self.situation_entry.insert(0, self._equipment_field(equipment, 'situation', '') or '')
            self.service_entry.insert(0, self._equipment_field(equipment, 'service', '') or '')
            self.insurance_entry.insert(0, self._equipment_field(equipment, 'insurance_date', '') or '')
            self.diagnostic_card_entry.insert(0, self._equipment_field(equipment, 'diagnostic_card_date', '') or '')
            self.mkad_pass_entry.insert(0, self._equipment_field(equipment, 'mkad_pass_date', '') or '')

            self.current_insurance_file_path = self._equipment_field(equipment, 'insurance_file_path', '') or ''
            self.current_diagnostic_file_path = self._equipment_field(equipment, 'diagnostic_card_file_path', '') or ''
            self.current_sts_file_path = self._equipment_field(equipment, 'sts_file_path', '') or ''

            if self.current_insurance_file_path:
                self.insurance_action = 'keep'
                self.insurance_file_label.config(
                    text=os.path.basename(self.current_insurance_file_path), foreground='black'
                )
            if self.current_diagnostic_file_path:
                self.diagnostic_action = 'keep'
                self.diagnostic_file_label.config(
                    text=os.path.basename(self.current_diagnostic_file_path), foreground='black'
                )
            if self.current_sts_file_path:
                self.sts_action = 'keep'
                self.sts_file_label.config(
                    text=os.path.basename(self.current_sts_file_path), foreground='black'
                )
            
            # Обновить единицы измерения согласно типу учета
            self.on_measurement_type_changed()

    def _open_attached_file(self, file_path, caption):
        if not file_path:
            messagebox.showinfo("Информация", f"Файл для '{caption}' не прикреплен")
            return
        try:
            if str(file_path).startswith('supabase://') and hasattr(self.db, 'resolve_invoice_path'):
                import tempfile
                import urllib.request
                url = self.db.resolve_invoice_path(file_path)
                if not url:
                    messagebox.showerror("Ошибка", "Не удалось получить ссылку на файл")
                    return
                file_ext = file_path.split('.')[-1] if '.' in file_path else 'bin'
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_ext}')
                temp_path = temp_file.name
                temp_file.close()
                urllib.request.urlretrieve(url, temp_path)
                os.startfile(temp_path)
                return
            if os.path.exists(file_path):
                os.startfile(file_path)
                return
            messagebox.showerror("Ошибка", f"Файл не найден:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{str(e)}")

    def _delete_old_cloud_file(self, uri):
        """Удаляет прежний объект в Supabase Storage при замене файла (не дублировать бакет)."""
        if not uri or not str(uri).startswith('supabase://'):
            return
        if hasattr(self.db, 'delete_storage_file'):
            self.db.delete_storage_file(uri)

    def _copy_or_upload_document(self, source_file_path, reg_number):
        """Сохраняет файл в облаке или локально и возвращает путь."""
        if hasattr(self.db, 'upload_invoice_file'):
            return self.db.upload_invoice_file(source_file_path, reg_number)

        from pdf_compress import read_file_bytes_for_upload

        docs_dir = os.path.join(os.path.dirname(__file__), 'equipment_docs')
        os.makedirs(docs_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{reg_number}_{timestamp}{os.path.splitext(source_file_path)[1]}"
        destination_path = os.path.join(docs_dir, filename)
        data = read_file_bytes_for_upload(source_file_path)
        with open(destination_path, 'wb') as out:
            out.write(data)
        return destination_path

    def select_insurance_file(self):
        file_path = filedialog.askopenfilename(
            parent=self.dialog,
            title="Выберите файл страховки",
            filetypes=[
                ('Все файлы', '*.*'),
                ('PDF', '*.pdf'),
                ('Изображения', '*.jpg'),
                ('Изображения PNG', '*.png'),
            ],
        )
        if file_path:
            self.insurance_source_path = file_path
            self.insurance_action = 'replace'
            self.insurance_file_label.config(text=os.path.basename(file_path), foreground='black')

    def clear_insurance_file(self):
        self.insurance_source_path = None
        self.insurance_action = 'clear'
        self.current_insurance_file_path = ''
        self.insurance_file_label.config(text="Файл не выбран", foreground='gray')

    def preview_insurance_file(self):
        if self.insurance_action == 'replace' and self.insurance_source_path:
            self._open_attached_file(self.insurance_source_path, "Страховка")
            return
        path = self.current_insurance_file_path if self.insurance_action == 'keep' else ''
        self._open_attached_file(path, "Страховка")

    def select_diagnostic_file(self):
        file_path = filedialog.askopenfilename(
            parent=self.dialog,
            title="Выберите файл диагностической карты",
            filetypes=[
                ('Все файлы', '*.*'),
                ('PDF', '*.pdf'),
                ('Изображения', '*.jpg'),
                ('Изображения PNG', '*.png'),
            ],
        )
        if file_path:
            self.diagnostic_source_path = file_path
            self.diagnostic_action = 'replace'
            self.diagnostic_file_label.config(text=os.path.basename(file_path), foreground='black')

    def clear_diagnostic_file(self):
        self.diagnostic_source_path = None
        self.diagnostic_action = 'clear'
        self.current_diagnostic_file_path = ''
        self.diagnostic_file_label.config(text="Файл не выбран", foreground='gray')

    def preview_diagnostic_file(self):
        if self.diagnostic_action == 'replace' and self.diagnostic_source_path:
            self._open_attached_file(self.diagnostic_source_path, "Диагностическая карта")
            return
        path = self.current_diagnostic_file_path if self.diagnostic_action == 'keep' else ''
        self._open_attached_file(path, "Диагностическая карта")

    def select_sts_file(self):
        file_path = filedialog.askopenfilename(
            parent=self.dialog,
            title="Выберите файл СТС",
            filetypes=[
                ('Все файлы', '*.*'),
                ('PDF', '*.pdf'),
                ('Изображения', '*.jpg'),
                ('Изображения PNG', '*.png'),
            ],
        )
        if file_path:
            self.sts_source_path = file_path
            self.sts_action = 'replace'
            self.sts_file_label.config(text=os.path.basename(file_path), foreground='black')

    def clear_sts_file(self):
        self.sts_source_path = None
        self.sts_action = 'clear'
        self.current_sts_file_path = ''
        self.sts_file_label.config(text="Файл не выбран", foreground='gray')

    def preview_sts_file(self):
        if self.sts_action == 'replace' and self.sts_source_path:
            self._open_attached_file(self.sts_source_path, "СТС")
            return
        path = self.current_sts_file_path if self.sts_action == 'keep' else ''
        self._open_attached_file(path, "СТС")
    
    def save(self):
        """Сохранение данных"""
        # Валидация
        name = self.name_entry.get().strip()
        reg_number = self.reg_number_entry.get().strip()
        
        if not name:
            messagebox.showerror("Ошибка", "Введите название техники")
            return
        
        if not reg_number:
            messagebox.showerror("Ошибка", "Введите регистрационный номер")
            return
        
        try:
            last_maintenance = int(self.last_maintenance_entry.get())
            current_value = int(self.current_value_entry.get())
            interval_summer = int(self.interval_summer_entry.get())
            interval_winter = int(self.interval_winter_entry.get())
            has_kmu = bool(self.has_kmu_var.get())
            secondary_current_value = int(self.secondary_current_value_entry.get() or 0)
            secondary_last_maintenance = int(self.secondary_last_maintenance_entry.get() or 0)
            secondary_interval = int(self.secondary_interval_entry.get() or 250)
        except ValueError:
            messagebox.showerror("Ошибка", "Пробег/моточасы и интервалы должны быть числами")
            return
        
        measurement_type = 'mileage' if self.measurement_type.get() == 'Пробег (км)' else 'motohours'
        current_value_updated_at = self.current_value_updated_at
        if self.original_current_value is None or current_value != self.original_current_value:
            current_value_updated_at = datetime.now().strftime('%d.%m')
        secondary_current_value_updated_at = self.secondary_current_value_updated_at
        if (
            self.original_secondary_current_value is None
            or secondary_current_value != self.original_secondary_current_value
        ):
            secondary_current_value_updated_at = datetime.now().strftime('%d.%m')

        if self.insurance_action == 'keep':
            insurance_file_path = self.current_insurance_file_path
        elif self.insurance_action == 'clear':
            self._delete_old_cloud_file(self.current_insurance_file_path)
            insurance_file_path = ''
        else:
            insurance_file_path = ''
            if self.insurance_source_path:
                try:
                    old_ins = self.current_insurance_file_path
                    insurance_file_path = self._copy_or_upload_document(self.insurance_source_path, reg_number)
                    if old_ins and insurance_file_path and old_ins != insurance_file_path:
                        self._delete_old_cloud_file(old_ins)
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось сохранить файл страховки:\n{str(e)}")
                    return

        if self.diagnostic_action == 'keep':
            diagnostic_file_path = self.current_diagnostic_file_path
        elif self.diagnostic_action == 'clear':
            self._delete_old_cloud_file(self.current_diagnostic_file_path)
            diagnostic_file_path = ''
        else:
            diagnostic_file_path = ''
            if self.diagnostic_source_path:
                try:
                    old_diag = self.current_diagnostic_file_path
                    diagnostic_file_path = self._copy_or_upload_document(self.diagnostic_source_path, reg_number)
                    if old_diag and diagnostic_file_path and old_diag != diagnostic_file_path:
                        self._delete_old_cloud_file(old_diag)
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось сохранить файл диагностической карты:\n{str(e)}")
                    return

        if self.sts_action == 'keep':
            sts_file_path = self.current_sts_file_path
        elif self.sts_action == 'clear':
            self._delete_old_cloud_file(self.current_sts_file_path)
            sts_file_path = ''
        else:
            sts_file_path = ''
            if self.sts_source_path:
                try:
                    old_sts = self.current_sts_file_path
                    sts_file_path = self._copy_or_upload_document(self.sts_source_path, reg_number)
                    if old_sts and sts_file_path and old_sts != sts_file_path:
                        self._delete_old_cloud_file(old_sts)
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось сохранить файл СТС:\n{str(e)}")
                    return
        
        try:
            if self.equipment_id:
                # Обновление
                self.db.update_equipment(
                    self.equipment_id,
                    name=name,
                    sts_pts=self.sts_entry.get().strip(),
                    reg_number=reg_number,
                    measurement_type=measurement_type,
                    last_maintenance=last_maintenance,
                    current_value=current_value,
                    secondary_last_maintenance=secondary_last_maintenance,
                    secondary_current_value=secondary_current_value,
                    secondary_current_value_updated_at=secondary_current_value_updated_at,
                    secondary_maintenance_interval=secondary_interval,
                    has_kmu=has_kmu,
                    maintenance_interval_summer=interval_summer,
                    maintenance_interval_winter=interval_winter,
                    situation=self.situation_entry.get().strip(),
                    service=self.service_entry.get().strip(),
                    insurance_date=self.insurance_entry.get().strip(),
                    insurance_file_path=insurance_file_path,
                    diagnostic_card_date=self.diagnostic_card_entry.get().strip(),
                    diagnostic_card_file_path=diagnostic_file_path,
                    mkad_pass_date=self.mkad_pass_entry.get().strip(),
                    current_value_updated_at=current_value_updated_at,
                    sts_certificate=self.sts_certificate_entry.get().strip(),
                    sts_file_path=sts_file_path,
                )
                messagebox.showinfo("Успех", "Данные техники обновлены")
            else:
                # Добавление
                self.db.add_equipment(
                    name=name,
                    sts_pts=self.sts_entry.get().strip(),
                    reg_number=reg_number,
                    measurement_type=measurement_type,
                    last_maintenance=last_maintenance,
                    current_value=current_value,
                    secondary_last_maintenance=secondary_last_maintenance,
                    secondary_current_value=secondary_current_value,
                    secondary_current_value_updated_at=secondary_current_value_updated_at,
                    secondary_maintenance_interval=secondary_interval,
                    has_kmu=has_kmu,
                    maintenance_interval_summer=interval_summer,
                    maintenance_interval_winter=interval_winter,
                    situation=self.situation_entry.get().strip(),
                    service=self.service_entry.get().strip(),
                    insurance_date=self.insurance_entry.get().strip(),
                    insurance_file_path=insurance_file_path,
                    diagnostic_card_date=self.diagnostic_card_entry.get().strip(),
                    diagnostic_card_file_path=diagnostic_file_path,
                    mkad_pass_date=self.mkad_pass_entry.get().strip(),
                    current_value_updated_at=current_value_updated_at,
                    sts_certificate=self.sts_certificate_entry.get().strip(),
                    sts_file_path=sts_file_path,
                )
                messagebox.showinfo("Успех", "Техника добавлена")
            
            self.result = True
            self.dialog.destroy()
            
        except ValueError as e:
            messagebox.showerror("Ошибка", str(e))
        except Exception as e:
            messagebox.showerror(
                "Ошибка",
                "Не удалось сохранить технику.\n\n"
                f"Причина: {str(e)}\n\n"
                "Если используется облачная БД, проверьте выполнение миграций:\n"
                "- migration_add_equipment_documents.sql\n"
                "- migration_add_equipment_current_value_updated_at.sql\n"
                "- migration_add_equipment_secondary_counter.sql"
            )


class AssignDriversDialog:
    """Диалог привязки водителей к технике"""
    
    def __init__(self, parent, db, equipment_id, equipment_name):
        self.db = db
        self.equipment_id = equipment_id
        self.equipment_name = equipment_name
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Водители: {equipment_name}")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Центрирование окна
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (400 // 2)
        self.dialog.geometry(f"+{x}+{y}")
        
        self.create_widgets()
        self.load_drivers()
        
        # Применение горячих клавиш ко всем полям ввода
        bind_all_entries(self.dialog)
    
    def create_widgets(self):
        """Создание виджетов диалога"""
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Выберите водителей для этой техники:", 
                 font=('Arial', 10, 'bold')).pack(pady=5)
        
        # Список водителей с чекбоксами
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill='both', expand=True, pady=10)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')
        
        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, 
                                  selectmode='multiple', height=15)
        self.listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        # Кнопки
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Сохранить", command=self.save, width=15).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Отмена", command=self.dialog.destroy, width=15).pack(side='left', padx=5)
    
    def load_drivers(self):
        """Загрузка списка водителей"""
        self.drivers = self.db.get_all_drivers()
        assigned_drivers = self.db.get_equipment_drivers(self.equipment_id)
        assigned_ids = [d['id'] for d in assigned_drivers]
        
        for i, driver in enumerate(self.drivers):
            self.listbox.insert(tk.END, f"{driver['name']} - {driver['phone']}")
            if driver['id'] in assigned_ids:
                self.listbox.selection_set(i)
    
    def save(self):
        """Сохранение привязки водителей"""
        # Удаляем все текущие привязки
        current_drivers = self.db.get_equipment_drivers(self.equipment_id)
        for driver in current_drivers:
            self.db.remove_driver_from_equipment(self.equipment_id, driver['id'])
        
        # Добавляем новые привязки
        selected_indices = self.listbox.curselection()
        for index in selected_indices:
            driver = self.drivers[index]
            self.db.assign_driver_to_equipment(self.equipment_id, driver['id'])
        
        self.result = True
        messagebox.showinfo("Успех", "Водители привязаны к технике")
        self.dialog.destroy()
