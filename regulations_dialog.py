"""
Диалоговое окно для управления регламентами ТО
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import tempfile
import urllib.request
from regulations_manager import RegulationsManager


class RegulationsDialog:
    """Диалог управления регламентами технического обслуживания"""
    
    def __init__(self, parent, db, user_id=None):
        """
        Инициализация диалога
        
        Args:
            parent: Родительское окно
            db: Экземпляр базы данных
            user_id: ID текущего пользователя
        """
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Регламенты технического обслуживания")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Центрирование окна
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (400 // 2)
        self.dialog.geometry(f"600x400+{x}+{y}")
        
        # Инициализация менеджера регламентов
        self.regulations_manager = RegulationsManager(db)
        self.user_id = user_id
        
        self.create_widgets()
        self.refresh_list()
    
    def create_widgets(self):
        """Создание виджетов диалога"""
        # Заголовок
        header = ttk.Label(
            self.dialog,
            text="Управление регламентами ТО по типам техники",
            font=('Arial', 11, 'bold')
        )
        header.pack(pady=10)
        
        # Фрейм с таблицей
        list_frame = ttk.Frame(self.dialog)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Таблица регламентов
        columns = ('Тип техники', 'Статус')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        
        self.tree.heading('Тип техники', text='Тип техники')
        self.tree.heading('Статус', text='Статус')
        
        self.tree.column('Тип техники', width=350)
        self.tree.column('Статус', width=150)
        
        # Скроллбар
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Привязка двойного клика
        self.tree.bind('<Double-1>', lambda e: self.open_regulation())
        
        # Панель кнопок
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=10)
        
        ttk.Button(
            button_frame,
            text="Добавить файл",
            command=self.add_regulation
        ).pack(side='left', padx=5)
        
        ttk.Button(
            button_frame,
            text="Открыть",
            command=self.open_regulation
        ).pack(side='left', padx=5)
        
        ttk.Button(
            button_frame,
            text="Удалить",
            command=self.delete_regulation
        ).pack(side='left', padx=5)
        
        ttk.Button(
            button_frame,
            text="Закрыть",
            command=self.dialog.destroy
        ).pack(side='left', padx=5)
        
        # Подсказка
        hint = ttk.Label(
            self.dialog,
            text="Совет: Дважды кликните на тип техники для открытия регламента",
            font=('Arial', 9),
            foreground='gray'
        )
        hint.pack(pady=5)
    
    def refresh_list(self):
        """Обновление списка регламентов"""
        # Очищаем таблицу
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Получаем статус всех регламентов
        regulations_status = self.regulations_manager.get_all_regulations()
        
        # Заполняем таблицу
        for eq_type, has_file in regulations_status.items():
            status = "Загружен" if has_file else "Не загружен"
            tag = 'has_file' if has_file else 'no_file'
            
            self.tree.insert('', 'end', values=(eq_type, status), tags=(tag,))
        
        # Раскраска строк
        self.tree.tag_configure('has_file', background='#ccffcc')
        self.tree.tag_configure('no_file', background='#ffeecc')
    
    def add_regulation(self):
        """Добавление файла регламента"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning(
                "Предупреждение",
                "Выберите тип техники для добавления регламента"
            )
            return
        
        item = self.tree.item(selection[0])
        equipment_type = item['values'][0]
        
        # Проверка наличия существующего файла
        if self.regulations_manager.has_regulation(equipment_type):
            if not messagebox.askyesno(
                "Подтверждение",
                f"Для '{equipment_type}' уже загружен регламент.\n"
                "Заменить его новым файлом?"
            ):
                return
        
        # Выбор файла
        file_path = filedialog.askopenfilename(
            title=f"Выберите файл регламента для {equipment_type}",
            filetypes=[
                ("PDF файлы", "*.pdf"),
                ("Word документы", "*.doc *.docx"),
                ("Excel файлы", "*.xls *.xlsx"),
                ("Изображения", "*.png *.jpg *.jpeg"),
                ("Все файлы", "*.*")
            ]
        )
        
        if file_path:
            if self.regulations_manager.add_regulation(equipment_type, file_path, self.user_id):
                messagebox.showinfo(
                    "Успех",
                    f"Регламент для '{equipment_type}' успешно добавлен!"
                )
                self.refresh_list()
            else:
                messagebox.showerror(
                    "Ошибка",
                    "Не удалось добавить файл регламента.\n\n"
                    "Проверьте:\n"
                    "• Выполнена ли SQL миграция (migration_add_regulations.sql)\n"
                    "• Создан ли bucket 'regulations' в Supabase Storage\n"
                    "• Настроены ли Storage политики"
                )
    
    def open_regulation(self):
        """Открытие файла регламента"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning(
                "Предупреждение",
                "Выберите тип техники"
            )
            return
        
        item = self.tree.item(selection[0])
        equipment_type = item['values'][0]
        
        # Получаем путь к файлу
        file_path = self.regulations_manager.get_regulation_path(equipment_type)
        
        if file_path:
            try:
                # Проверка на облачный путь
                if file_path.startswith('supabase://'):
                    # Получаем URL для скачивания
                    url = self.regulations_manager.resolve_regulation_url(file_path)
                    
                    if url:
                        # Получаем расширение файла
                        file_ext = file_path.split('.')[-1] if '.' in file_path else 'pdf'
                        
                        # Скачиваем файл во временную директорию
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_ext}')
                        temp_path = temp_file.name
                        temp_file.close()
                        
                        urllib.request.urlretrieve(url, temp_path)
                        
                        # Открываем файл
                        os.startfile(temp_path)
                    else:
                        messagebox.showerror(
                            "Ошибка",
                            f"Не удалось получить доступ к файлу"
                        )
                else:
                    # Локальный файл
                    if os.path.exists(file_path):
                        os.startfile(file_path)
                    else:
                        messagebox.showerror(
                            "Ошибка",
                            f"Файл не найден:\n{file_path}"
                        )
            except Exception as e:
                messagebox.showerror(
                    "Ошибка",
                    f"Не удалось открыть файл:\n{str(e)}"
                )
        else:
            messagebox.showinfo(
                "Информация",
                f"Регламент для '{equipment_type}' не загружен.\n"
                "Нажмите 'Добавить файл' для загрузки."
            )
    
    def delete_regulation(self):
        """Удаление файла регламента"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning(
                "Предупреждение",
                "Выберите тип техники"
            )
            return
        
        item = self.tree.item(selection[0])
        equipment_type = item['values'][0]
        
        # Проверка наличия файла
        if not self.regulations_manager.has_regulation(equipment_type):
            messagebox.showinfo(
                "Информация",
                f"Для '{equipment_type}' нет загруженного регламента"
            )
            return
        
        # Подтверждение удаления
        if messagebox.askyesno(
            "Подтверждение",
            f"Удалить регламент для '{equipment_type}'?"
        ):
            if self.regulations_manager.delete_regulation(equipment_type):
                messagebox.showinfo(
                    "Успех",
                    "Регламент успешно удален"
                )
                self.refresh_list()
            else:
                messagebox.showerror(
                    "Ошибка",
                    "Не удалось удалить регламент"
                )
