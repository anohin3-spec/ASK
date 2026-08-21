"""
Менеджер управления пользователями
"""
import tkinter as tk
from tkinter import messagebox, ttk, simpledialog
from typing import Optional, Dict, Any, List
from keyboard_shortcuts import bind_all_entries


class UserManager:
    """Управление пользователями в базе данных"""
    
    def __init__(self, db, auth_manager):
        """
        Инициализация менеджера пользователей
        
        Args:
            db: Экземпляр базы данных
            auth_manager: Экземпляр AuthManager
        """
        self.db = db
        self.auth_manager = auth_manager

    def is_superadmin(self) -> bool:
        """Проверка, что текущий пользователь — супер-администратор"""
        current_user = self.auth_manager.get_current_user()
        return bool(current_user and current_user.get('role') == 'superadmin')
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Получить список всех пользователей текущей компании"""
        try:
            if self.is_superadmin():
                # Пробуем с расширенными данными компании (новая схема БД)
                try:
                    result = self.db.client.table('users').select(
                        'id, username, full_name, role, is_active, created_at, '
                        'company_id, companies:company_id(name, phone, email)'
                    ).order('created_at', desc=False).execute()
                except Exception as schema_error:
                    # Для старой схемы БД (без phone/email в companies)
                    result = self.db.client.table('users').select(
                        'id, username, full_name, role, is_active, created_at, '
                        'company_id, companies:company_id(name)'
                    ).order('created_at', desc=False).execute()

                users = result.data if result.data else []
                for user in users:
                    company_data = user.get('companies')
                    if company_data:
                        user['company_name'] = company_data.get('name', '-')
                        user['company_phone'] = company_data.get('phone', '-')
                        user['company_email'] = company_data.get('email', '-')
                    else:
                        user['company_name'] = '-'
                        user['company_phone'] = '-'
                        user['company_email'] = '-'
                return users

            company_id = self.auth_manager.current_company['id']
            result = self.db.client.table('users').select(
                'id, username, full_name, role, is_active, created_at'
            ).eq('company_id', company_id).order('created_at', desc=False).execute()

            return result.data if result.data else []
        except Exception as e:
            print(f"Ошибка при получении пользователей: {e}")
            return []
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получить данные пользователя по ID"""
        try:
            query = self.db.client.table('users').select(
                'id, username, full_name, role, is_active, created_at, company_id'
            ).eq('id', user_id)

            if not self.is_superadmin():
                query = query.eq('company_id', self.auth_manager.current_company['id'])

            result = query.execute()
            
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Ошибка при получении пользователя: {e}")
            return None
    
    def update_user(self, user_id: str, full_name: str, role: str, is_active: bool) -> bool:
        """Обновить данные пользователя"""
        try:
            query = self.db.client.table('users').update({
                'full_name': full_name,
                'role': role,
                'is_active': is_active
            }).eq('id', user_id)

            if not self.is_superadmin():
                query = query.eq('company_id', self.auth_manager.current_company['id'])

            query.execute()
            
            return True
        except Exception as e:
            print(f"Ошибка при обновлении пользователя: {e}")
            return False
    
    def delete_user(self, user_id: str) -> bool:
        """Удалить пользователя"""
        try:
            # Нельзя удалить самого себя
            if user_id == self.auth_manager.current_user['id']:
                return False

            query = self.db.client.table('users').delete().eq('id', user_id)
            if not self.is_superadmin():
                query = query.eq('company_id', self.auth_manager.current_company['id'])

            query.execute()
            return True
        except Exception as e:
            print(f"Ошибка при удалении пользователя: {e}")
            return False


class UserDialog:
    """Диалог добавления/редактирования пользователя"""
    
    def __init__(self, parent, auth_manager, user_id=None):
        """
        Инициализация диалога
        
        Args:
            parent: Родительское окно
            auth_manager: Экземпляр AuthManager
            user_id: ID пользователя для редактирования (None для создания нового)
        """
        self.parent = parent
        self.auth_manager = auth_manager
        self.user_id = user_id
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Редактировать пользователя" if user_id else "Добавить пользователя")
        self.dialog.geometry("450x400")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Центрирование
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (450 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (400 // 2)
        self.dialog.geometry(f"450x400+{x}+{y}")
        
        self.create_widgets()
        
        # Если редактирование - загружаем данные
        if user_id:
            self.load_user_data()
    
    def create_widgets(self):
        """Создание элементов интерфейса"""
        # Заголовок
        title_frame = tk.Frame(self.dialog, bg="#34495e", height=50)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_text = "✏️ Редактировать пользователя" if self.user_id else "➕ Добавить пользователя"
        title_label = tk.Label(
            title_frame,
            text=title_text,
            font=("Arial", 13, "bold"),
            bg="#34495e",
            fg="white"
        )
        title_label.pack(expand=True)
        
        # Форма
        form_frame = tk.Frame(self.dialog, padx=30, pady=20)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Username
        tk.Label(
            form_frame,
            text="Логин (username):",
            font=("Arial", 10)
        ).grid(row=0, column=0, sticky=tk.W, pady=(0, 3))
        
        self.username_entry = tk.Entry(
            form_frame,
            font=("Arial", 10),
            width=35
        )
        self.username_entry.grid(row=1, column=0, pady=(0, 12), sticky=tk.W+tk.E)
        
        if self.user_id:
            self.username_entry.config(state='disabled')  # Нельзя менять логин
        
        # Полное имя
        tk.Label(
            form_frame,
            text="Полное имя:",
            font=("Arial", 10)
        ).grid(row=2, column=0, sticky=tk.W, pady=(0, 3))
        
        self.fullname_entry = tk.Entry(
            form_frame,
            font=("Arial", 10),
            width=35
        )
        self.fullname_entry.grid(row=3, column=0, pady=(0, 12), sticky=tk.W+tk.E)
        
        # Пароль (только для нового пользователя)
        if not self.user_id:
            tk.Label(
                form_frame,
                text="Пароль (минимум 6 символов):",
                font=("Arial", 10)
            ).grid(row=4, column=0, sticky=tk.W, pady=(0, 3))
            
            self.password_entry = tk.Entry(
                form_frame,
                font=("Arial", 10),
                width=35,
                show="•"
            )
            self.password_entry.grid(row=5, column=0, pady=(0, 12), sticky=tk.W+tk.E)
        
        # Роль
        row_offset = 0 if self.user_id else 2
        tk.Label(
            form_frame,
            text="Роль:",
            font=("Arial", 10)
        ).grid(row=6-row_offset, column=0, sticky=tk.W, pady=(0, 3))
        
        self.role_var = tk.StringVar(value="user")
        role_frame = tk.Frame(form_frame)
        role_frame.grid(row=7-row_offset, column=0, pady=(0, 12), sticky=tk.W)
        
        roles = [
            ("Администратор (полный доступ)", "admin"),
            ("Менеджер (управление данными)", "manager"),
            ("Пользователь (базовый доступ)", "user")
        ]
        
        for text, value in roles:
            tk.Radiobutton(
                role_frame,
                text=text,
                variable=self.role_var,
                value=value,
                font=("Arial", 9)
            ).pack(anchor=tk.W, pady=2)
        
        # Активность
        self.active_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            form_frame,
            text="Аккаунт активен",
            variable=self.active_var,
            font=("Arial", 10)
        ).grid(row=8-row_offset, column=0, sticky=tk.W, pady=(5, 15))
        
        # Кнопки
        button_frame = tk.Frame(form_frame)
        button_frame.grid(row=9-row_offset, column=0, pady=(10, 0))
        
        save_btn = tk.Button(
            button_frame,
            text="Сохранить",
            font=("Arial", 9, "bold"),
            bg="#27ae60",
            fg="white",
            width=13,
            cursor="hand2",
            command=self.on_save
        )
        save_btn.pack(side=tk.LEFT, padx=4)
        
        cancel_btn = tk.Button(
            button_frame,
            text="Отмена",
            font=("Arial", 9),
            bg="#95a5a6",
            fg="white",
            width=13,
            cursor="hand2",
            command=self.dialog.destroy
        )
        cancel_btn.pack(side=tk.LEFT, padx=4)
    
    def load_user_data(self):
        """Загрузка данных пользователя для редактирования"""
        try:
            result = self.auth_manager.db.client.table('users').select(
                'username, full_name, role, is_active'
            ).eq('id', self.user_id).execute()
            
            if result.data:
                user = result.data[0]
                self.username_entry.config(state='normal')
                self.username_entry.insert(0, user['username'])
                self.username_entry.config(state='disabled')
                
                self.fullname_entry.insert(0, user.get('full_name', ''))
                self.role_var.set(user.get('role', 'user'))
                self.active_var.set(user.get('is_active', True))
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить данные пользователя: {e}")
    
    def on_save(self):
        """Обработка сохранения"""
        username = self.username_entry.get().strip()
        fullname = self.fullname_entry.get().strip()
        role = self.role_var.get()
        is_active = self.active_var.get()
        
        # Валидация
        if not username:
            messagebox.showerror("Ошибка", "Введите логин", parent=self.dialog)
            return
        
        if not fullname:
            messagebox.showerror("Ошибка", "Введите полное имя", parent=self.dialog)
            return
        
        if self.user_id:
            # Редактирование
            self.result = {
                'id': self.user_id,
                'full_name': fullname,
                'role': role,
                'is_active': is_active
            }
        else:
            # Создание нового
            password = self.password_entry.get()
            
            if not password:
                messagebox.showerror("Ошибка", "Введите пароль", parent=self.dialog)
                return
            
            if len(password) < 6:
                messagebox.showerror(
                    "Ошибка",
                    "Пароль должен содержать минимум 6 символов",
                    parent=self.dialog
                )
                return
            
            self.result = {
                'username': username,
                'password': password,
                'full_name': fullname,
                'role': role,
                'is_active': is_active
            }
        
        self.dialog.destroy()
    
    def show(self):
        """Показать диалог и вернуть результат"""
        # Применение горячих клавиш ко всем полям ввода
        bind_all_entries(self.dialog)
        self.dialog.wait_window()
        return self.result


class ResetPasswordDialog:
    """Диалог сброса пароля администратором"""
    
    def __init__(self, parent, username):
        """
        Инициализация диалога
        
        Args:
            parent: Родительское окно
            username: Имя пользователя
        """
        self.parent = parent
        self.username = username
        self.new_password = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Сброс пароля")
        self.dialog.geometry("420x280")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Центрирование
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (420 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (280 // 2)
        self.dialog.geometry(f"420x280+{x}+{y}")
        
        self.create_widgets()
    
    def create_widgets(self):
        """Создание элементов интерфейса"""
        # Заголовок
        title_frame = tk.Frame(self.dialog, bg="#e74c3c", height=50)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="🔓 Сброс пароля",
            font=("Arial", 13, "bold"),
            bg="#e74c3c",
            fg="white"
        )
        title_label.pack(expand=True)
        
        # Форма
        form_frame = tk.Frame(self.dialog, padx=30, pady=20)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Информация о пользователе
        info_label = tk.Label(
            form_frame,
            text=f"Сброс пароля для пользователя: {self.username}",
            font=("Arial", 10, "bold"),
            fg="#2c3e50"
        )
        info_label.grid(row=0, column=0, pady=(0, 15))
        
        # Новый пароль
        tk.Label(
            form_frame,
            text="Новый временный пароль:",
            font=("Arial", 10)
        ).grid(row=1, column=0, sticky=tk.W, pady=(0, 3))
        
        self.password_entry = tk.Entry(
            form_frame,
            font=("Arial", 10),
            width=32,
            show="•"
        )
        self.password_entry.grid(row=2, column=0, pady=(0, 12))
        self.password_entry.focus()
        
        # Подтверждение пароля
        tk.Label(
            form_frame,
            text="Подтвердите пароль:",
            font=("Arial", 10)
        ).grid(row=3, column=0, sticky=tk.W, pady=(0, 3))
        
        self.confirm_entry = tk.Entry(
            form_frame,
            font=("Arial", 10),
            width=32,
            show="•"
        )
        self.confirm_entry.grid(row=4, column=0, pady=(0, 15))
        
        # Предупреждение
        warning_label = tk.Label(
            form_frame,
            text="⚠️ Сообщите новый пароль пользователю",
            font=("Arial", 8, "italic"),
            fg="#e67e22"
        )
        warning_label.grid(row=5, column=0, pady=(0, 15))
        
        # Кнопки
        button_frame = tk.Frame(form_frame)
        button_frame.grid(row=6, column=0, pady=(5, 0))
        
        reset_btn = tk.Button(
            button_frame,
            text="Сбросить пароль",
            font=("Arial", 9, "bold"),
            bg="#e74c3c",
            fg="white",
            width=15,
            cursor="hand2",
            command=self.on_reset
        )
        reset_btn.pack(side=tk.LEFT, padx=4)
        
        cancel_btn = tk.Button(
            button_frame,
            text="Отмена",
            font=("Arial", 9),
            bg="#95a5a6",
            fg="white",
            width=13,
            cursor="hand2",
            command=self.dialog.destroy
        )
        cancel_btn.pack(side=tk.LEFT, padx=4)
    
    def on_reset(self):
        """Обработка сброса пароля"""
        password = self.password_entry.get()
        confirm = self.confirm_entry.get()
        
        # Валидация
        if not password:
            messagebox.showerror("Ошибка", "Введите новый пароль", parent=self.dialog)
            return
        
        if len(password) < 6:
            messagebox.showerror(
                "Ошибка",
                "Пароль должен содержать минимум 6 символов",
                parent=self.dialog
            )
            return
        
        if password != confirm:
            messagebox.showerror("Ошибка", "Пароли не совпадают", parent=self.dialog)
            return
        
        self.new_password = password
        self.dialog.destroy()
    
    def show(self):
        """Показать диалог и вернуть новый пароль"""
        # Применение горячих клавиш ко всем полям ввода
        bind_all_entries(self.dialog)
        self.dialog.wait_window()
        return self.new_password
