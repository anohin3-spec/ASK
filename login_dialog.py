"""
Диалог входа в систему
"""
import tkinter as tk
from tkinter import messagebox, ttk
from credentials_manager import CredentialsManager
from keyboard_shortcuts import bind_all_entries


class LoginDialog:
    """Диалоговое окно входа в систему"""
    
    def __init__(self, auth_manager):
        """
        Инициализация диалога входа
        
        Args:
            auth_manager: Экземпляр AuthManager
        """
        self.auth_manager = auth_manager
        self.success = False
        self.root = None
        self.credentials_manager = CredentialsManager()
        
    def show(self, auto_login=False) -> bool:
        """
        Показать диалог входа
        
        Args:
            auto_login: Попытка автоматического входа
            
        Returns:
            bool: True если вход успешен, False если отменен
        """
        # Попытка автоматического входа
        if auto_login:
            saved_creds = self.credentials_manager.load_credentials()
            if saved_creds and saved_creds.get('auto_login'):
                # Попытка входа с сохраненными данными
                result = self.auth_manager.login(
                    saved_creds['username'],
                    saved_creds['password']
                )
                if result:
                    self.success = True
                    return True
        
        # Показываем окно входа
        self.root = tk.Tk()
        self.root.title("Вход в систему - Maintenance Helper")
        self.root.geometry("420x350")
        self.root.resizable(False, False)
        
        # Центрирование окна
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (420 // 2)
        y = (self.root.winfo_screenheight() // 2) - (350 // 2)
        self.root.geometry(f"420x350+{x}+{y}")
        
        # Заголовок
        title_frame = tk.Frame(self.root, bg="#2c3e50", height=55)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="🔐 Вход в систему",
            font=("Arial", 14, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        title_label.pack(expand=True)
        
        # Основная форма
        form_frame = tk.Frame(self.root, padx=35, pady=15)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Поле "Логин"
        tk.Label(
            form_frame,
            text="Логин:",
            font=("Arial", 10)
        ).grid(row=0, column=0, sticky=tk.W, pady=(5, 3))
        
        self.username_entry = tk.Entry(
            form_frame,
            font=("Arial", 10),
            width=32
        )
        self.username_entry.grid(row=1, column=0, pady=(0, 12))
        
        # Поле "Пароль"
        tk.Label(
            form_frame,
            text="Пароль:",
            font=("Arial", 10)
        ).grid(row=2, column=0, sticky=tk.W, pady=(0, 3))
        
        self.password_entry = tk.Entry(
            form_frame,
            font=("Arial", 10),
            width=32,
            show="•"
        )
        self.password_entry.grid(row=3, column=0, pady=(0, 12))
        
        # Чекбоксы
        checkbox_frame = tk.Frame(form_frame)
        checkbox_frame.grid(row=4, column=0, sticky=tk.W, pady=(0, 15))
        
        self.remember_var = tk.BooleanVar(value=False)
        remember_check = tk.Checkbutton(
            checkbox_frame,
            text="💾 Запомнить пароль",
            variable=self.remember_var,
            font=("Arial", 9)
        )
        remember_check.pack(anchor=tk.W)
        
        self.auto_login_var = tk.BooleanVar(value=False)
        auto_login_check = tk.Checkbutton(
            checkbox_frame,
            text="🚀 Автоматический вход",
            variable=self.auto_login_var,
            font=("Arial", 9)
        )
        auto_login_check.pack(anchor=tk.W, pady=(3, 0))
        
        # Загрузка сохраненных данных
        saved_creds = self.credentials_manager.load_credentials()
        if saved_creds:
            self.username_entry.insert(0, saved_creds['username'])
            self.password_entry.insert(0, saved_creds['password'])
            self.remember_var.set(True)
            self.auto_login_var.set(saved_creds.get('auto_login', False))
            self.password_entry.focus()
        else:
            self.username_entry.focus()
        
        # Кнопки
        button_frame = tk.Frame(form_frame)
        button_frame.grid(row=5, column=0, pady=(8, 0))
        
        login_btn = tk.Button(
            button_frame,
            text="Войти",
            font=("Arial", 9, "bold"),
            bg="#27ae60",
            fg="white",
            width=13,
            cursor="hand2",
            command=self.on_login
        )
        login_btn.pack(side=tk.LEFT, padx=4)
        
        cancel_btn = tk.Button(
            button_frame,
            text="Отмена",
            font=("Arial", 9),
            bg="#95a5a6",
            fg="white",
            width=13,
            cursor="hand2",
            command=self.on_cancel
        )
        cancel_btn.pack(side=tk.LEFT, padx=4)
        
        # Кнопка регистрации
        register_frame = tk.Frame(form_frame)
        register_frame.grid(row=6, column=0, pady=(12, 0))
        
        tk.Label(
            register_frame,
            text="Нет учетной записи?",
            font=("Arial", 9),
            fg="#7f8c8d"
        ).pack(side=tk.LEFT, padx=(0, 8))
        
        register_btn = tk.Button(
            register_frame,
            text="🏢 Зарегистрировать организацию",
            font=("Arial", 9, "bold"),
            bg="#3498db",
            fg="white",
            cursor="hand2",
            command=self.on_register
        )
        register_btn.pack(side=tk.LEFT)
        
        # Привязка Enter к кнопке входа
        self.username_entry.bind('<Return>', lambda e: self.password_entry.focus())
        self.password_entry.bind('<Return>', lambda e: self.on_login())
        
        # Обработка закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
        # Применение горячих клавиш ко всем полям ввода
        bind_all_entries(self.root)
        
        # Запуск главного цикла
        self.root.mainloop()
        
        return self.success
    
    def on_login(self):
        """Обработка нажатия кнопки "Войти" """
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        
        # Валидация
        if not username:
            messagebox.showerror(
                "Ошибка",
                "Введите логин",
                parent=self.root
            )
            self.username_entry.focus()
            return
        
        if not password:
            messagebox.showerror(
                "Ошибка",
                "Введите пароль",
                parent=self.root
            )
            self.password_entry.focus()
            return
        
        # Попытка входа
        result = self.auth_manager.login(username, password)
        
        if result:
            # Успешный вход
            user = result['user']
            company = result['company']
            
            # Сохранение учетных данных если нужно
            if self.remember_var.get():
                self.credentials_manager.save_credentials(
                    username,
                    password,
                    self.auto_login_var.get()
                )
            else:
                # Очистка сохраненных данных если флаг снят
                self.credentials_manager.clear_credentials()
            
            messagebox.showinfo(
                "Успешный вход",
                f"Добро пожаловать, {user['full_name']}!\n\n"
                f"Организация: {company['name']}\n"
                f"Роль: {user['role']}",
                parent=self.root
            )
            try:
                import os
                import tempfile
                from datetime import datetime
                log_path = os.path.join(tempfile.gettempdir(), "ask_startup.log")
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"[{ts}] login success user={user.get('username', '-')}\n")
            except Exception:
                pass
            
            self.success = True
            self.root.destroy()
        else:
            # Ошибка входа
            try:
                import os
                import tempfile
                from datetime import datetime
                log_path = os.path.join(tempfile.gettempdir(), "ask_startup.log")
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"[{ts}] login failed username={username}\n")
            except Exception:
                pass
            messagebox.showerror(
                "Ошибка входа",
                "Неверный логин или пароль.\n\n"
                "Проверьте правильность введенных данных.",
                parent=self.root
            )
            self.password_entry.delete(0, tk.END)
            self.password_entry.focus()
    
    def on_cancel(self):
        """Обработка отмены входа"""
        if messagebox.askyesno(
            "Выход",
            "Вы действительно хотите выйти из программы?",
            parent=self.root
        ):
            self.success = False
            self.root.destroy()
    
    def on_register(self):
        """Обработка нажатия кнопки регистрации"""
        # Открываем диалог регистрации
        register_dialog = RegisterCompanyDialog(self.root, self.auth_manager)
        if register_dialog.show():
            # После успешной регистрации можно закрыть окно входа
            # чтобы пользователь мог войти с новыми данными
            pass


class ChangePasswordDialog:
    """Диалог смены пароля"""
    
    def __init__(self, parent, auth_manager):
        """
        Инициализация диалога смены пароля
        
        Args:
            parent: Родительское окно
            auth_manager: Экземпляр AuthManager
        """
        self.parent = parent
        self.auth_manager = auth_manager
        self.success = False
        
    def show(self) -> bool:
        """
        Показать диалог смены пароля
        
        Returns:
            bool: True если пароль успешно изменен
        """
        dialog = tk.Toplevel(self.parent)
        dialog.title("Смена пароля")
        dialog.geometry("420x360")
        dialog.resizable(False, False)
        dialog.transient(self.parent)
        dialog.grab_set()
        
        # Центрирование
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (420 // 2)
        y = (dialog.winfo_screenheight() // 2) - (360 // 2)
        dialog.geometry(f"420x360+{x}+{y}")
        
        # Заголовок
        title_frame = tk.Frame(dialog, bg="#2c3e50", height=50)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="🔑 Смена пароля",
            font=("Arial", 13, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        title_label.pack(expand=True)
        
        # Форма
        form_frame = tk.Frame(dialog, padx=35, pady=15)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Старый пароль
        tk.Label(
            form_frame,
            text="Текущий пароль:",
            font=("Arial", 10)
        ).grid(row=0, column=0, sticky=tk.W, pady=(5, 3))
        
        old_password_entry = tk.Entry(
            form_frame,
            font=("Arial", 10),
            width=32,
            show="•"
        )
        old_password_entry.grid(row=1, column=0, pady=(0, 12))
        old_password_entry.focus()
        
        # Новый пароль
        tk.Label(
            form_frame,
            text="Новый пароль (минимум 6 символов):",
            font=("Arial", 10)
        ).grid(row=2, column=0, sticky=tk.W, pady=(0, 3))
        
        new_password_entry = tk.Entry(
            form_frame,
            font=("Arial", 10),
            width=32,
            show="•"
        )
        new_password_entry.grid(row=3, column=0, pady=(0, 12))
        
        # Подтверждение пароля
        tk.Label(
            form_frame,
            text="Подтвердите пароль:",
            font=("Arial", 10)
        ).grid(row=4, column=0, sticky=tk.W, pady=(0, 3))
        
        confirm_password_entry = tk.Entry(
            form_frame,
            font=("Arial", 10),
            width=32,
            show="•"
        )
        confirm_password_entry.grid(row=5, column=0, pady=(0, 15))
        
        def on_change():
            """Обработка смены пароля"""
            old_pwd = old_password_entry.get()
            new_pwd = new_password_entry.get()
            confirm_pwd = confirm_password_entry.get()
            
            # Валидация
            if not old_pwd:
                messagebox.showerror("Ошибка", "Введите текущий пароль", parent=dialog)
                return
            
            if not new_pwd:
                messagebox.showerror("Ошибка", "Введите новый пароль", parent=dialog)
                return
            
            if len(new_pwd) < 6:
                messagebox.showerror(
                    "Ошибка",
                    "Новый пароль должен содержать минимум 6 символов",
                    parent=dialog
                )
                return
            
            if new_pwd != confirm_pwd:
                messagebox.showerror("Ошибка", "Пароли не совпадают", parent=dialog)
                return
            
            # Попытка смены пароля
            if self.auth_manager.change_password(old_pwd, new_pwd):
                messagebox.showinfo(
                    "Успех",
                    "Пароль успешно изменен!",
                    parent=dialog
                )
                self.success = True
                dialog.destroy()
            else:
                messagebox.showerror(
                    "Ошибка",
                    "Неверный текущий пароль",
                    parent=dialog
                )
                old_password_entry.delete(0, tk.END)
                old_password_entry.focus()
        
        # Кнопки
        button_frame = tk.Frame(form_frame)
        button_frame.grid(row=6, column=0, pady=(8, 5))
        
        change_btn = tk.Button(
            button_frame,
            text="Изменить",
            font=("Arial", 9, "bold"),
            bg="#27ae60",
            fg="white",
            width=13,
            cursor="hand2",
            command=on_change
        )
        change_btn.pack(side=tk.LEFT, padx=4)
        
        cancel_btn = tk.Button(
            button_frame,
            text="Отмена",
            font=("Arial", 9),
            bg="#95a5a6",
            fg="white",
            width=13,
            cursor="hand2",
            command=dialog.destroy
        )
        cancel_btn.pack(side=tk.LEFT, padx=4)
        
        # Применение горячих клавиш ко всем полям ввода
        bind_all_entries(dialog)
        
        # Ожидание закрытия диалога
        dialog.wait_window()
        
        return self.success


class RegisterCompanyDialog:
    """Диалог регистрации новой компании"""
    
    def __init__(self, parent, auth_manager):
        """
        Инициализация диалога регистрации
        
        Args:
            parent: Родительское окно
            auth_manager: Экземпляр AuthManager
        """
        self.parent = parent
        self.auth_manager = auth_manager
        self.success = False
        
    def show(self) -> bool:
        """
        Показать диалог регистрации
        
        Returns:
            bool: True если регистрация успешна
        """
        dialog = tk.Toplevel(self.parent)
        dialog.title("Регистрация новой организации")
        dialog.geometry("480x540")
        dialog.resizable(False, False)
        dialog.transient(self.parent)
        dialog.grab_set()
        
        # Центрирование
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (480 // 2)
        y = (dialog.winfo_screenheight() // 2) - (540 // 2)
        dialog.geometry(f"480x540+{x}+{y}")
        
        # Заголовок
        title_frame = tk.Frame(dialog, bg="#3498db", height=55)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="🏢 Регистрация новой организации",
            font=("Arial", 13, "bold"),
            bg="#3498db",
            fg="white"
        )
        title_label.pack(expand=True)
        
        # Форма
        form_frame = tk.Frame(dialog, padx=35, pady=20)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Логин
        tk.Label(
            form_frame,
            text="Ваш логин (для входа в систему):",
            font=("Arial", 10, "bold")
        ).grid(row=0, column=0, sticky=tk.W, pady=(5, 3))
        
        username_entry = tk.Entry(
            form_frame,
            font=("Arial", 10),
            width=38
        )
        username_entry.grid(row=1, column=0, pady=(0, 12))
        username_entry.focus()
        
        # Пароль
        tk.Label(
            form_frame,
            text="Ваш пароль (минимум 6 символов):",
            font=("Arial", 10, "bold")
        ).grid(row=2, column=0, sticky=tk.W, pady=(0, 3))
        
        password_entry = tk.Entry(
            form_frame,
            font=("Arial", 10),
            width=38,
            show="•"
        )
        password_entry.grid(row=3, column=0, pady=(0, 12))
        
        # Подтверждение пароля
        tk.Label(
            form_frame,
            text="Подтвердите пароль:",
            font=("Arial", 10, "bold")
        ).grid(row=4, column=0, sticky=tk.W, pady=(0, 3))
        
        confirm_entry = tk.Entry(
            form_frame,
            font=("Arial", 10),
            width=38,
            show="•"
        )
        confirm_entry.grid(row=5, column=0, pady=(0, 12))
        
        # Полное имя
        tk.Label(
            form_frame,
            text="Ваше полное имя:",
            font=("Arial", 10, "bold")
        ).grid(row=6, column=0, sticky=tk.W, pady=(0, 3))
        
        fullname_entry = tk.Entry(
            form_frame,
            font=("Arial", 10),
            width=38
        )
        fullname_entry.grid(row=7, column=0, pady=(0, 12))
        
        # Название организации
        tk.Label(
            form_frame,
            text="Название вашей организации:",
            font=("Arial", 10, "bold")
        ).grid(row=8, column=0, sticky=tk.W, pady=(0, 3))
        
        company_entry = tk.Entry(
            form_frame,
            font=("Arial", 10),
            width=38
        )
        company_entry.grid(row=9, column=0, pady=(0, 12))
        
        # Номер телефона
        tk.Label(
            form_frame,
            text="Номер телефона организации:",
            font=("Arial", 10, "bold")
        ).grid(row=10, column=0, sticky=tk.W, pady=(0, 3))
        
        phone_entry = tk.Entry(
            form_frame,
            font=("Arial", 10),
            width=38
        )
        phone_entry.grid(row=11, column=0, pady=(0, 12))
        
        # Email
        tk.Label(
            form_frame,
            text="Email организации:",
            font=("Arial", 10, "bold")
        ).grid(row=12, column=0, sticky=tk.W, pady=(0, 3))
        
        email_entry = tk.Entry(
            form_frame,
            font=("Arial", 10),
            width=38
        )
        email_entry.grid(row=13, column=0, pady=(0, 20))
        
        def on_register():
            """Обработка регистрации"""
            username = username_entry.get().strip()
            password = password_entry.get()
            confirm = confirm_entry.get()
            fullname = fullname_entry.get().strip()
            company_name = company_entry.get().strip()
            phone = phone_entry.get().strip()
            email = email_entry.get().strip()
            
            # Валидация
            if not username:
                messagebox.showerror("Ошибка", "Введите логин", parent=dialog)
                return
            
            if len(username) < 3:
                messagebox.showerror("Ошибка", "Логин должен содержать минимум 3 символа", parent=dialog)
                return
            
            if not password:
                messagebox.showerror("Ошибка", "Введите пароль", parent=dialog)
                return
            
            if len(password) < 6:
                messagebox.showerror("Ошибка", "Пароль должен содержать минимум 6 символов", parent=dialog)
                return
            
            if password != confirm:
                messagebox.showerror("Ошибка", "Пароли не совпадают", parent=dialog)
                return
            
            if not fullname:
                messagebox.showerror("Ошибка", "Введите ваше полное имя", parent=dialog)
                return
            
            if not company_name:
                messagebox.showerror("Ошибка", "Введите название организации", parent=dialog)
                return
            
            if not phone:
                messagebox.showerror("Ошибка", "Введите номер телефона", parent=dialog)
                return
            
            if not email:
                messagebox.showerror("Ошибка", "Введите email", parent=dialog)
                return
            
            # Простая валидация email
            if '@' not in email or '.' not in email:
                messagebox.showerror("Ошибка", "Введите корректный email", parent=dialog)
                return
            
            # Попытка регистрации
            success, message = self.auth_manager.register_company(
                company_name=company_name,
                phone=phone,
                email=email,
                admin_username=username,
                admin_password=password,
                admin_fullname=fullname
            )

            if success:
                messagebox.showinfo(
                    "Успех!",
                    f"Организация '{company_name}' успешно зарегистрирована!\n\n"
                    f"Ваши учетные данные для входа:\n"
                    f"Логин: {username}\n"
                    f"Пароль: {password}\n\n"
                    "Сохраните эти данные в надежном месте!",
                    parent=dialog
                )
                self.success = True
                dialog.destroy()
            else:
                messagebox.showerror(
                    "Ошибка",
                    f"Не удалось зарегистрировать организацию.\n\n{message}",
                    parent=dialog
                )
        
        # Кнопки
        button_frame = tk.Frame(form_frame)
        button_frame.grid(row=14, column=0, pady=(10, 0))
        
        register_btn = tk.Button(
            button_frame,
            text="Зарегистрировать",
            font=("Arial", 9, "bold"),
            bg="#3498db",
            fg="white",
            width=18,
            cursor="hand2",
            command=on_register
        )
        register_btn.pack(side=tk.LEFT, padx=4)
        
        cancel_btn = tk.Button(
            button_frame,
            text="Отмена",
            font=("Arial", 9),
            bg="#95a5a6",
            fg="white",
            width=13,
            cursor="hand2",
            command=dialog.destroy
        )
        cancel_btn.pack(side=tk.LEFT, padx=4)
        
        # Применение горячих клавиш ко всем полям ввода
        bind_all_entries(dialog)
        
        # Ожидание закрытия диалога
        dialog.wait_window()
        
        return self.success
