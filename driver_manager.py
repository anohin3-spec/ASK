"""
Модуль для управления водителями
"""
import tkinter as tk
from tkinter import ttk, messagebox
from keyboard_shortcuts import bind_entry_shortcuts, bind_all_entries


class DriverManager:
    def __init__(self, db):
        self.db = db


def normalize_phone_ru(value: str) -> str:
    """Формат: X (XXX) xxx-xx-xx."""
    digits = ''.join(ch for ch in str(value or '') if ch.isdigit())
    if len(digits) == 11:
        head = digits[0]
        return f"{head} ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return value.strip()


class DriverDialog:
    """Диалог добавления/редактирования водителя"""
    
    def __init__(self, parent, db, driver_id=None, title="Водитель"):
        self.db = db
        self.driver_id = driver_id
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("450x320")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Центрирование окна
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (450 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (320 // 2)
        self.dialog.geometry(f"+{x}+{y}")
        
        self.create_widgets()
        
        # Если редактируем, загружаем данные
        if driver_id:
            self.load_driver_data()
        
        # Применение горячих клавиш ко всем полям ввода
        bind_all_entries(self.dialog)
    
    def create_widgets(self):
        """Создание виджетов диалога"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Имя
        ttk.Label(main_frame, text="Имя водителя:", font=('Arial', 10)).grid(row=0, column=0, sticky='w', pady=10)
        self.name_entry = ttk.Entry(main_frame, width=35, font=('Arial', 10))
        self.name_entry.grid(row=0, column=1, pady=10, sticky='ew')
        bind_entry_shortcuts(self.name_entry)
        
        # Телефон
        ttk.Label(main_frame, text="Телефон:", font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=10)
        self.phone_entry = ttk.Entry(main_frame, width=35, font=('Arial', 10))
        self.phone_entry.grid(row=1, column=1, pady=10, sticky='ew')
        bind_entry_shortcuts(self.phone_entry)
        ttk.Label(main_frame, text="(например: +7 900 123-45-67)", 
                 font=('Arial', 8), foreground='gray').grid(row=2, column=1, sticky='w')

        # Топливная карта
        ttk.Label(main_frame, text="Топливная карта:", font=('Arial', 10)).grid(row=3, column=0, sticky='w', pady=10)
        self.fuel_card_entry = ttk.Entry(main_frame, width=35, font=('Arial', 10))
        self.fuel_card_entry.grid(row=3, column=1, pady=10, sticky='ew')
        bind_entry_shortcuts(self.fuel_card_entry)
        ttk.Label(main_frame, text="(номер карты или комментарий)", 
                 font=('Arial', 8), foreground='gray').grid(row=4, column=1, sticky='w')
        
        # Настройка растягивания столбцов
        main_frame.columnconfigure(1, weight=1)
        
        # Кнопки
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Сохранить", command=self.save, width=15).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Отмена", command=self.dialog.destroy, width=15).pack(side='left', padx=5)
        
        # Фокус на первое поле
        self.name_entry.focus()
    
    def load_driver_data(self):
        """Загрузка данных водителя для редактирования"""
        driver = self.db.get_driver(self.driver_id)
        if driver:
            self.name_entry.insert(0, driver['name'])
            self.phone_entry.insert(0, normalize_phone_ru(driver['phone']))
            self.fuel_card_entry.insert(0, driver['fuel_card'] or '')
    
    def save(self):
        """Сохранение данных"""
        # Валидация
        name = self.name_entry.get().strip()
        phone = self.phone_entry.get().strip()
        fuel_card = self.fuel_card_entry.get().strip()
        
        if not name:
            messagebox.showerror("Ошибка", "Введите имя водителя")
            return
        
        if not phone:
            messagebox.showerror("Ошибка", "Введите номер телефона")
            return
        phone = normalize_phone_ru(phone)
        digits = ''.join(ch for ch in phone if ch.isdigit())
        if len(digits) != 11:
            messagebox.showerror("Ошибка", "Телефон должен содержать 11 цифр")
            return
        
        try:
            if self.driver_id:
                # Обновление
                self.db.update_driver(self.driver_id, name, phone, fuel_card)
                messagebox.showinfo("Успех", "Данные водителя обновлены")
            else:
                # Добавление
                self.db.add_driver(name, phone, fuel_card)
                messagebox.showinfo("Успех", "Водитель добавлен")
            
            self.result = True
            self.dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при сохранении:\n{str(e)}")
