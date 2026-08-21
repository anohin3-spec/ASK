"""
Диалоговое окно для управления водителями техники и их сменами
"""
import tkinter as tk
from tkinter import ttk, messagebox

class DriverShiftsDialog:
    def __init__(self, parent, db, equipment_id, equipment_name):
        self.db = db
        self.equipment_id = equipment_id
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Водители: {equipment_name}")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.load_data()
        
        # Центрируем окно
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        # Фрейм с инструкцией
        info_frame = ttk.Frame(self.dialog)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        info_label = ttk.Label(info_frame, text="Управление водителями и их сменами", font=("Arial", 10, "bold"))
        info_label.pack()
        
        help_text = "1-я половина: с 1 по 14/15 число • 2-я половина: с 15/16 до конца месяца • Весь месяц: водитель работает постоянно"
        help_label = ttk.Label(info_frame, text=help_text, font=("Arial", 8), foreground="gray")
        help_label.pack()
        
        # Список водителей техники
        list_frame = ttk.LabelFrame(self.dialog, text="Закреплённые водители")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox для водителей
        self.drivers_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Arial", 10))
        self.drivers_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.config(command=self.drivers_listbox.yview)
        
        self.drivers_listbox.bind('<<ListboxSelect>>', self.on_driver_select)
        
        # Фрейм для добавления водителя
        add_frame = ttk.LabelFrame(self.dialog, text="Добавить водителя")
        add_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Выбор водителя
        driver_row = ttk.Frame(add_frame)
        driver_row.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(driver_row, text="Водитель:").pack(side=tk.LEFT, padx=5)
        
        self.driver_combo = ttk.Combobox(driver_row, state='readonly', width=30)
        self.driver_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Выбор смены
        shift_row = ttk.Frame(add_frame)
        shift_row.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(shift_row, text="Смена:").pack(side=tk.LEFT, padx=5)
        
        self.shift_var = tk.StringVar(value="full")
        
        ttk.Radiobutton(shift_row, text="1-я половина", variable=self.shift_var, value="1").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(shift_row, text="2-я половина", variable=self.shift_var, value="2").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(shift_row, text="Весь месяц", variable=self.shift_var, value="full").pack(side=tk.LEFT, padx=5)
        
        # Кнопки
        button_row = ttk.Frame(add_frame)
        button_row.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(button_row, text="+ Добавить", command=self.add_driver).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_row, text="Изменить смену выбранного", command=self.update_driver_shift).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_row, text="Удалить выбранного", command=self.remove_driver).pack(side=tk.LEFT, padx=5)
        
        # Кнопка закрытия
        close_frame = ttk.Frame(self.dialog)
        close_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(close_frame, text="Закрыть", command=self.dialog.destroy).pack(side=tk.RIGHT)
    
    def load_data(self):
        """Загрузка данных"""
        # Загрузка всех доступных водителей
        try:
            all_drivers = self.db.get_all_drivers()
            driver_names = [f"{d['name']} ({d.get('phone', 'нет телефона')})" for d in all_drivers]
            self.driver_combo['values'] = driver_names
            self.all_drivers_data = all_drivers
        except Exception as e:
            print(f"Ошибка загрузки водителей: {e}")
            self.driver_combo['values'] = []
            self.all_drivers_data = []
        
        # Загрузка водителей техники
        self.refresh_equipment_drivers()
    
    def refresh_equipment_drivers(self):
        """Обновление списка водителей техники"""
        self.drivers_listbox.delete(0, tk.END)
        
        try:
            drivers = self.db.get_all_drivers_for_equipment_with_shifts(self.equipment_id)
            self.current_drivers = drivers
            
            for driver in drivers:
                name = driver.get('name', 'Без имени')
                shift_half = driver.get('shift_half')
                is_active = driver.get('is_active', False)
                
                if shift_half == 1:
                    shift_text = "1-я половина"
                elif shift_half == 2:
                    shift_text = "2-я половина"
                else:
                    shift_text = "Весь месяц"
                
                active_mark = " (в смене)" if is_active else ""
                
                display_text = f"{name} — {shift_text}{active_mark}"
                self.drivers_listbox.insert(tk.END, display_text)
        
        except Exception as e:
            print(f"Ошибка загрузки водителей техники: {e}")
            self.current_drivers = []
    
    def on_driver_select(self, event):
        """Обработка выбора водителя из списка"""
        selected_indices = self.drivers_listbox.curselection()
        if selected_indices and len(self.current_drivers) > selected_indices[0]:
            driver = self.current_drivers[selected_indices[0]]
            shift_half = driver.get('shift_half')
            
            # Устанавливаем радиокнопку в соответствии со сменой водителя
            if shift_half == 1:
                self.shift_var.set("1")
            elif shift_half == 2:
                self.shift_var.set("2")
            else:
                self.shift_var.set("full")
    
    def update_driver_shift(self):
        """Изменение смены выбранного водителя"""
        selected_indices = self.drivers_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Предупреждение", "Выберите водителя из списка для изменения смены")
            return
        
        selected_index = selected_indices[0]
        if selected_index >= len(self.current_drivers):
            return
        
        driver = self.current_drivers[selected_index]
        driver_name = driver.get('name', 'Неизвестный')
        driver_id = driver['id']
        
        # Получаем новую смену
        shift_value = self.shift_var.get()
        if shift_value == "1":
            new_shift_half = 1
            shift_text = "1-я половина"
        elif shift_value == "2":
            new_shift_half = 2
            shift_text = "2-я половина"
        else:
            new_shift_half = None
            shift_text = "весь месяц"
        
        # Проверяем, не занята ли новая смена другим водителем
        if new_shift_half is not None:
            for existing_driver in self.current_drivers:
                if existing_driver['id'] != driver_id and existing_driver.get('shift_half') == new_shift_half:
                    messagebox.showwarning(
                        "Предупреждение",
                        f"Эта смена уже занята водителем: {existing_driver.get('name')}\n"
                        f"Удалите его сначала или выберите другую смену."
                    )
                    return
        
        # Обновляем смену
        try:
            self.db.set_driver_shift(self.equipment_id, driver_id, new_shift_half)
            messagebox.showinfo("Успех", f"Смена водителя {driver_name} изменена на: {shift_text}")
            self.refresh_equipment_drivers()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось изменить смену:\n{e}")
    
    def add_driver(self):
        """Добавление водителя к технике"""
        if not self.driver_combo.get():
            messagebox.showwarning("Предупреждение", "Выберите водителя из списка")
            return
        
        # Получаем выбранного водителя
        selected_index = self.driver_combo.current()
        if selected_index < 0 or selected_index >= len(self.all_drivers_data):
            return
        
        driver = self.all_drivers_data[selected_index]
        driver_id = driver['id']
        
        # Получаем выбранную смену
        shift_value = self.shift_var.get()
        if shift_value == "1":
            shift_half = 1
        elif shift_value == "2":
            shift_half = 2
        else:
            shift_half = None
        
        # Проверяем, не занята ли смена
        if shift_half is not None:
            for existing_driver in self.current_drivers:
                if existing_driver.get('shift_half') == shift_half:
                    messagebox.showwarning(
                        "Предупреждение",
                        f"Эта смена уже занята водителем: {existing_driver.get('name')}\n"
                        f"Удалите его сначала или выберите другую смену."
                    )
                    return
        
        # Добавляем водителя
        try:
            self.db.set_driver_shift(self.equipment_id, driver_id, shift_half)
            messagebox.showinfo("Успех", f"Водитель {driver['name']} добавлен")
            self.refresh_equipment_drivers()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось добавить водителя:\n{e}")
    
    def remove_driver(self):
        """Удаление водителя от техники"""
        selected_indices = self.drivers_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Предупреждение", "Выберите водителя для удаления")
            return
        
        selected_index = selected_indices[0]
        if selected_index >= len(self.current_drivers):
            return
        
        driver = self.current_drivers[selected_index]
        driver_name = driver.get('name', 'Неизвестный')
        
        if messagebox.askyesno("Подтверждение", f"Удалить водителя {driver_name}?"):
            try:
                self.db.remove_driver_from_equipment(self.equipment_id, driver['id'])
                messagebox.showinfo("Успех", f"Водитель {driver_name} удалён")
                self.refresh_equipment_drivers()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось удалить водителя:\n{e}")
