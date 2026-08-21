"""
Диалог настроек приложения
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
from keyboard_shortcuts import bind_entry_shortcuts, bind_all_entries


class SettingsDialog:
    """Диалог настроек приложения"""
    
    def __init__(self, parent, db, auth_manager):
        self.db = db
        self.auth_manager = auth_manager
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Настройки")
        self.dialog.geometry("550x500")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Центрирование окна
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (550 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (500 // 2)
        self.dialog.geometry(f"+{x}+{y}")
        
        self.create_widgets()
        self.load_settings()
        
        # Применение горячих клавиш ко всем полям ввода
        bind_all_entries(self.dialog)
    
    def create_widgets(self):
        """Создание виджетов диалога"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Данные компании
        company_frame = ttk.LabelFrame(main_frame, text="Данные компании", padding=10)
        company_frame.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 15))
        
        ttk.Label(company_frame, text="Название:", font=('Arial', 10)).grid(row=0, column=0, sticky='w', pady=5)
        self.company_name_entry = ttk.Entry(company_frame, width=40, font=('Arial', 10))
        self.company_name_entry.grid(row=0, column=1, pady=5, sticky='ew', padx=5)
        bind_entry_shortcuts(self.company_name_entry)
        
        ttk.Label(company_frame, text="Телефон:", font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=5)
        self.company_phone_entry = ttk.Entry(company_frame, width=40, font=('Arial', 10))
        self.company_phone_entry.grid(row=1, column=1, pady=5, sticky='ew', padx=5)
        bind_entry_shortcuts(self.company_phone_entry)
        
        ttk.Label(company_frame, text="Email:", font=('Arial', 10)).grid(row=2, column=0, sticky='w', pady=5)
        self.company_email_entry = ttk.Entry(company_frame, width=40, font=('Arial', 10))
        self.company_email_entry.grid(row=2, column=1, pady=5, sticky='ew', padx=5)
        bind_entry_shortcuts(self.company_email_entry)
        
        company_frame.columnconfigure(1, weight=1)
        
        # Путь к корневой папке для хранения файлов
        ttk.Label(main_frame, text="Путь к корневой папке:", 
                 font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=10)
        
        path_frame = ttk.Frame(main_frame)
        path_frame.grid(row=1, column=1, pady=10, sticky='ew')
        
        self.root_path_entry = ttk.Entry(path_frame, width=35, font=('Arial', 9))
        self.root_path_entry.pack(side='left', fill='x', expand=True)
        bind_entry_shortcuts(self.root_path_entry)
        
        ttk.Button(path_frame, text="Обзор...", 
                  command=self.browse_root_path).pack(side='left', padx=5)
        
        ttk.Label(main_frame, text="(папка для хранения счетов и документов)", 
                 font=('Arial', 8), foreground='gray').grid(row=2, column=1, sticky='w')
        
        # Настройка растягивания столбцов
        main_frame.columnconfigure(1, weight=1)
        
        # Информация о базе данных
        info_frame = ttk.LabelFrame(main_frame, text="Информация", padding=10)
        info_frame.grid(row=3, column=0, columnspan=2, sticky='ew', pady=20)
        
        db_path = os.path.abspath(self.db.db_path) if hasattr(self.db, 'db_path') else 'Supabase Cloud'
        ttk.Label(info_frame, text=f"База данных:", font=('Arial', 9)).pack(anchor='w')
        ttk.Label(info_frame, text=db_path, font=('Arial', 8), 
                 foreground='blue').pack(anchor='w', padx=10)
        
        # Кнопки
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Сохранить", 
                  command=self.save, width=15).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Отмена", 
                  command=self.dialog.destroy, width=15).pack(side='left', padx=5)
    
    def browse_root_path(self):
        """Выбор корневой папки"""
        path = filedialog.askdirectory(title="Выберите корневую папку")
        if path:
            self.root_path_entry.delete(0, tk.END)
            self.root_path_entry.insert(0, path)
    
    def load_settings(self):
        """Загрузка настроек"""
        try:
            # Очищаем поля перед загрузкой
            self.root_path_entry.delete(0, tk.END)
            self.company_name_entry.delete(0, tk.END)
            self.company_phone_entry.delete(0, tk.END)
            self.company_email_entry.delete(0, tk.END)
            
            # Загрузка пути к корневой папке
            root_path = self.db.get_setting('root_path', '')
            if root_path:
                self.root_path_entry.insert(0, root_path)
            
            # Загрузка данных компании
            company = self.db.get_company()
            if company:
                if company.get('name'):
                    self.company_name_entry.insert(0, company['name'])
                
                # Проверяем, поддерживает ли БД phone/email
                has_contacts = 'phone' in company or 'email' in company
                
                if has_contacts:
                    if company.get('phone'):
                        self.company_phone_entry.insert(0, company['phone'])
                    if company.get('email'):
                        self.company_email_entry.insert(0, company['email'])
                else:
                    # Отключаем поля если БД не поддерживает
                    self.company_phone_entry.config(state='disabled')
                    self.company_email_entry.config(state='disabled')
                    self.company_phone_entry.insert(0, '(не поддерживается старой схемой БД)')
                    self.company_email_entry.insert(0, '(не поддерживается старой схемой БД)')
                    
        except Exception as e:
            print(f"Ошибка при загрузке настроек: {e}")
            import traceback
            traceback.print_exc()
    
    def save(self):
        """Сохранение настроек"""
        try:
            root_path = self.root_path_entry.get().strip()
            
            # Проверка папки
            if root_path and not os.path.exists(root_path):
                if messagebox.askyesno("Папка не существует", 
                                      "Создать папку?"):
                    try:
                        os.makedirs(root_path, exist_ok=True)
                    except Exception as e:
                        messagebox.showerror("Ошибка", f"Не удалось создать папку:\n{str(e)}")
                        return
                else:
                    return
            
            # Сохранение пути к корневой папке
            try:
                self.db.set_setting('root_path', root_path)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить путь к папке:\n{str(e)}")
                return
            
            # Сохранение данных компании
            company_name = self.company_name_entry.get().strip()
            company_phone = self.company_phone_entry.get().strip()
            company_email = self.company_email_entry.get().strip()
            
            # Проверяем, доступны ли поля phone/email
            phone_enabled = str(self.company_phone_entry.cget('state')) != 'disabled'
            
            company_updated = False
            if company_name:
                company_id = self.auth_manager.current_company['id']
                
                if phone_enabled:
                    # Новая схема БД с phone/email
                    company_updated = self.db.update_company(
                        company_id,
                        name=company_name,
                        phone=company_phone,
                        email=company_email
                    )
                else:
                    # Старая схема БД - только название
                    company_updated = self.db.update_company(
                        company_id,
                        name=company_name
                    )
            
            # Всегда показываем успех если хотя бы путь сохранился
            if company_name and not company_updated:
                if phone_enabled:
                    # Если новая схема и не обновилось - это ошибка
                    messagebox.showinfo("Успех", 
                                      "Настройки сохранены.\n\n"
                                      "Примечание: Данные компании (телефон/email) не были обновлены.\n"
                                      "Возможно, требуется обновление схемы БД.")
                else:
                    # Старая схема - всё нормально
                    messagebox.showinfo("Успех", "Настройки сохранены")
            else:
                messagebox.showinfo("Успех", "Настройки сохранены")
            
            self.dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка при сохранении:\n{str(e)}")
