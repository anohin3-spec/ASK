"""
Модуль для управления неисправностями
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import os
from keyboard_shortcuts import bind_entry_shortcuts, bind_all_entries


class IssueManager:
    def __init__(self, db):
        self.db = db


def _split_invoice_paths(value):
    raw = str(value or '').strip()
    if not raw:
        return []
    normalized = raw.replace('\r', '\n').replace(';', '\n')
    return [p.strip() for p in normalized.split('\n') if p.strip()]


def _join_invoice_paths(paths):
    return '\n'.join([str(p).strip() for p in (paths or []) if str(p).strip()])


def _store_invoice_files(db, source_paths, reg_number='issue'):
    stored = []
    for src in source_paths or []:
        if not src:
            continue
        try:
            if hasattr(db, 'upload_invoice_file'):
                stored_path = db.upload_invoice_file(src, reg_number or 'issue')
            else:
                from pdf_compress import read_file_bytes_for_upload
                docs_dir = os.path.join(os.path.dirname(__file__), 'issue_invoices')
                os.makedirs(docs_dir, exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{(reg_number or 'issue')}_{timestamp}{os.path.splitext(src)[1]}"
                stored_path = os.path.join(docs_dir, filename)
                data = read_file_bytes_for_upload(src)
                with open(stored_path, 'wb') as f:
                    f.write(data)
            stored.append(stored_path)
        except Exception as e:
            raise RuntimeError(f"{os.path.basename(src)}: {e}") from e
    return stored


class IssueDialog:
    """Диалог добавления неисправности"""
    
    def __init__(self, parent, db, equipment_id=None, issue_id=None):
        self.db = db
        self.equipment_id = equipment_id
        self.issue_id = issue_id
        self.result = None
        self.existing_invoice_paths = []
        self.new_invoice_source_paths = []
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Редактировать неисправность" if self.issue_id else "Добавить неисправность")
        self.dialog.geometry("700x680")
        self.dialog.resizable(True, True)
        self.dialog.minsize(660, 600)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Центрирование окна
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (700 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (680 // 2)
        self.dialog.geometry(f"+{x}+{y}")
        
        self.create_widgets()
        if self.issue_id:
            self.load_issue_data()
        
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
        
        # Инициализация данных водителей
        self.driver_data = {}
        
        # Выбор водителя (СОЗДАЕМ ДО вызова on_equipment_selected)
        ttk.Label(main_frame, text="Водитель:", font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=10)
        
        self.driver_combo = ttk.Combobox(main_frame, state='readonly', width=40, font=('Arial', 10))
        self.driver_combo.grid(row=1, column=1, pady=10, sticky='ew')
        
        # Теперь можем настроить выбор техники
        if self.equipment_id:
            # Если передан ID техники, выбираем её
            for key, eq in self.equipment_data.items():
                if eq['id'] == self.equipment_id:
                    self.equipment_combo.set(key)
                    self.on_equipment_selected(None)
                    break
        
        self.equipment_combo.bind('<<ComboboxSelected>>', self.on_equipment_selected)
        
        # Описание неисправности
        ttk.Label(main_frame, text="Описание неисправности:", font=('Arial', 10)).grid(row=2, column=0, sticky='nw', pady=10)
        self.description_text = tk.Text(main_frame, width=40, height=8, font=('Arial', 10))
        self.description_text.grid(row=2, column=1, pady=10, sticky='nsew')

        invoices_box = ttk.LabelFrame(main_frame, text="Счета / вложения к неисправности", padding=8)
        invoices_box.grid(row=3, column=0, columnspan=2, sticky='nsew', pady=(4, 8))
        self.invoices_listbox = tk.Listbox(invoices_box, height=5, exportselection=False)
        self.invoices_listbox.grid(row=0, column=0, sticky='nsew', pady=(0, 6))
        inv_buttons = ttk.Frame(invoices_box)
        inv_buttons.grid(row=1, column=0, sticky='ew')
        ttk.Button(inv_buttons, text="Добавить файлы", command=self.add_invoice_files).grid(row=0, column=0, padx=(0, 6), sticky='w')
        ttk.Button(inv_buttons, text="Убрать выбранный", command=self.remove_selected_invoice).grid(row=0, column=1, padx=6, sticky='w')
        ttk.Button(inv_buttons, text="Открыть", command=self.preview_selected_invoice).grid(row=0, column=2, padx=(6, 0), sticky='w')
        invoices_box.columnconfigure(0, weight=1)
        invoices_box.rowconfigure(0, weight=1)
        
        # Настройка растягивания столбцов
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Кнопки
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=(10, 4), sticky='ew')
        
        ttk.Button(button_frame, text="Сохранить", command=self.save, width=15).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Отмена", command=self.dialog.destroy, width=15).pack(side='left', padx=5)
    
    def on_equipment_selected(self, event):
        """Обработчик выбора техники - загружает водителей"""
        selected = self.equipment_combo.get()
        if selected in self.equipment_data:
            equipment = self.equipment_data[selected]
            
            # Загружаем водителей этой техники
            drivers = self.db.get_equipment_drivers(equipment['id'])
            self.driver_data = {f"{d['name']} ({d['phone']})": d for d in drivers}
            
            self.driver_combo['values'] = ['Не указан'] + list(self.driver_data.keys())
            self.driver_combo.set('Не указан')
    
    def save(self):
        """Сохранение неисправности"""
        # Валидация
        selected = self.equipment_combo.get()
        if not selected:
            messagebox.showerror("Ошибка", "Выберите технику")
            return
        
        equipment = self.equipment_data[selected]
        
        description = self.description_text.get('1.0', tk.END).strip()
        if not description:
            messagebox.showerror("Ошибка", "Введите описание неисправности")
            return
        
        # Получение водителя
        driver_id = None
        driver_selected = self.driver_combo.get()
        if driver_selected and driver_selected != 'Не указан' and driver_selected in self.driver_data:
            driver_id = self.driver_data[driver_selected]['id']
        
        try:
            all_paths = list(self.existing_invoice_paths)
            if self.new_invoice_source_paths:
                all_paths.extend(_store_invoice_files(self.db, self.new_invoice_source_paths, equipment.get('reg_number') or 'issue'))
            joined_invoice_paths = _join_invoice_paths(all_paths)
            if self.issue_id:
                self.db.update_issue(
                    issue_id=self.issue_id,
                    equipment_id=equipment['id'],
                    description=description,
                    driver_id=driver_id,
                    resolution_invoice_path=joined_invoice_paths,
                )
                messagebox.showinfo("Успех", "Неисправность обновлена")
            else:
                self.db.add_issue(
                    equipment_id=equipment['id'],
                    description=description,
                    driver_id=driver_id,
                    resolution_invoice_path=joined_invoice_paths,
                )
                messagebox.showinfo("Успех", "Неисправность добавлена")
            self.result = True
            self.dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при сохранении:\n{str(e)}")

    def load_issue_data(self):
        """Загрузка данных неисправности для редактирования."""
        issue = self.db.get_issue(self.issue_id)
        if not issue:
            messagebox.showerror("Ошибка", "Не удалось загрузить неисправность")
            self.dialog.destroy()
            return

        eq_id = issue.get('equipment_id')
        for key, eq in self.equipment_data.items():
            if str(eq.get('id')) == str(eq_id):
                self.equipment_combo.set(key)
                self.on_equipment_selected(None)
                break

        self.description_text.delete('1.0', tk.END)
        self.description_text.insert('1.0', issue.get('description', ''))

        issue_driver_id = issue.get('driver_id')
        if issue_driver_id:
            for display, drv in self.driver_data.items():
                if str(drv.get('id')) == str(issue_driver_id):
                    self.driver_combo.set(display)
                    break
        self.existing_invoice_paths = _split_invoice_paths(issue.get('resolution_invoice_path', ''))
        self.new_invoice_source_paths = []
        self.refresh_invoice_listbox()

    def refresh_invoice_listbox(self):
        self.invoices_listbox.delete(0, tk.END)
        for path in self.existing_invoice_paths:
            self.invoices_listbox.insert(tk.END, f"[сохранен] {os.path.basename(path)}")
        for path in self.new_invoice_source_paths:
            self.invoices_listbox.insert(tk.END, f"[новый] {os.path.basename(path)}")
        if self.invoices_listbox.size() == 0:
            self.invoices_listbox.insert(tk.END, "Файлы не выбраны")

    def add_invoice_files(self):
        paths = filedialog.askopenfilenames(
            parent=self.dialog,
            title="Выберите счета / вложения",
            filetypes=[
                ('Все файлы', '*.*'),
                ('PDF', '*.pdf'),
                ('Изображения', '*.jpg *.jpeg *.png *.webp'),
                ('Документы Word', '*.doc *.docx'),
            ],
        )
        if paths:
            self.new_invoice_source_paths.extend([p for p in paths if p not in self.new_invoice_source_paths])
            self.refresh_invoice_listbox()

    def remove_selected_invoice(self):
        selection = self.invoices_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(self.existing_invoice_paths):
            self.existing_invoice_paths.pop(idx)
        else:
            new_idx = idx - len(self.existing_invoice_paths)
            if 0 <= new_idx < len(self.new_invoice_source_paths):
                self.new_invoice_source_paths.pop(new_idx)
        self.refresh_invoice_listbox()

    def preview_selected_invoice(self):
        selection = self.invoices_listbox.curselection()
        if not selection:
            # Если не выделено, а файл один — открываем его.
            total_paths = len(self.existing_invoice_paths) + len(self.new_invoice_source_paths)
            if total_paths == 1:
                idx = 0
            else:
                messagebox.showinfo("Информация", "Выберите файл в списке и нажмите «Открыть».")
                return
        else:
            idx = selection[0]
        path = ''
        if idx < len(self.existing_invoice_paths):
            path = self.existing_invoice_paths[idx]
        else:
            new_idx = idx - len(self.existing_invoice_paths)
            if 0 <= new_idx < len(self.new_invoice_source_paths):
                path = self.new_invoice_source_paths[new_idx]
        if not path:
            return
        if str(path).startswith('supabase://'):
            if hasattr(self.db, 'resolve_invoice_path'):
                try:
                    url = self.db.resolve_invoice_path(path)
                    if not url:
                        raise RuntimeError("Пустой URL")
                    # Ожидаемое поведение: открыть как локальный файл (без перехода в браузер).
                    import urllib.request
                    import tempfile
                    ext = path.rsplit('.', 1)[-1] if '.' in path else 'pdf'
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}')
                    temp_path = temp_file.name
                    temp_file.close()
                    urllib.request.urlretrieve(url, temp_path)
                    os.startfile(temp_path)
                    return
                except Exception as e:
                    # Резерв: если локальное открытие не удалось, пробуем открыть URL в браузере.
                    try:
                        import webbrowser
                        if url and webbrowser.open(url):
                            return
                    except Exception:
                        pass
                    messagebox.showerror("Ошибка", f"Не удалось открыть вложение:\n{e}")
                    return
        if os.path.exists(path):
            os.startfile(path)
        else:
            messagebox.showwarning("Файл не найден", f"Файл не найден:\n{path}")


class ResolveIssueDialog:
    """Диалог закрытия неисправности"""
    
    def __init__(self, parent, db, issue_id, reg_number=''):
        self.db = db
        self.issue_id = issue_id
        self.reg_number = reg_number
        self.result = None
        self.invoice_source_paths = []
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Закрыть неисправность")
        self.dialog.geometry("620x500")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Центрирование окна
        self.dialog.update_idletasks()
        width = 550
        height = 500
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
        
        self.create_widgets()
        
        # Применение горячих клавиш ко всем полям ввода
        bind_all_entries(self.dialog)
    
    def create_widgets(self):
        """Создание виджетов диалога"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Комментарий к решению (необязательно):", 
                 font=('Arial', 10, 'bold')).pack(pady=10)
        
        ttk.Label(main_frame, text="Опишите, как была устранена неисправность:", 
                 font=('Arial', 9)).pack(pady=5)
        
        # Текстовое поле для комментария
        self.comment_text = tk.Text(main_frame, width=50, height=6, font=('Arial', 10))
        self.comment_text.pack(pady=10, fill='both', expand=True)
        bind_entry_shortcuts(self.comment_text)

        invoices_box = ttk.LabelFrame(main_frame, text="Счета по устранению", padding=8)
        invoices_box.pack(fill='both', expand=False, pady=6)
        self.invoice_listbox = tk.Listbox(invoices_box, height=4)
        self.invoice_listbox.pack(fill='both', expand=True, pady=(0, 6))
        inv_buttons = ttk.Frame(invoices_box)
        inv_buttons.pack(fill='x')
        ttk.Button(inv_buttons, text="Добавить файлы", command=self.select_invoices).pack(side='left')
        ttk.Button(inv_buttons, text="Убрать выбранный", command=self.remove_selected_invoice).pack(side='left', padx=6)
        
        # Кнопки
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="OK (Закрыть)", 
                  command=self.resolve, width=20).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Отмена", 
                  command=self.dialog.destroy, width=15).pack(side='left', padx=5)
        
        self._refresh_resolve_invoice_listbox()
        self.comment_text.focus()

    def select_invoices(self):
        """Выбор файлов счетов по устранению."""
        files = filedialog.askopenfilenames(
            parent=self.dialog,
            title="Выберите счета по устранению",
            filetypes=[
                ('Все файлы', '*.*'),
                ('PDF', '*.pdf'),
                ('Изображения', '*.jpg *.jpeg *.png *.webp'),
                ('Документы Word', '*.doc *.docx'),
            ],
        )
        if files:
            for file_path in files:
                if file_path not in self.invoice_source_paths:
                    self.invoice_source_paths.append(file_path)
            self._refresh_resolve_invoice_listbox()

    def remove_selected_invoice(self):
        selection = self.invoice_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if 0 <= idx < len(self.invoice_source_paths):
            self.invoice_source_paths.pop(idx)
        self._refresh_resolve_invoice_listbox()

    def _refresh_resolve_invoice_listbox(self):
        self.invoice_listbox.delete(0, tk.END)
        for path in self.invoice_source_paths:
            self.invoice_listbox.insert(tk.END, os.path.basename(path))
        if self.invoice_listbox.size() == 0:
            self.invoice_listbox.insert(tk.END, "Файлы не выбраны")
    
    def resolve(self):
        """Закрытие неисправности"""
        comment = self.comment_text.get('1.0', tk.END).strip()
        resolution_invoice_path = ''
        if self.invoice_source_paths:
            try:
                stored_paths = _store_invoice_files(self.db, self.invoice_source_paths, self.reg_number or 'issue')
                resolution_invoice_path = _join_invoice_paths(stored_paths)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить файл счета:\n{str(e)}")
                return
        
        # Комментарий необязателен
        try:
            self.db.update_issue_status(
                issue_id=self.issue_id,
                status='resolved',
                resolution_comment=comment if comment else 'Устранено',
                resolution_invoice_path=resolution_invoice_path
            )
            
            messagebox.showinfo("Успех", "Неисправность закрыта")
            self.result = True
            self.dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при закрытии:\n{str(e)}")
