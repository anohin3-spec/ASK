"""
Главное приложение для учета технического обслуживания техники
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timezone
import os
import sys
import tempfile
import atexit
import re
try:
    from tksheet import Sheet
except Exception:
    Sheet = None
import database as db_config
from database import Database
from ui_display import (
    enable_windows_per_monitor_dpi,
    apply_tk_display_scaling,
    configure_global_ui_style,
    load_window_state,
    save_window_state,
    ui_font,
)
from auth_manager import AuthManager
from login_dialog import LoginDialog, ChangePasswordDialog
from equipment_manager import EquipmentManager, EquipmentDialog
from driver_manager import DriverManager, DriverDialog
from driver_shifts_dialog import DriverShiftsDialog
from maintenance_manager import MaintenanceManager, MaintenanceDialog
from issue_manager import IssueManager, IssueDialog, ResolveIssueDialog
from export_manager import ExportManager
from settings_dialog import SettingsDialog
from user_manager import UserManager, UserDialog, ResetPasswordDialog
from regulations_dialog import RegulationsDialog


class MaintenanceApp:
    def __init__(self, root, auth_manager):
        _startup_log("MaintenanceApp.__init__ start")
        self.root = root
        self.root.title("Maintenance Helper")
        
        # Инициализация базы данных и авторизации
        self.db = auth_manager.db
        self.auth_manager = auth_manager
        self.switch_user_requested = False
        self.is_superadmin = bool(
            self.auth_manager.get_current_user() and
            self.auth_manager.get_current_user().get('role') == 'superadmin'
        )
        
        # Обновление заголовка окна с информацией о пользователе и компании
        user = self.auth_manager.get_current_user()
        company = self.auth_manager.get_current_company()
        self.root.title(f"Maintenance Helper - {company['name']} [{user['full_name']}]")
        
        # Создание менеджеров
        self.equipment_manager = EquipmentManager(self.db)
        self.driver_manager = DriverManager(self.db)
        self.maintenance_manager = MaintenanceManager(self.db)
        self.issue_manager = IssueManager(self.db)
        self.export_manager = ExportManager(self.db)
        self.user_manager = UserManager(self.db, self.auth_manager)
        self.equipment_tree = None
        self.equipment_sheet_preview = None
        self._equipment_preview_row_ids = []
        self.drivers_tree = None
        self.drivers_sheet_preview = None
        self._drivers_preview_row_ids = []
        self.drivers_tab = None
        self.use_drivers_sheet = False
        self.maintenance_current_equipment_id = None
        self.issues_closed_current_equipment_id = None
        
        # Создание главного меню
        _startup_log("MaintenanceApp: create_menu")
        self.create_menu()
        
        # Создание вкладок
        _startup_log("MaintenanceApp: create notebook")
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        self.notebook.bind('<<NotebookTabChanged>>', self.on_notebook_tab_changed, add='+')
        
        # Для superadmin показываем только вкладку пользователей/клиентов
        if self.is_superadmin:
            _startup_log("MaintenanceApp: superadmin mode")
            self.create_users_tab()
        else:
            # Создание рабочих вкладок
            if Sheet is not None:
                _startup_log("MaintenanceApp: create equipment sheet preview tab")
                self.create_equipment_sheet_preview_tab()
            else:
                _startup_log("MaintenanceApp: create equipment tree tab")
                self.create_equipment_tab()
            _startup_log("MaintenanceApp: create drivers tab")
            self.create_drivers_tab()
            _startup_log("MaintenanceApp: create maintenance tab")
            self.create_maintenance_tab()
            _startup_log("MaintenanceApp: create issues tab")
            self.create_issues_tab()

            # Вкладка управления пользователями (только для админов)
            if self.auth_manager.has_permission('admin'):
                _startup_log("MaintenanceApp: create users tab (admin)")
                self.create_users_tab()

            # Загрузка сохраненных ширин столбцов
            _startup_log("MaintenanceApp: load column widths")
            self.load_all_column_widths()
        
        # Обновление данных при запуске (двойной refresh техники не нужен — см. refresh_all_tabs)
        _startup_log("MaintenanceApp: refresh_all_tabs start")
        self.refresh_all_tabs()
        _startup_log("MaintenanceApp.__init__ done")
    
    def create_menu(self):
        """Создание главного меню"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Меню "Файл"
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Экспорт в Excel", command=self.export_to_excel)
        file_menu.add_command(label="Экспорт списка техники", command=self.export_equipment_only)
        file_menu.add_command(label="Экспорт истории ТО", command=self.export_maintenance_only)
        file_menu.add_command(label="Экспорт неисправностей", command=self.export_issues_only)
        file_menu.add_separator()
        file_menu.add_command(
            label="Очистить неиспользуемые файлы в Storage…",
            command=self.cleanup_orphan_storage,
        )
        file_menu.add_separator()
        file_menu.add_command(label="Настройки", command=self.show_settings)
        file_menu.add_command(label="Сменить пароль", command=self.change_password)
        file_menu.add_separator()
        file_menu.add_command(label="Сменить пользователя", command=self.switch_user)
        file_menu.add_command(label="Выход", command=self.on_exit)
        
        # Меню "Справка"
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="О программе", command=self.show_about)
    
    def create_equipment_tab(self):
        """Создание вкладки управления техникой"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Техника")
        
        # Панель инструментов
        toolbar = ttk.Frame(tab)
        toolbar.pack(side='top', fill='x', padx=5, pady=5)
        
        ttk.Button(toolbar, text="Добавить", command=self.add_equipment).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Редактировать", command=self.edit_equipment).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Удалить", command=self.delete_equipment).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Обновить", command=self.refresh_equipment_views).pack(side='left', padx=2)
        
        # Таблица техники
        columns = ('ID', 'Название', 'VIN', 'СТС', 'Номер', 'Водители', 'Неисправности', 'Тип учета', 
                   'Последнее ТО', 'Текущее значение', 'Следующее ТО', 'Статус',
                   'Страховка', 'Диагностическая карта', 'Пропуск МКАД', 'Сервис', 'KMU')
        self.equipment_columns = columns
        self._equipment_row_ids = []
        # Стабильный режим отображения (Treeview)
        self.use_equipment_sheet = False
        
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill='both', expand=True, padx=5, pady=5)

        if self.use_equipment_sheet:
            self.equipment_tree = Sheet(
                tree_frame,
                headers=list(columns),
                show_row_index=False,
                show_top_left=False,
                width=1200,
                height=600
            )
            self.equipment_tree.enable_bindings()
            self.equipment_tree.pack(fill='both', expand=True)
            self.equipment_tree.bind('<Double-1>', lambda e: self.edit_equipment())
            self.equipment_tree.bind('<Button-3>', self.show_equipment_context_menu)
            return
        
        self.equipment_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)
        
        # Настройка колонок
        self.equipment_tree.heading('ID', text='ID')
        self.equipment_tree.heading('Название', text='Название техники')
        self.equipment_tree.heading('VIN', text='VIN')
        self.equipment_tree.heading('СТС', text='СТС')
        self.equipment_tree.heading('Номер', text='Номер')
        self.equipment_tree.heading('Водители', text='Водители')
        self.equipment_tree.heading('Неисправности', text='Открытые неисправности')
        self.equipment_tree.heading('Тип учета', text='Тип учета')
        self.equipment_tree.heading('Последнее ТО', text='Последнее ТО')
        self.equipment_tree.heading('Текущее значение', text='Пробег/моточасы')
        self.equipment_tree.heading('Следующее ТО', text='Следующее ТО')
        self.equipment_tree.heading('Статус', text='Статус')
        self.equipment_tree.heading('Страховка', text='Страховка')
        self.equipment_tree.heading('Диагностическая карта', text='Диагностическая карта')
        self.equipment_tree.heading('Пропуск МКАД', text='Пропуск МКАД')
        self.equipment_tree.heading('Сервис', text='Сервис')
        self.equipment_tree.heading('KMU', text='КМУ (м/ч)')
        
        self.equipment_tree.column('ID', width=40)
        self.equipment_tree.column('Название', width=150)
        self.equipment_tree.column('VIN', width=120)
        self.equipment_tree.column('СТС', width=140)
        self.equipment_tree.column('Номер', width=100)
        self.equipment_tree.column('Водители', width=180)
        self.equipment_tree.column('Неисправности', width=200)
        self.equipment_tree.column('Тип учета', width=100)
        self.equipment_tree.column('Последнее ТО', width=100)
        self.equipment_tree.column('Текущее значение', width=120)
        self.equipment_tree.column('Следующее ТО', width=100)
        self.equipment_tree.column('Статус', width=150)
        self.equipment_tree.column('Страховка', width=160)
        self.equipment_tree.column('Диагностическая карта', width=180)
        self.equipment_tree.column('Пропуск МКАД', width=100)
        self.equipment_tree.column('Сервис', width=120)
        self.equipment_tree.column('KMU', width=135)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.equipment_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.equipment_tree.xview)
        self.equipment_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.equipment_tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')
        
        # Двойной клик для редактирования
        self.equipment_tree.bind('<Double-1>', lambda e: self.edit_equipment())
        
        # Контекстное меню по правой кнопке мыши
        self.equipment_tree.bind('<Button-3>', self.show_equipment_context_menu)

        # Drag & Drop для перемещения строк
        self._drag_item = None
        self._drag_changed = False
        self._is_dragging_equipment = False
        self._last_drag_target = None
        self.equipment_tree.bind('<ButtonPress-1>', self.start_equipment_drag, add='+')
        self.equipment_tree.bind('<B1-Motion>', self.on_equipment_drag, add='+')
        self.equipment_tree.bind('<ButtonRelease-1>', self.finish_equipment_drag, add='+')
        
        # Сохранение ширины столбцов при изменении
        self.equipment_tree.bind('<ButtonRelease-1>', self.save_column_widths, add='+')
    
    def create_drivers_tab(self):
        """Создание вкладки управления водителями"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Водители")
        self.drivers_tab = tab
        
        # Панель инструментов
        toolbar = ttk.Frame(tab)
        toolbar.pack(side='top', fill='x', padx=5, pady=5)
        
        ttk.Button(toolbar, text="Добавить", command=self.add_driver).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Редактировать", command=self.edit_driver).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Удалить", command=self.delete_driver).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Обновить", command=self.refresh_drivers_list).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Управление водителями", command=self.manage_driver_shifts_from_drivers_tab).pack(side='left', padx=10)
        columns = ('ID', 'Имя', 'Телефон', 'Топливная карта', 'Техника')
        self.drivers_tree = None
        self.drivers_sheet_preview = None
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill='both', expand=True, padx=5, pady=5)
        self.drivers_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)
        self.drivers_tree.heading('ID', text='ID')
        self.drivers_tree.heading('Имя', text='Имя водителя')
        self.drivers_tree.heading('Телефон', text='Телефон')
        self.drivers_tree.heading('Топливная карта', text='Топливная карта')
        self.drivers_tree.heading('Техника', text='Закрепленная техника')
        self.drivers_tree.column('ID', width=50)
        self.drivers_tree.column('Имя', width=220, stretch=False)
        self.drivers_tree.column('Телефон', width=150, stretch=False)
        self.drivers_tree.column('Топливная карта', width=180, stretch=False)
        self.drivers_tree.column('Техника', width=460, stretch=False)
        self.drivers_tree.column('ID', stretch=False)
        v_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.drivers_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.drivers_tree.xview)
        self.drivers_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        self.drivers_tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')
        self.drivers_tree.bind('<Double-1>', lambda e: self.edit_driver())
        self._bind_treeview_width_persistence(self.drivers_tree, 'drivers_column_widths')

    def create_equipment_sheet_preview_tab(self):
        """Основная вкладка техники с поклеточной подсветкой."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Техника")

        toolbar = ttk.Frame(tab)
        toolbar.pack(side='top', fill='x', padx=5, pady=5)
        ttk.Button(toolbar, text="Добавить", command=self.add_equipment).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Редактировать", command=self.edit_equipment).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Удалить", command=self.delete_equipment).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Обновить", command=self.refresh_all_tabs).pack(side='left', padx=2)

        columns = [
            'ID', 'Название', 'VIN', 'СТС', 'Номер', 'Водители', 'Неисправности', 'Тип учета',
            'Последнее ТО', 'Текущее значение', 'Следующее ТО', 'Статус',
            'Страховка', 'Диагностическая карта', 'Пропуск МКАД', 'Сервис', 'КМУ (м/ч)'
        ]
        self.equipment_columns = tuple(columns)

        self.equipment_sheet_preview = Sheet(
            tab,
            headers=columns,
            show_row_index=False,
            show_top_left=False,
            all_columns_displayed=True,
            all_rows_displayed=True,
            width=1200,
            height=620,
            # Меньше задержка отложенного refresh (по умолчанию 16 ms — заметно мерцает после select_cell)
            after_redraw_time_ms=1,
        )
        self.equipment_sheet_preview.enable_bindings(menu=False)
        # В tksheet при enable_bindings("all", menu=False) флаг rc_popup_menus_enabled всё равно
        # остаётся True — справа всплывает встроенное меню таблицы (Delete rows, Sort…).
        self.equipment_sheet_preview.disable_bindings("right_click_popup_menu")
        try:
            self.equipment_sheet_preview.readonly("all")
        except Exception:
            pass
        self.equipment_sheet_preview.pack(fill='both', expand=True, padx=5, pady=5)
        # В tksheet 7.x клик идёт на внутренний canvas (MT), а не на фрейм Sheet — обычный bind('<Button-1>') не срабатывает.
        # bind('<ButtonPress-1>') задаёт extra_b1_press_func и вызывается ПОСЛЕ select_cell внутри таблицы — здесь переключаем на выделение строки.
        self.equipment_sheet_preview.bind('<ButtonPress-1>', self._on_equipment_sheet_b1_extra)
        self.equipment_sheet_preview.bind('<Double-1>', self.on_equipment_preview_double_click, add='+')
        self.equipment_sheet_preview.bind('<Button-3>', self.show_equipment_context_menu, add='+')
        self.equipment_sheet_preview.bind('<ButtonRelease-1>', self.save_column_widths, add='+')
    
    def create_maintenance_tab(self):
        """Создание вкладки истории ТО"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="История ТО")
        
        # Панель инструментов
        toolbar = ttk.Frame(tab)
        toolbar.pack(side='top', fill='x', padx=5, pady=5)
        
        ttk.Button(toolbar, text="Добавить ТО", command=self.add_maintenance).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Редактировать ТО", command=self.edit_maintenance).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Обновить", command=self.refresh_maintenance_list).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Открыть счет", command=self.open_invoice).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Регламенты", command=self.open_regulations).pack(side='left', padx=2)
        ttk.Label(toolbar, text="Поиск:").pack(side='left', padx=(14, 4))
        self.maintenance_search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=self.maintenance_search_var, width=26)
        search_entry.pack(side='left', padx=(0, 8))
        search_entry.bind('<KeyRelease>', lambda e: self.refresh_maintenance_list())
        self.maintenance_only_with_records = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            toolbar,
            text="Только с записями",
            variable=self.maintenance_only_with_records,
            command=self.refresh_maintenance_list
        ).pack(side='left')
        self.maintenance_breadcrumb = ttk.Label(tab, text="История ТО", foreground='#1a73e8', cursor='hand2')
        self.maintenance_breadcrumb.pack(anchor='w', padx=8, pady=(0, 4))
        self.maintenance_breadcrumb.bind('<Button-1>', lambda e: self.back_to_maintenance_equipment_list())
        
        # Таблица истории ТО (папочный вид)
        columns = ('Номер', 'Счетчик', 'Значение', 'Дата', 'Комментарий', 'Счет', 'Записей', '_ID', '_INVOICE_PATH')
        
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.maintenance_tree = ttk.Treeview(tree_frame, columns=columns, show='tree headings', height=20)

        self.maintenance_tree.heading('#0', text='Название техники')
        self.maintenance_tree.heading('Номер', text='Номер')
        self.maintenance_tree.heading('Счетчик', text='Счетчик')
        self.maintenance_tree.heading('Значение', text='Пробег/моточасы')
        self.maintenance_tree.heading('Дата', text='Дата ТО')
        self.maintenance_tree.heading('Комментарий', text='Комментарий')
        self.maintenance_tree.heading('Счет', text='Счет')
        self.maintenance_tree.heading('Записей', text='Записей')

        self.maintenance_tree.column('#0', width=220, stretch=False)
        self.maintenance_tree.column('Номер', width=100, stretch=False)
        self.maintenance_tree.column('Счетчик', width=110, stretch=False)
        self.maintenance_tree.column('Значение', width=120, stretch=False)
        self.maintenance_tree.column('Дата', width=150, stretch=False)
        self.maintenance_tree.column('Комментарий', width=400, stretch=False)
        self.maintenance_tree.column('Счет', width=100, stretch=False)
        self.maintenance_tree.column('Записей', width=110, stretch=False)
        self.maintenance_tree.column('_ID', width=0, stretch=False)
        self.maintenance_tree.column('_INVOICE_PATH', width=0, stretch=False)
        
        v_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.maintenance_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.maintenance_tree.xview)
        self.maintenance_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.maintenance_tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')

        # Двойной клик по папке техники или записи
        self.maintenance_tree.bind('<Double-1>', self.on_maintenance_double_click)
        self.maintenance_tree.bind('<BackSpace>', lambda e: self.back_to_maintenance_equipment_list() if self.maintenance_current_equipment_id else None)
        self.maintenance_tree.bind('<Button-3>', self.show_maintenance_context_menu)
        self._bind_treeview_width_persistence(self.maintenance_tree, 'maintenance_column_widths', include_tree=True)
    
    def create_issues_tab(self):
        """Создание вкладки неисправностей"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Неисправности")
        
        # Панель инструментов
        toolbar = ttk.Frame(tab)
        toolbar.pack(side='top', fill='x', padx=5, pady=5)
        
        ttk.Button(toolbar, text="Добавить", command=self.add_issue).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Редактировать", command=self.edit_issue).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Закрыть", command=self.resolve_issue).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Открыть счет решения", command=self.open_issue_resolution_invoice).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Удалить", command=self.delete_issue).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Обновить", command=self.refresh_issues_list).pack(side='left', padx=2)
        
        ttk.Label(toolbar, text="Фильтр:").pack(side='left', padx=(20, 5))
        self.issues_filter = ttk.Combobox(toolbar, values=['Все', 'Открытые', 'Закрытые'], 
                                          state='readonly', width=15)
        self.issues_filter.set('Открытые')
        self.issues_filter.pack(side='left', padx=2)
        self.issues_filter.bind('<<ComboboxSelected>>', self.on_issues_filter_changed)
        self.issues_breadcrumb = ttk.Label(tab, text="Неисправности", foreground='#1a73e8', cursor='hand2')
        self.issues_breadcrumb.pack(anchor='w', padx=8, pady=(0, 4))
        self.issues_breadcrumb.bind('<Button-1>', lambda e: self.back_to_closed_issues_equipment_list())
        
        # Таблица неисправностей
        columns = (
            'ID', 'Техника', 'Номер', 'Водитель', 'Описание', 'Статус',
            'Дата сообщения', 'Дата решения', 'Решение', 'Счет', '_RESOLUTION_INVOICE_PATH', '_ISSUE_ID', '_TYPE', '_EID'
        )
        
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.issues_tree = ttk.Treeview(tree_frame, columns=columns, show='tree headings', height=20)
        self.issues_tree.heading('#0', text='Папка')
        
        self.issues_tree.heading('ID', text='ID')
        self.issues_tree.heading('Техника', text='Техника')
        self.issues_tree.heading('Номер', text='Номер')
        self.issues_tree.heading('Водитель', text='Водитель')
        self.issues_tree.heading('Описание', text='Описание неисправности')
        self.issues_tree.heading('Статус', text='Статус')
        self.issues_tree.heading('Дата сообщения', text='Дата сообщения')
        self.issues_tree.heading('Дата решения', text='Дата решения')
        self.issues_tree.heading('Решение', text='Как устранено')
        self.issues_tree.heading('Счет', text='Счет')
        
        self.issues_tree.column('#0', width=180, stretch=False)
        self.issues_tree.column('ID', width=50, stretch=False)
        self.issues_tree.column('Техника', width=150, stretch=False)
        self.issues_tree.column('Номер', width=100, stretch=False)
        self.issues_tree.column('Водитель', width=150, stretch=False)
        self.issues_tree.column('Описание', width=350, stretch=False)
        self.issues_tree.column('Статус', width=100, stretch=False)
        self.issues_tree.column('Дата сообщения', width=130, stretch=False)
        self.issues_tree.column('Дата решения', width=130, stretch=False)
        self.issues_tree.column('Решение', width=260, stretch=False)
        self.issues_tree.column('Счет', width=80, stretch=False)
        self.issues_tree.column('_RESOLUTION_INVOICE_PATH', width=0, stretch=False)
        self.issues_tree.column('_ISSUE_ID', width=0, stretch=False)
        self.issues_tree.column('_TYPE', width=0, stretch=False)
        self.issues_tree.column('_EID', width=0, stretch=False)
        
        v_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.issues_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.issues_tree.xview)
        self.issues_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.issues_tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')
        self.issues_tree.bind('<Double-1>', self.on_issues_double_click)
        self.issues_tree.bind('<BackSpace>', lambda e: self.back_to_closed_issues_equipment_list() if self.issues_closed_current_equipment_id else None)
        self.issues_tree.bind('<Button-3>', self.show_issues_context_menu)
        self._bind_treeview_width_persistence(self.issues_tree, 'issues_column_widths', include_tree=True)
    
    def create_reports_tab(self):
        """Создание вкладки отчетов"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Отчеты и статистика")
        
        # Основная информация
        info_frame = ttk.LabelFrame(tab, text="Общая информация", padding=10)
        info_frame.pack(fill='x', padx=10, pady=10)
        
        self.stats_labels = {}
        stats_data = [
            ('total_equipment', 'Всего техники:'),
            ('total_drivers', 'Всего водителей:'),
            ('total_maintenance', 'Всего ТО:'),
            ('open_issues', 'Открытых неисправностей:'),
            ('maintenance_needed', 'Требуется ТО:'),
        ]
        
        for i, (key, label) in enumerate(stats_data):
            card = ttk.Frame(info_frame, padding=(10, 6))
            card.grid(row=i // 3, column=i % 3, sticky='nsew', padx=6, pady=6)
            ttk.Label(card, text=label, font=ui_font(10)).pack(anchor='w')
            self.stats_labels[key] = ttk.Label(card, text='0', font=ui_font(13, 'bold'))
            self.stats_labels[key].pack(anchor='w', pady=(2, 0))
        for col in range(3):
            info_frame.columnconfigure(col, weight=1)
        
        # Кнопки экспорта
        export_frame = ttk.LabelFrame(tab, text="Экспорт данных", padding=10)
        export_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(export_frame, text="Экспорт всех данных в Excel", 
                  command=self.export_to_excel).pack(pady=5, fill='x')
        ttk.Button(export_frame, text="Экспорт списка техники", 
                  command=self.export_equipment_only).pack(pady=5, fill='x')
        ttk.Button(export_frame, text="Экспорт истории ТО", 
                  command=self.export_maintenance_only).pack(pady=5, fill='x')
        ttk.Button(export_frame, text="Экспорт неисправностей", 
                  command=self.export_issues_only).pack(pady=5, fill='x')
        
        self.update_statistics()
    
    def create_users_tab(self):
        """Создание вкладки управления пользователями (только для админов)"""
        tab = ttk.Frame(self.notebook)
        tab_title = "Все пользователи" if self.is_superadmin else "Пользователи"
        self.notebook.add(tab, text=tab_title)
        
        # Панель инструментов
        toolbar = ttk.Frame(tab)
        toolbar.pack(side='top', fill='x', padx=5, pady=5)
        
        if not self.is_superadmin:
            ttk.Button(toolbar, text="Добавить пользователя", command=self.add_user).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Редактировать", command=self.edit_user).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Сбросить пароль", command=self.reset_user_password).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Удалить", command=self.delete_user).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Обновить", command=self.refresh_users_list).pack(side='left', padx=2)
        
        # Таблица пользователей
        if self.is_superadmin:
            columns = ('ID', 'Компания', 'Телефон', 'Email', 'Логин', 'Полное имя', 'Роль', 'Статус', 'Дата создания')
        else:
            columns = ('ID', 'Логин', 'Полное имя', 'Роль', 'Статус', 'Дата создания')
        
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.users_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)
        
        # Настройка столбцов
        self.users_tree.heading('ID', text='ID')
        if self.is_superadmin:
            self.users_tree.heading('Компания', text='Компания')
            self.users_tree.heading('Телефон', text='Телефон')
            self.users_tree.heading('Email', text='Email')
        self.users_tree.heading('Логин', text='Логин')
        self.users_tree.heading('Полное имя', text='Полное имя')
        self.users_tree.heading('Роль', text='Роль')
        self.users_tree.heading('Статус', text='Статус')
        self.users_tree.heading('Дата создания', text='Дата создания')
        
        self.users_tree.column('ID', width=0, stretch=False)  # Скрываем ID
        if self.is_superadmin:
            self.users_tree.column('Компания', width=180, stretch=False)
            self.users_tree.column('Телефон', width=140, stretch=False)
            self.users_tree.column('Email', width=200, stretch=False)
        self.users_tree.column('Логин', width=150, stretch=False)
        self.users_tree.column('Полное имя', width=200, stretch=False)
        self.users_tree.column('Роль', width=120, stretch=False)
        self.users_tree.column('Статус', width=100, stretch=False)
        self.users_tree.column('Дата создания', width=150, stretch=False)
        
        # Scrollbar
        v_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.users_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.users_tree.xview)
        self.users_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.users_tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')
        
        # Двойной клик для редактирования
        self.users_tree.bind('<Double-1>', lambda e: self.edit_user())
        self._bind_treeview_width_persistence(self.users_tree, 'users_column_widths')
    
    # ===== Методы для работы с техникой =====
    
    def refresh_equipment_list(self):
        """Обновление списка техники"""
        if self.equipment_tree is None:
            return
        if getattr(self, 'use_equipment_sheet', False):
            self.equipment_tree.set_sheet_data([])
            self._equipment_row_ids = []
            try:
                self.equipment_tree.dehighlight("all")
            except Exception:
                pass
            sheet_data = []
        else:
            for item in self.equipment_tree.get_children():
                self.equipment_tree.delete(item)
        
        equipment_list = self.db.get_all_equipment()
        current_date = datetime.now()
        batch_ok = False
        try:
            issues_by_eq = self.db.get_open_issues_grouped_by_equipment_id()
            driver_by_eq = self.db.get_active_driver_name_by_equipment_id()
            batch_ok = True
        except Exception:
            issues_by_eq = {}
            driver_by_eq = {}
        
        for idx, eq in enumerate(equipment_list):
            measurement_type = 'Пробег' if eq['measurement_type'] == 'mileage' else 'Моточасы'
            eid = str(eq['id'])
            
            if batch_ok:
                drivers_str = driver_by_eq.get(eid, '-')
                open_issues = issues_by_eq.get(eid, [])
            else:
                try:
                    drivers = self.db.get_all_drivers_for_equipment_with_shifts(eq['id'])
                    if drivers:
                        active_driver = next((d for d in drivers if d.get('is_active', False)), None)
                        drivers_str = active_driver['name'] if active_driver else '-'
                    else:
                        drivers_str = '-'
                except Exception:
                    drivers = self.db.get_equipment_drivers(eq['id'])
                    drivers_str = drivers[0]['name'] if drivers else '-'
                open_issues = self.db.get_equipment_issues(eq['id'], status='open')
            if open_issues:
                # Показываем все неисправности через точку с запятой
                issues_list = []
                for issue in open_issues:
                    desc = issue['description'][:30] + ('...' if len(issue['description']) > 30 else '')
                    issues_list.append(desc)
                issues_str = f"[!] {len(open_issues)}: " + '; '.join(issues_list)
            else:
                issues_str = '-'
            
            # Расчет следующего ТО
            current_month = datetime.now().month
            # Зима: ноябрь-февраль (11,12,1,2), Лето: март-октябрь (3-10)
            is_winter = current_month in [11, 12, 1, 2]
            interval = eq['maintenance_interval_winter'] if is_winter else eq['maintenance_interval_summer']
            next_maintenance = eq['last_maintenance'] + interval
            
            # Определение статуса ТО
            remaining = next_maintenance - eq['current_value']
            severity = 0  # 0=green, 1=yellow, 2=red
            
            # Пороги для предупреждений: 500 км или 50 моточасов
            warning_threshold = 50 if eq['measurement_type'] == 'motohours' else 500
            critical_threshold = warning_threshold // 2
            
            if remaining <= 0:
                status = "[!] ТРЕБУЕТСЯ ТО!"
                severity = max(severity, 2)
                maintenance_level = 2
            elif remaining <= critical_threshold:
                status = f"[КРИТ] Очень скоро ТО ({remaining})"
                severity = max(severity, 2)
                maintenance_level = 2
            elif remaining <= warning_threshold:
                status = f"[ВНИМ] Скоро ТО ({remaining})"
                severity = max(severity, 1)
                maintenance_level = 1
            else:
                status = f"[OK] ({remaining})"
                maintenance_level = 0
            
            # Проверка страховки
            insurance_level = None
            if eq['insurance_date']:
                try:
                    insurance_date = datetime.strptime(eq['insurance_date'], '%d.%m.%Y')
                    days_left = (insurance_date - current_date).days
                    insurance_level = self._severity_for_days(days_left)
                    severity = max(severity, insurance_level)
                except:
                    pass
            
            # Проверка пропуска МКАД
            mkad_level = None
            if eq['mkad_pass_date']:
                try:
                    mkad_date = datetime.strptime(eq['mkad_pass_date'], '%d.%m.%Y')
                    days_left = (mkad_date - current_date).days
                    mkad_level = self._severity_for_days(days_left)
                    severity = max(severity, mkad_level)
                except:
                    pass

            # Проверка диагностической карты
            diagnostic_level = None
            diagnostic_date_value = self._row_value(eq, 'diagnostic_card_date', '')
            if diagnostic_date_value:
                try:
                    diagnostic_date = datetime.strptime(diagnostic_date_value, '%d.%m.%Y')
                    days_left = (diagnostic_date - current_date).days
                    diagnostic_level = self._severity_for_days(days_left)
                    severity = max(severity, diagnostic_level)
                except:
                    pass
            
            insurance_cell = self._format_document_cell(
                self._row_value(eq, 'insurance_date', ''),
                self._row_value(eq, 'insurance_file_path', '')
            )
            diagnostic_cell = self._format_document_cell(
                diagnostic_date_value,
                self._row_value(eq, 'diagnostic_card_file_path', '')
            )
            sts_cell = self._format_sts_cell(
                self._row_value(eq, 'sts_certificate', ''),
                self._row_value(eq, 'sts_file_path', ''),
            )
            mkad_cell = eq['mkad_pass_date'] if eq['mkad_pass_date'] else '-'
            kmu_value = self._row_value(eq, 'secondary_current_value', 0)
            kmu_updated = self._row_value(eq, 'secondary_current_value_updated_at', '')
            kmu_cell = self._format_current_value_cell(kmu_value, kmu_updated) if self._row_value(eq, 'has_kmu', False) else '-'

            row_values = [
                idx + 1, eq['name'], eq['sts_pts'], sts_cell, eq['reg_number'],
                drivers_str, issues_str, measurement_type, eq['last_maintenance'],
                self._format_current_value_cell(eq['current_value'], self._row_value(eq, 'current_value_updated_at', '')),
                next_maintenance, status, insurance_cell, diagnostic_cell,
                mkad_cell, eq['service'], kmu_cell
            ]
            if getattr(self, 'use_equipment_sheet', False):
                self._equipment_row_ids.append(str(eq['id']))
                sheet_data.append(row_values)
            else:
                self.equipment_tree.insert('', 'end', iid=eq['id'], values=tuple(row_values))

        if getattr(self, 'use_equipment_sheet', False):
            self.equipment_tree.set_sheet_data(sheet_data, reset_col_positions=False, reset_row_positions=False)
            for row_idx, eq in enumerate(equipment_list):
                # Пересчитываем уровни только для нужных ячеек
                level_status = 0
                current_month = datetime.now().month
                is_winter = current_month in [11, 12, 1, 2]
                interval = eq['maintenance_interval_winter'] if is_winter else eq['maintenance_interval_summer']
                next_maintenance = eq['last_maintenance'] + interval
                remaining = next_maintenance - eq['current_value']
                warning_threshold = 50 if eq['measurement_type'] == 'motohours' else 500
                critical_threshold = warning_threshold // 2
                if remaining <= 0 or remaining <= critical_threshold:
                    level_status = 2
                elif remaining <= warning_threshold:
                    level_status = 1

                insurance_level = None
                if eq['insurance_date']:
                    try:
                        insurance_date = datetime.strptime(eq['insurance_date'], '%d.%m.%Y')
                        insurance_level = self._severity_for_days((insurance_date - current_date).days)
                    except Exception:
                        insurance_level = None

                diagnostic_level = None
                diagnostic_date_value = self._row_value(eq, 'diagnostic_card_date', '')
                if diagnostic_date_value:
                    try:
                        diagnostic_date = datetime.strptime(diagnostic_date_value, '%d.%m.%Y')
                        diagnostic_level = self._severity_for_days((diagnostic_date - current_date).days)
                    except Exception:
                        diagnostic_level = None

                mkad_level = None
                if eq['mkad_pass_date']:
                    try:
                        mkad_date = datetime.strptime(eq['mkad_pass_date'], '%d.%m.%Y')
                        mkad_level = self._severity_for_days((mkad_date - current_date).days)
                    except Exception:
                        mkad_level = None

                self._highlight_equipment_sheet_cell(row_idx, 11, level_status)
                self._highlight_equipment_sheet_cell(row_idx, 12, insurance_level)
                self._highlight_equipment_sheet_cell(row_idx, 13, diagnostic_level)
                self._highlight_equipment_sheet_cell(row_idx, 14, mkad_level)
    
    def add_equipment(self):
        """Добавление новой техники"""
        dialog = EquipmentDialog(self.root, self.db, title="Добавить технику")
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            self.refresh_equipment_views()
            self.update_statistics()
    
    def edit_equipment(self):
        """Редактирование техники"""
        is_preview = self._is_equipment_preview_active() and self.equipment_sheet_preview
        equipment_list = self.db.get_all_equipment() or []
        equipment = None
        equipment_id = None

        selected_name = ''
        selected_reg = ''
        selected_cur = ''
        selected_kmu = ''

        if self._is_equipment_preview_active() and self.equipment_sheet_preview:
            try:
                selected_rows = self.equipment_sheet_preview.get_selected_rows()
                if selected_rows:
                    row_index = sorted(list(selected_rows))[0]
                else:
                    current = self.equipment_sheet_preview.get_currently_selected()
                    row_index = getattr(current, 'row', None)
                    if row_index is None and isinstance(current, (list, tuple)) and len(current) > 0:
                        row_index = current[0]
                if row_index is not None and row_index >= 0:
                    selected_name = str(self.equipment_sheet_preview.get_cell_data(row_index, 1) or '').strip()
                    selected_reg = str(self.equipment_sheet_preview.get_cell_data(row_index, 4) or '').strip()
                    selected_cur = str(self.equipment_sheet_preview.get_cell_data(row_index, 9) or '').strip()
                    selected_kmu = str(self.equipment_sheet_preview.get_cell_data(row_index, 16) or '').strip()
            except Exception:
                pass
        else:
            try:
                selection = self.equipment_tree.selection()
                if selection:
                    item = self.equipment_tree.item(selection[0])
                    values = item.get('values', [])
                    if len(values) >= 17:
                        selected_name = str(values[1] or '').strip()
                        selected_reg = str(values[4] or '').strip()
                        selected_cur = str(values[9] or '').strip()
                        selected_kmu = str(values[16] or '').strip()
            except Exception:
                pass

        # 1) Пытаемся найти ровно ту строку, что видит пользователь.
        if selected_reg:
            candidates = []
            for row in equipment_list:
                reg = str(self._row_value(row, 'reg_number', '') or '').strip()
                if reg == selected_reg:
                    candidates.append(row)
            if selected_name:
                narrowed = [r for r in candidates if str(self._row_value(r, 'name', '') or '').strip() == selected_name]
                if narrowed:
                    candidates = narrowed
            if len(candidates) > 1 and (selected_cur or selected_kmu):
                narrowed = []
                for r in candidates:
                    cur_cell = self._format_current_value_cell(
                        self._row_value(r, 'current_value', 0),
                        self._row_value(r, 'current_value_updated_at', '')
                    )
                    kmu_cell = (
                        self._format_current_value_cell(
                            self._row_value(r, 'secondary_current_value', 0),
                            self._row_value(r, 'secondary_current_value_updated_at', '')
                        )
                        if self._row_value(r, 'has_kmu', False)
                        else '-'
                    )
                    if (not selected_cur or cur_cell == selected_cur) and (not selected_kmu or kmu_cell == selected_kmu):
                        narrowed.append(r)
                if narrowed:
                    candidates = narrowed
            if candidates:
                equipment = candidates[0]
                equipment_id = str(self._row_value(equipment, 'id', ''))

        # 2) Fallback по выбранному ID (только вне preview).
        if is_preview and not equipment:
            messagebox.showwarning(
                "Выбор строки",
                "Не удалось определить технику из выбранной строки.\n"
                "Кликните по нужной строке еще раз и повторите."
            )
            return
        if not equipment:
            candidate_id = self._get_selected_equipment_id()
            if candidate_id:
                equipment = self.db.get_equipment(candidate_id)
                equipment_id = str(candidate_id)

        if not equipment:
            messagebox.showerror("Ошибка", "Не удалось загрузить технику для редактирования.")
            return

        # Синхронизируем "текущие" значения с выбранной строкой таблицы:
        # окно редактирования должно показывать те же цифры, что и колонка.
        try:
            equipment = dict(equipment)
        except Exception:
            pass
        if isinstance(equipment, dict):
            def _parse_cell_number(cell_value):
                text = str(cell_value or '').strip()
                m = re.match(r"^\s*(-?\d+)", text)
                return int(m.group(1)) if m else None

            parsed_cur = _parse_cell_number(selected_cur)
            parsed_kmu = _parse_cell_number(selected_kmu)
            if parsed_cur is not None:
                equipment['current_value'] = parsed_cur
            if parsed_kmu is not None:
                equipment['secondary_current_value'] = parsed_kmu

        dialog = EquipmentDialog(
            self.root,
            self.db,
            equipment_id=equipment_id,
            title="Редактировать технику",
            equipment_data=equipment,
            equipment_reg_number=selected_reg,
        )
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            self.refresh_equipment_views()
            self.update_statistics()
    
    def delete_equipment(self):
        """Удаление техники"""
        equipment_id = self._get_selected_equipment_id()
        if not equipment_id:
            messagebox.showwarning("Предупреждение", "Выберите технику для удаления")
            return
        equipment = self.db.get_equipment(equipment_id)
        equipment_name = self._row_value(equipment, 'name', '')
        
        if messagebox.askyesno("Подтверждение", 
                               f"Удалить технику '{equipment_name}'?\nВся история ТО и неисправности будут удалены!"):
            self.db.delete_equipment(equipment_id)
            self.refresh_equipment_views()
            self.refresh_drivers_list()
            self.refresh_maintenance_list()
            self.refresh_issues_list()
            self.update_statistics()
            messagebox.showinfo("Успех", "Техника удалена")
    
    def move_equipment_up(self):
        """Переместить технику вверх в списке"""
        equipment_id = self._get_selected_equipment_id()
        if not equipment_id:
            messagebox.showwarning("Предупреждение", "Выберите технику")
            return
        
        self.db.move_equipment_up(equipment_id)
        self.refresh_equipment_views()
    
    def move_equipment_down(self):
        """Переместить технику вниз в списке"""
        equipment_id = self._get_selected_equipment_id()
        if not equipment_id:
            messagebox.showwarning("Предупреждение", "Выберите технику")
            return
        
        self.db.move_equipment_down(equipment_id)
        self.refresh_equipment_views()

    def start_equipment_drag(self, event):
        """Начало перетаскивания строки техники"""
        if getattr(self, 'use_equipment_sheet', False):
            return
        region = self.equipment_tree.identify_region(event.x, event.y)
        if region not in ('tree', 'cell'):
            self._drag_item = None
            self._is_dragging_equipment = False
            return

        item = self.equipment_tree.identify_row(event.y)
        if item:
            self._drag_item = item
            self._drag_changed = False
            self._is_dragging_equipment = True
            self._last_drag_target = None

    def on_equipment_drag(self, event):
        """Перетаскивание строки техники"""
        if getattr(self, 'use_equipment_sheet', False):
            return
        if not self._drag_item:
            return

        target_item = self.equipment_tree.identify_row(event.y)
        if not target_item or target_item == self._drag_item:
            return

        if target_item == self._last_drag_target:
            return

        current_index = self.equipment_tree.index(self._drag_item)
        target_index = self.equipment_tree.index(target_item)
        if current_index == target_index:
            return

        self.equipment_tree.move(self._drag_item, '', target_index)
        self._last_drag_target = target_item
        self._drag_changed = True

    def finish_equipment_drag(self, event):
        """Завершение перетаскивания и сохранение порядка"""
        if getattr(self, 'use_equipment_sheet', False):
            return
        if not self._drag_item:
            return

        try:
            if self._drag_changed:
                ordered_items = self.equipment_tree.get_children('')
                total = len(ordered_items)

                for index, equipment_id in enumerate(ordered_items):
                    sort_order = total - index
                    self.db.update_equipment(equipment_id, sort_order=sort_order)

                self.refresh_equipment_views()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить порядок техники:\n{str(e)}")
        finally:
            self._drag_item = None
            self._drag_changed = False
            self._is_dragging_equipment = False
            self._last_drag_target = None
    
    def _event_in_equipment_sheet_preview(self, event):
        """Клик по tksheet часто приходит с дочернего виджета, не с самого Sheet."""
        if not getattr(self, 'equipment_sheet_preview', None):
            return False
        w = event.widget
        while w is not None:
            if w == self.equipment_sheet_preview:
                return True
            w = getattr(w, 'master', None)
        return False

    def show_equipment_context_menu(self, event):
        """Показать контекстное меню по правой кнопке мыши"""
        if self._event_in_equipment_sheet_preview(event):
            self._select_equipment_preview_row_from_event(event)
            item = self._get_selected_equipment_id_from_preview()
            if not item:
                return

            context_menu = tk.Menu(self.root, tearoff=0)
            context_menu.add_command(label="Пройти ТО", command=self.register_maintenance)
            context_menu.add_command(label="Добавить неисправность", command=self.add_issue_for_equipment)
            context_menu.add_command(label="История неисправностей", command=self.show_equipment_issues_history)
            context_menu.add_separator()
            context_menu.add_command(label="Открыть файл страховки", command=self.open_insurance_file)
            context_menu.add_command(label="Открыть файл СТС", command=self.open_sts_file)
            context_menu.add_command(label="Открыть файл диагностической карты", command=self.open_diagnostic_card_file)
            context_menu.add_separator()
            context_menu.add_command(label="Редактировать", command=self.edit_equipment)
            context_menu.add_command(label="Управление водителями", command=self.assign_drivers_to_equipment)
            context_menu.add_separator()
            context_menu.add_command(label="Удалить", command=self.delete_equipment)
            context_menu.post(event.x_root, event.y_root)
            return

        if not self.equipment_tree:
            return

        # Определяем, на какой строке был клик
        if getattr(self, 'use_equipment_sheet', False):
            try:
                row_index = self.equipment_tree.identify_row(event.y)
                if isinstance(row_index, int) and row_index >= 0:
                    self.equipment_tree.select_row(row_index)
                    self.equipment_tree.set_currently_selected(row=row_index, column=0)
            except Exception:
                pass
            item = self._get_selected_equipment_id()
        else:
            item = self.equipment_tree.identify_row(event.y)
        if item:
            if not getattr(self, 'use_equipment_sheet', False):
                self.equipment_tree.selection_set(item)
            
            # Создаем контекстное меню
            context_menu = tk.Menu(self.root, tearoff=0)
            context_menu.add_command(label="Пройти ТО", command=self.register_maintenance)
            context_menu.add_command(label="Добавить неисправность", command=self.add_issue_for_equipment)
            context_menu.add_command(label="История неисправностей", command=self.show_equipment_issues_history)
            context_menu.add_separator()
            context_menu.add_command(label="Открыть файл страховки", command=self.open_insurance_file)
            context_menu.add_command(label="Открыть файл СТС", command=self.open_sts_file)
            context_menu.add_command(label="Открыть файл диагностической карты", command=self.open_diagnostic_card_file)
            context_menu.add_separator()
            context_menu.add_command(label="Редактировать", command=self.edit_equipment)
            context_menu.add_command(label="Управление водителями", command=self.assign_drivers_to_equipment)
            context_menu.add_separator()
            context_menu.add_command(label="Удалить", command=self.delete_equipment)
            
            # Показываем меню в месте клика
            context_menu.post(event.x_root, event.y_root)

    def _format_document_cell(self, date_value, file_path):
        date_text = date_value if date_value else '-'
        return f"{date_text} 📎" if file_path else date_text

    def _format_sts_cell(self, certificate_text, file_path):
        t = (certificate_text or '').strip()
        display = t if t else '-'
        return f"{display} 📎" if file_path else display

    def _document_cell_date_prefix(self, cell_text):
        """Дата из ячейки страховки/диагностики (без суффикса вложения)."""
        raw = str(cell_text or '').strip()
        if not raw or raw == '-':
            return ''
        s = raw.replace('📎', '').replace('[Файл]', '').replace(' (файл)', '').strip()
        if ' (' in s:
            s = s.split(' (', 1)[0].strip()
        return s

    def _split_invoice_paths(self, value):
        raw = str(value or '').strip()
        if not raw:
            return []
        normalized = raw.replace('\r', '\n').replace(';', '\n')
        return [p.strip() for p in normalized.split('\n') if p.strip()]

    def _format_current_value_cell(self, current_value, updated_at):
        value_text = str(current_value)
        if updated_at:
            return f"{value_text} ({updated_at})"
        return value_text

    def _severity_for_days(self, days_left):
        """Степень срочности по сроку: 0 зеленый, 1 желтый, 2 красный."""
        if days_left is None:
            return 0
        if days_left < 14:
            return 2
        if days_left <= 30:
            return 1
        return 0

    def _row_value(self, row, key, default=''):
        if row is None:
            return default
        if isinstance(row, dict):
            return row.get(key, default)
        try:
            value = row[key]
            return default if value is None else value
        except Exception:
            return default

    def _format_phone_display(self, value):
        raw = str(value or '')
        digits = ''.join(ch for ch in raw if ch.isdigit())
        if len(digits) == 11:
            return f"{digits[0]} ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
        return raw

    def _get_selected_equipment_id(self):
        if self._is_equipment_preview_active():
            preview_id = self._get_selected_equipment_id_from_preview()
            if preview_id:
                return preview_id

        if getattr(self, 'use_equipment_sheet', False):
            try:
                selected_rows = self.equipment_tree.get_selected_rows()
                if not selected_rows:
                    return None
                row_index = sorted(list(selected_rows))[0]
                if 0 <= row_index < len(self._equipment_row_ids):
                    return self._equipment_row_ids[row_index]
            except Exception:
                return None
            return None
        selection = self.equipment_tree.selection()
        if not selection:
            return None
        return selection[0]

    def _is_equipment_preview_active(self):
        if not self.equipment_sheet_preview:
            return False
        try:
            current_tab = self.notebook.select()
            return self.notebook.tab(current_tab, "text") == "Техника"
        except Exception:
            return False

    def _get_selected_equipment_id_from_preview(self):
        if not self.equipment_sheet_preview:
            return None
        try:
            selected_rows = self.equipment_sheet_preview.get_selected_rows()
            if not selected_rows:
                current = self.equipment_sheet_preview.get_currently_selected()
                row_index = getattr(current, 'row', None)
                if row_index is None and isinstance(current, (list, tuple)) and len(current) > 0:
                    row_index = current[0]
            else:
                row_index = sorted(list(selected_rows))[0]
            if 0 <= row_index < len(self._equipment_preview_row_ids):
                return self._equipment_preview_row_ids[row_index]
        except Exception:
            return None
        return None

    def _equipment_preview_data_row(self, event):
        """Индекс строки таблицы по событию мыши (координаты относительно canvas MT)."""
        sheet = self.equipment_sheet_preview
        if not sheet or not getattr(sheet, 'MT', None):
            return None
        w = getattr(event, 'widget', None)
        for _ in range(24):
            if w is None:
                break
            if w == sheet.MT or w == sheet.RI:
                return sheet.MT.identify_row(event=event)
            w = getattr(w, 'master', None)
        return None

    def _cancel_sheet_pending_redraw(self, sheet):
        """Отменяет отложенный refresh tksheet, чтобы не было второй отрисовки через ~16 ms."""
        aid = getattr(sheet, 'after_redraw_id', None)
        if aid is not None:
            try:
                sheet.after_cancel(aid)
            except Exception:
                pass
            sheet.after_redraw_id = None

    def _apply_equipment_preview_full_row(self, sheet, row_index):
        """Визуально выделить всю строку. Без лишнего debounce: сразу одна синхронная перерисовка."""
        if not isinstance(row_index, int) or row_index < 0:
            return
        self._cancel_sheet_pending_redraw(sheet)
        try:
            sheet.deselect(row="all", redraw=False)
        except Exception:
            try:
                sheet.deselect(row="all")
            except Exception:
                pass
        try:
            sheet.select_row(row_index, redraw=False, run_binding_func=True)
            sheet.set_currently_selected(row=row_index, column=0)
            self._cancel_sheet_pending_redraw(sheet)
            sheet.MT.main_table_redraw_grid_and_text(redraw_header=True, redraw_row_index=True)
        except Exception:
            try:
                sheet.select_row(row_index, redraw=True)
                sheet.set_currently_selected(row=row_index, column=0)
            except Exception:
                pass

    def _on_equipment_sheet_b1_extra(self, event):
        """Вызывается tksheet ПОСЛЕ внутреннего select_cell — заменяем на выделение строки."""
        if not self.equipment_sheet_preview:
            return
        row_index = self._equipment_preview_data_row(event)
        if row_index is None:
            return
        self._apply_equipment_preview_full_row(self.equipment_sheet_preview, row_index)

    def _select_equipment_preview_row_from_event(self, event):
        """Для контекстного меню и двойного клика — то же выделение строки."""
        if not self.equipment_sheet_preview:
            return
        row_index = self._equipment_preview_data_row(event)
        if row_index is None:
            return
        self._apply_equipment_preview_full_row(self.equipment_sheet_preview, row_index)

    def on_equipment_preview_double_click(self, event):
        self._select_equipment_preview_row_from_event(event)
        self.edit_equipment()

    def _highlight_equipment_sheet_cell(self, row_index, col_index, level):
        if not getattr(self, 'use_equipment_sheet', False):
            return
        bg = None
        if level == 2:
            bg = '#ffd0d0'
        elif level == 1:
            bg = '#fff4b8'
        elif level == 0:
            bg = '#d8f5d0'
        if bg is not None:
            try:
                self.equipment_tree.highlight_cells(row=row_index, column=col_index, fg='black', bg=bg)
            except Exception:
                pass

    def _open_document_file(self, file_path, display_name):
        if not file_path:
            messagebox.showinfo("Информация", f"Файл для '{display_name}' не прикреплен")
            return

        if str(file_path).startswith('supabase://'):
            if hasattr(self.db, 'resolve_invoice_path'):
                try:
                    url = self.db.resolve_invoice_path(file_path)
                    if not url:
                        messagebox.showerror("Ошибка", f"Не удалось получить доступ к файлу:\n{file_path}")
                        return

                    import tempfile
                    import urllib.request
                    file_ext = file_path.split('.')[-1] if '.' in file_path else 'bin'
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_ext}')
                    temp_path = temp_file.name
                    temp_file.close()
                    urllib.request.urlretrieve(url, temp_path)
                    os.startfile(temp_path)
                    return
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{str(e)}")
                    return
            messagebox.showerror("Ошибка", "Облачное хранилище не поддерживается в текущей конфигурации")
            return

        if os.path.exists(file_path):
            os.startfile(file_path)
            return

        messagebox.showerror("Ошибка", f"Файл не найден:\n{file_path}")

    def open_insurance_file(self):
        equipment_id = self._get_selected_equipment_id()
        if not equipment_id:
            messagebox.showwarning("Предупреждение", "Выберите технику")
            return
        equipment = self.db.get_equipment(equipment_id)
        self._open_document_file(self._row_value(equipment, 'insurance_file_path', ''), "Страховка")

    def open_diagnostic_card_file(self):
        equipment_id = self._get_selected_equipment_id()
        if not equipment_id:
            messagebox.showwarning("Предупреждение", "Выберите технику")
            return
        equipment = self.db.get_equipment(equipment_id)
        self._open_document_file(self._row_value(equipment, 'diagnostic_card_file_path', ''), "Диагностическая карта")

    def open_sts_file(self):
        equipment_id = self._get_selected_equipment_id()
        if not equipment_id:
            messagebox.showwarning("Предупреждение", "Выберите технику")
            return
        equipment = self.db.get_equipment(equipment_id)
        self._open_document_file(self._row_value(equipment, 'sts_file_path', ''), "СТС")
    
    def show_equipment_issues_history(self):
        """Показать историю неисправностей для выбранной техники"""
        equipment_id = self._get_selected_equipment_id()
        if not equipment_id:
            messagebox.showwarning("Предупреждение", "Выберите технику")
            return
        equipment = self.db.get_equipment(equipment_id)
        equipment_name = self._row_value(equipment, 'name', '')
        
        # Получаем все неисправности (открытые и закрытые)
        issues = self.db.get_equipment_issues(equipment_id)
        
        if not issues:
            messagebox.showinfo("История неисправностей", 
                              f"У техники '{equipment_name}' нет зарегистрированных неисправностей")
            return
        
        # Создаем окно с историей
        issues_window = tk.Toplevel(self.root)
        issues_window.title(f"История неисправностей: {equipment_name}")
        issues_window.geometry("900x500")
        issues_window.transient(self.root)
        
        # Заголовок
        header_frame = ttk.Frame(issues_window, padding=10)
        header_frame.pack(fill='x')
        ttk.Label(header_frame, text=f"История неисправностей: {equipment_name}", 
                 font=ui_font(12, 'bold')).pack()
        
        # Таблица
        tree_frame = ttk.Frame(issues_window)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        columns = ('Статус', 'Дата', 'Водитель', 'Описание', 'Решение')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        tree.heading('Статус', text='Статус')
        tree.heading('Дата', text='Дата сообщения')
        tree.heading('Водитель', text='Водитель')
        tree.heading('Описание', text='Описание')
        tree.heading('Решение', text='Как исправлено')
        
        tree.column('Статус', width=80)
        tree.column('Дата', width=120)
        tree.column('Водитель', width=120)
        tree.column('Описание', width=250)
        tree.column('Решение', width=250)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Заполняем данными
        for issue in issues:
            status = 'Закрыто' if issue['status'] == 'resolved' else 'Открыто'
            date = datetime.fromisoformat(issue['reported_date']).strftime('%d.%m.%Y %H:%M')
            driver = issue['driver_name'] if issue['driver_name'] else '-'
            description = issue['description']
            resolution = issue['resolution_comment'] if issue['resolution_comment'] else '-'
            
            tag = 'resolved' if issue['status'] == 'resolved' else 'open'
            tree.insert('', 'end', values=(status, date, driver, description, resolution), tags=(tag,))
        
        tree.tag_configure('open', background='#ffffcc')
        tree.tag_configure('resolved', background='#ccffcc')
        
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Кнопка закрытия
        button_frame = ttk.Frame(issues_window, padding=10)
        button_frame.pack(fill='x')
        ttk.Button(button_frame, text="Закрыть", command=issues_window.destroy, width=15).pack()
    
    def assign_drivers_to_equipment(self):
        """Привязка водителей к технике со сменами"""
        equipment_id = self._get_selected_equipment_id()
        if not equipment_id:
            messagebox.showwarning("Предупреждение", "Выберите технику")
            return
        equipment = self.db.get_equipment(equipment_id)
        equipment_name = self._row_value(equipment, 'name', '')
        
        dialog = DriverShiftsDialog(self.root, self.db, equipment_id, equipment_name)
        self.root.wait_window(dialog.dialog)
        
        # Обновляем списки после закрытия диалога
        self.refresh_drivers_list()
        self.refresh_equipment_views()
    
    def register_maintenance(self):
        """Регистрация ТО для выбранной техники"""
        equipment_id = self._get_selected_equipment_id()
        if not equipment_id:
            messagebox.showwarning("Предупреждение", "Выберите технику")
            return
        
        dialog = MaintenanceDialog(self.root, self.db, equipment_id=equipment_id)
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            self.refresh_equipment_views()
            self.refresh_maintenance_list()
            self.update_statistics()
    
    def add_issue_for_equipment(self):
        """Добавление неисправности для выбранной техники"""
        equipment_id = self._get_selected_equipment_id()
        if not equipment_id:
            messagebox.showwarning("Предупреждение", "Выберите технику")
            return
        
        dialog = IssueDialog(self.root, self.db, equipment_id=equipment_id)
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            self.refresh_issues_list()
            self.refresh_equipment_views()
            self.update_statistics()
    
    # ===== Методы для работы с водителями =====
    
    def refresh_drivers_list(self):
        """Обновление списка водителей"""
        if self.drivers_tree is not None:
            for item in self.drivers_tree.get_children():
                self.drivers_tree.delete(item)
        if self.drivers_sheet_preview is not None:
            self.drivers_sheet_preview.set_sheet_data([])
            self._drivers_preview_row_ids = []
        
        drivers_list = self.db.get_all_drivers() or []
        equipment_map = {}
        if hasattr(self.db, 'get_equipment_names_by_driver_id'):
            try:
                equipment_map = self.db.get_equipment_names_by_driver_id() or {}
            except Exception:
                equipment_map = {}
        sheet_data = []
        for idx, driver in enumerate(drivers_list):
            driver_id = self._row_value(driver, 'id', None)
            driver_name = self._row_value(driver, 'name', '')
            driver_phone = self._row_value(driver, 'phone', '')
            if driver_id is None:
                continue
            # Получаем технику водителя
            if equipment_map:
                equipment_names = ', '.join(equipment_map.get(str(driver_id), []))
            else:
                equipment_list = self.db.get_driver_equipment(driver_id) or []
                equipment_names = ', '.join([eq['name'] + ' (' + eq['reg_number'] + ')' for eq in equipment_list])
            row_values = [
                idx + 1,
                driver_name,
                self._format_phone_display(driver_phone),
                self._row_value(driver, 'fuel_card', ''),
                equipment_names
            ]
            if self.drivers_tree is not None:
                self.drivers_tree.insert('', 'end', iid=str(driver_id), values=tuple(row_values))

    def on_notebook_tab_changed(self, event=None):
        """Ленивая перерисовка некоторых вкладок после фактического показа."""
        try:
            current_tab = self.notebook.select()
            title = self.notebook.tab(current_tab, 'text')
        except Exception:
            return
        if title == 'Водители':
            self.refresh_drivers_list()

    def manage_driver_shifts_from_drivers_tab(self):
        """Открыть управление водителями для техники выбранного водителя."""
        driver_id = self._get_selected_driver_id()
        if not driver_id:
            messagebox.showwarning("Предупреждение", "Выберите водителя")
            return
        equipment_list = self.db.get_driver_equipment(driver_id) or []
        if not equipment_list:
            messagebox.showinfo("Информация", "У выбранного водителя нет закрепленной техники")
            return
        eq = equipment_list[0]
        dialog = DriverShiftsDialog(self.root, self.db, eq['id'], eq['name'])
        self.root.wait_window(dialog.dialog)
        self.refresh_drivers_list()
        self.refresh_equipment_views()
    
    def add_driver(self):
        """Добавление нового водителя"""
        dialog = DriverDialog(self.root, self.db, title="Добавить водителя")
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            self.refresh_drivers_list()
            self.update_statistics()
    
    def edit_driver(self):
        """Редактирование водителя"""
        driver_id = self._get_selected_driver_id()
        if not driver_id:
            messagebox.showwarning("Предупреждение", "Выберите водителя для редактирования")
            return

        dialog = DriverDialog(self.root, self.db, driver_id=driver_id, title="Редактировать водителя")
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            self.refresh_drivers_list()
    
    def delete_driver(self):
        """Удаление водителя"""
        driver_id = self._get_selected_driver_id()
        if not driver_id:
            messagebox.showwarning("Предупреждение", "Выберите водителя для удаления")
            return
        driver_name = self._driver_name_by_id(driver_id)
        
        if messagebox.askyesno("Подтверждение", 
                               f"Удалить водителя '{driver_name}'?"):
            self.db.delete_driver(driver_id)
            self.refresh_drivers_list()
            self.refresh_equipment_views()
            self.update_statistics()
            messagebox.showinfo("Успех", "Водитель удален")
    
    # ===== Методы для работы с ТО =====
    
    def refresh_maintenance_list(self):
        """Обновление списка ТО"""
        for item in self.maintenance_tree.get_children():
            self.maintenance_tree.delete(item)
        self._apply_maintenance_columns_mode()

        equipment_list = self.db.get_all_equipment()
        maintenance_list = self.db.get_all_maintenance_history()
        search_text = ''
        if hasattr(self, 'maintenance_search_var'):
            search_text = (self.maintenance_search_var.get() or '').strip().lower()
        only_with_records = bool(self.maintenance_only_with_records.get()) if hasattr(self, 'maintenance_only_with_records') else False

        def parse_maintenance_date(date_value):
            if not date_value:
                return datetime.min
            try:
                parsed_date = datetime.fromisoformat(str(date_value).replace('Z', '+00:00'))
                if parsed_date.tzinfo is not None:
                    return parsed_date.astimezone(timezone.utc).replace(tzinfo=None)
                return parsed_date
            except Exception:
                return datetime.min

        # Группировка истории ТО по технике
        maintenance_by_equipment = {}
        for maint in maintenance_list:
            equipment_id = str(maint.get('equipment_id', ''))
            maintenance_by_equipment.setdefault(equipment_id, []).append(maint)

        # Сортировка записей ТО внутри каждой техники: новые сверху
        latest_date_by_equipment = {}
        for equipment_id, records in maintenance_by_equipment.items():
            records.sort(key=lambda m: parse_maintenance_date(m.get('maintenance_date')), reverse=True)
            latest_date_by_equipment[equipment_id] = parse_maintenance_date(records[0].get('maintenance_date')) if records else datetime.min

        # Все машины, сортировка по дате последнего добавленного ТО (новые сверху)
        equipment_sorted = sorted(equipment_list, key=lambda eq: str(eq.get('name', '')).lower())
        equipment_sorted = sorted(
            equipment_sorted,
            key=lambda eq: latest_date_by_equipment.get(str(eq.get('id')), datetime.min),
            reverse=True
        )

        for equipment in equipment_sorted:
            equipment_id = str(equipment.get('id'))
            equipment_name = equipment.get('name', '-')
            equipment_number = equipment.get('reg_number', '-')
            records = maintenance_by_equipment.get(equipment_id, [])
            if self.maintenance_current_equipment_id and equipment_id != str(self.maintenance_current_equipment_id):
                continue
            if only_with_records and not records:
                continue
            if search_text:
                eq_match = (
                    search_text in str(equipment_name).lower() or
                    search_text in str(equipment_number).lower()
                )
                rec_match = any(
                    search_text in str(m.get('comment', '')).lower() or
                    search_text in str(m.get('maintenance_value', '')).lower() or
                    search_text in str(m.get('reg_number', equipment_number)).lower()
                    for m in records
                )
                if not (eq_match or rec_match):
                    continue

            if self.maintenance_current_equipment_id is None:
                self.maintenance_tree.insert(
                    '',
                    'end',
                    iid=f"equipment_{equipment_id}",
                    text=f"{equipment_name} ({equipment_number})",
                    values=('', '', '', '', '', '', f"Записей: {len(records)}", '', '')
                )
                continue

            for maint in records:
                maintenance_date = parse_maintenance_date(maint.get('maintenance_date'))
                date_str = maintenance_date.strftime('%d.%m.%Y %H:%M') if maintenance_date != datetime.min else ''
                has_invoice = '✓' if maint.get('invoice_path') else ''
                row_tags = ()
                if maintenance_date != datetime.min:
                    days_old = (datetime.now() - maintenance_date).days
                    if days_old <= 30:
                        row_tags = ('recent',)
                    elif days_old > 365:
                        row_tags = ('old',)

                counter_type = str(maint.get('counter_type') or 'primary').strip().lower()
                counter_label = 'КМУ (м/ч)' if counter_type == 'kmu' else 'Шасси (км)'
                self.maintenance_tree.insert(
                    '',
                    'end',
                    text='• Запись ТО',
                    values=(
                        maint.get('reg_number', equipment_number),
                        counter_label,
                        maint.get('maintenance_value', ''),
                        date_str,
                        maint.get('comment', ''),
                        has_invoice,
                        '',
                        maint.get('id', ''),
                        maint.get('invoice_path', '')
                    ),
                    tags=row_tags
                )
            break
        self.maintenance_tree.tag_configure('recent', background='#e9f7ef')
        self.maintenance_tree.tag_configure('old', background='#f8f9fa')
        if hasattr(self, 'maintenance_breadcrumb'):
            if self.maintenance_current_equipment_id:
                eq_name = ''
                selected = self.db.get_equipment(self.maintenance_current_equipment_id)
                if selected:
                    eq_name = self._row_value(selected, 'name', '')
                self.maintenance_breadcrumb.config(text=f"История ТО / {eq_name or self.maintenance_current_equipment_id}")
            else:
                self.maintenance_breadcrumb.config(text="История ТО")

    def _apply_maintenance_columns_mode(self):
        """В корне показываем только «папки» техники; в папке — все колонки записей ТО."""
        in_equipment_folder = self.maintenance_current_equipment_id is not None
        if in_equipment_folder:
            self.maintenance_tree.column('Номер', width=100, minwidth=40, stretch=False)
            self.maintenance_tree.column('Счетчик', width=120, minwidth=70, stretch=False)
            self.maintenance_tree.column('Значение', width=120, minwidth=60, stretch=False)
            self.maintenance_tree.column('Дата', width=150, minwidth=80, stretch=False)
            self.maintenance_tree.column('Комментарий', width=400, minwidth=100, stretch=False)
            self.maintenance_tree.column('Счет', width=100, minwidth=40, stretch=False)
            self.maintenance_tree.column('Записей', width=0, minwidth=0, stretch=False)
            self.maintenance_tree.heading('Номер', text='Номер')
            self.maintenance_tree.heading('Счетчик', text='Счетчик')
            self.maintenance_tree.heading('Значение', text='Пробег/моточасы')
            self.maintenance_tree.heading('Дата', text='Дата ТО')
            self.maintenance_tree.heading('Комментарий', text='Комментарий')
            self.maintenance_tree.heading('Счет', text='Счет')
            self.maintenance_tree.heading('Записей', text='')
        else:
            self.maintenance_tree.column('Номер', width=0, minwidth=0, stretch=False)
            self.maintenance_tree.column('Счетчик', width=0, minwidth=0, stretch=False)
            self.maintenance_tree.column('Значение', width=0, minwidth=0, stretch=False)
            self.maintenance_tree.column('Дата', width=0, minwidth=0, stretch=False)
            self.maintenance_tree.column('Комментарий', width=0, minwidth=0, stretch=False)
            self.maintenance_tree.column('Счет', width=0, minwidth=0, stretch=False)
            self.maintenance_tree.column('Записей', width=120, minwidth=60, stretch=False)
            self.maintenance_tree.heading('Номер', text='')
            self.maintenance_tree.heading('Счетчик', text='')
            self.maintenance_tree.heading('Значение', text='')
            self.maintenance_tree.heading('Дата', text='')
            self.maintenance_tree.heading('Комментарий', text='')
            self.maintenance_tree.heading('Счет', text='')
            self.maintenance_tree.heading('Записей', text='Записей')

    def back_to_maintenance_equipment_list(self):
        self.maintenance_current_equipment_id = None
        self.refresh_maintenance_list()

    def show_maintenance_context_menu(self, event):
        if self.maintenance_current_equipment_id is None:
            return
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Назад к списку техники", command=self.back_to_maintenance_equipment_list)
        menu.post(event.x_root, event.y_root)
    
    def add_maintenance(self):
        """Добавление записи о ТО"""
        dialog = MaintenanceDialog(self.root, self.db)
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            self.refresh_equipment_views()
            self.refresh_maintenance_list()
            self.update_statistics()

    def _get_selected_maintenance_entry(self):
        """Получить выбранную вложенную запись ТО из дерева"""
        selection = self.maintenance_tree.selection()
        if not selection:
            return None

        selected_item = selection[0]
        item = self.maintenance_tree.item(selected_item)
        values = item.get('values', [])
        if len(values) < 9:
            return None
        if not values[7]:
            return None
        equipment_id = str(self.maintenance_current_equipment_id or '')
        counter_label = str(values[1] or '').strip().lower()
        counter_type = 'kmu' if 'кму' in counter_label else 'primary'

        return {
            'maintenance_id': values[7],
            'equipment_id': equipment_id,
            'equipment_name': '',
            'reg_number': values[0],
            'counter_type': counter_type,
            'maintenance_value': values[2],
            'maintenance_date_display': values[3],
            'comment': values[4],
            'invoice_path': values[8]
        }

    def edit_maintenance(self):
        """Редактирование записи ТО"""
        selected_entry = self._get_selected_maintenance_entry()
        if not selected_entry:
            messagebox.showwarning("Предупреждение", "Выберите вложенную запись ТО для редактирования")
            return

        dialog = MaintenanceDialog(
            self.root,
            self.db,
            equipment_id=selected_entry['equipment_id'],
            maintenance_id=selected_entry['maintenance_id'],
            initial_data=selected_entry
        )
        self.root.wait_window(dialog.dialog)

        if dialog.result:
            self.refresh_equipment_views()
            self.refresh_maintenance_list()
            self.update_statistics()

    def on_maintenance_double_click(self, event):
        """Двойной клик по записи ТО: открыть счет"""
        item_id = self.maintenance_tree.identify_row(event.y)
        if not item_id:
            return
        self.maintenance_tree.selection_set(item_id)
        item = self.maintenance_tree.item(item_id)
        values = item.get('values', [])
        if self.maintenance_current_equipment_id is None:
            if item_id.startswith('equipment_'):
                self.maintenance_current_equipment_id = item_id.replace('equipment_', '', 1)
                self.refresh_maintenance_list()
            return
        if values and len(values) >= 9 and values[7]:
            self.open_invoice()
    
    def open_invoice(self):
        """Открытие файла счета"""
        selected_entry = self._get_selected_maintenance_entry()
        if not selected_entry:
            messagebox.showwarning("Предупреждение", "Выберите вложенную запись ТО у нужной машины")
            return

        invoice_path = selected_entry.get('invoice_path', '')

        if invoice_path:
            # Проверка на облачный путь (Supabase Storage)
            if str(invoice_path).startswith('supabase://'):
                # Попытка получить URL для скачивания
                if hasattr(self.db, 'resolve_invoice_path'):
                    try:
                        url = self.db.resolve_invoice_path(invoice_path)
                        if url:
                            # Скачиваем файл во временную директорию
                            import tempfile
                            import urllib.request
                            
                            # Получаем расширение файла из пути
                            file_ext = invoice_path.split('.')[-1] if '.' in invoice_path else 'pdf'
                            
                            # Создаем временный файл
                            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_ext}')
                            temp_path = temp_file.name
                            temp_file.close()
                            
                            # Скачиваем файл
                            urllib.request.urlretrieve(url, temp_path)
                            
                            # Открываем файл
                            os.startfile(temp_path)
                        else:
                            messagebox.showerror("Ошибка", f"Не удалось получить доступ к файлу:\n{invoice_path}")
                    except Exception as e:
                        messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{str(e)}")
                else:
                    messagebox.showerror("Ошибка", "Облачное хранилище не поддерживается в текущей конфигурации")
            # Локальный файл
            elif os.path.exists(invoice_path):
                os.startfile(invoice_path)
            else:
                messagebox.showerror("Ошибка", f"Файл не найден:\n{invoice_path}")
        else:
            messagebox.showinfo("Информация", "Счет не прикреплен")
    
    def open_regulations(self):
        """Открытие диалога управления регламентами ТО"""
        dialog = RegulationsDialog(self.root, self.db, user_id=None)
        self.root.wait_window(dialog.dialog)
    
    # ===== Методы для работы с неисправностями =====
    
    def refresh_issues_list(self):
        """Обновление списка неисправностей"""
        for item in self.issues_tree.get_children():
            self.issues_tree.delete(item)
        
        filter_value = self.issues_filter.get()
        status_filter = None
        if filter_value == 'Открытые':
            status_filter = 'open'
        elif filter_value == 'Закрытые':
            status_filter = 'resolved'
        else:
            self.issues_closed_current_equipment_id = None
        
        issues_list = self.db.get_all_issues(status=status_filter)
        if status_filter == 'resolved' and self.issues_closed_current_equipment_id is None:
            grouped = {}
            for issue in issues_list:
                eid = str(issue.get('equipment_id', ''))
                grouped.setdefault(eid, []).append(issue)
            for eid, rows in grouped.items():
                eq_name = self._row_value(rows[0], 'equipment_name', '-')
                reg = self._row_value(rows[0], 'reg_number', '-')
                self.issues_tree.insert(
                    '', 'end',
                    iid=f"eq_{eid}",
                    text=f"{eq_name} ({reg})",
                    values=('', eq_name, reg, '', '', 'Закрыто', '', '', f"Записей: {len(rows)}", '', '', '', 'folder', eid),
                    tags=('resolved',),
                )
            self.issues_tree.tag_configure('resolved', background='#ccffcc')
            return

        display_idx = 0
        for issue in issues_list:
            if status_filter == 'resolved' and self.issues_closed_current_equipment_id:
                if str(issue.get('equipment_id', '')) != str(self.issues_closed_current_equipment_id):
                    continue
            display_idx += 1
            reported_date = datetime.fromisoformat(issue['reported_date']).strftime('%d.%m.%Y %H:%M')
            resolved_date = ''
            if issue['resolved_date']:
                resolved_date = datetime.fromisoformat(issue['resolved_date']).strftime('%d.%m.%Y %H:%M')
            
            status = 'Открыто' if issue['status'] == 'open' else 'Закрыто'
            driver_name = issue['driver_name'] if issue['driver_name'] else '-'
            resolution_comment = self._row_value(issue, 'resolution_comment', '') or '-'
            resolution_invoice_path = self._row_value(issue, 'resolution_invoice_path', '')
            invoice_count = len(self._split_invoice_paths(resolution_invoice_path))
            has_resolution_invoice = f'✓ {invoice_count}' if invoice_count else ''
            
            tag = 'open' if issue['status'] == 'open' else 'resolved'
            
            self.issues_tree.insert('', 'end', values=(
                display_idx, issue['equipment_name'], issue['reg_number'],
                driver_name, issue['description'], status, reported_date, resolved_date,
                resolution_comment, has_resolution_invoice, resolution_invoice_path, issue['id'], 'issue', str(issue.get('equipment_id', ''))
            ), tags=(tag,))
        
        self.issues_tree.tag_configure('open', background='#ffffcc')
        self.issues_tree.tag_configure('resolved', background='#ccffcc')
        if hasattr(self, 'issues_breadcrumb'):
            if status_filter == 'resolved' and self.issues_closed_current_equipment_id is not None:
                eq_name = ''
                selected = self.db.get_equipment(self.issues_closed_current_equipment_id)
                if selected:
                    eq_name = self._row_value(selected, 'name', '')
                self.issues_breadcrumb.config(text=f"Неисправности / Закрытые / {eq_name or self.issues_closed_current_equipment_id}")
            elif status_filter == 'resolved':
                self.issues_breadcrumb.config(text="Неисправности / Закрытые")
            elif status_filter == 'open':
                self.issues_breadcrumb.config(text="Неисправности / Открытые")
            else:
                self.issues_breadcrumb.config(text="Неисправности")

    def on_issues_filter_changed(self, event=None):
        if self.issues_filter.get() != 'Закрытые':
            self.issues_closed_current_equipment_id = None
        self.refresh_issues_list()

    def back_to_closed_issues_equipment_list(self):
        self.issues_closed_current_equipment_id = None
        self.refresh_issues_list()

    def show_issues_context_menu(self, event):
        if self.issues_closed_current_equipment_id is None:
            return
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Назад к списку техники", command=self.back_to_closed_issues_equipment_list)
        menu.post(event.x_root, event.y_root)

    def on_issues_double_click(self, event):
        item_id = self.issues_tree.identify_row(event.y)
        if not item_id:
            return
        self.issues_tree.selection_set(item_id)
        item = self.issues_tree.item(item_id)
        values = item.get('values', [])
        if len(values) >= 14 and values[12] == 'folder':
            self.issues_closed_current_equipment_id = values[13]
            self.refresh_issues_list()
            return
        self.open_issue_resolution_invoice()
    
    def add_issue(self):
        """Добавление неисправности"""
        dialog = IssueDialog(self.root, self.db)
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            self.refresh_issues_list()
            self.refresh_equipment_views()
            self.update_statistics()
    
    def resolve_issue(self):
        """Закрытие неисправности"""
        selection = self.issues_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите неисправность")
            return
        
        item = self.issues_tree.item(selection[0])
        values = item.get('values', [])
        if len(values) < 14 or values[12] != 'issue':
            messagebox.showwarning("Предупреждение", "Выберите запись неисправности")
            return
        issue_id = values[11]
        status = values[5]
        
        if status == 'Закрыто':
            messagebox.showinfo("Информация", "Неисправность уже закрыта")
            return
        
        reg_number = values[2]
        dialog = ResolveIssueDialog(self.root, self.db, issue_id, reg_number=reg_number)
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            self.refresh_issues_list()
            self.refresh_equipment_views()
            self.update_statistics()

    def edit_issue(self):
        """Редактирование неисправности."""
        selection = self.issues_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите неисправность")
            return

        values = self.issues_tree.item(selection[0]).get('values', [])
        if len(values) < 14 or values[12] != 'issue':
            messagebox.showwarning("Предупреждение", "Выберите запись неисправности")
            return
        issue_id = values[11]
        status = values[5]
        if status == 'Закрыто':
            if not messagebox.askyesno(
                "Закрытая неисправность",
                "Вы выбрали закрытую неисправность. Разрешить редактирование описания и привязок?"
            ):
                return

        dialog = IssueDialog(self.root, self.db, issue_id=issue_id)
        self.root.wait_window(dialog.dialog)
        if dialog.result:
            self.refresh_issues_list()
            self.refresh_equipment_views()
            self.update_statistics()
    
    def delete_issue(self):
        """Удаление неисправности"""
        selection = self.issues_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите неисправность")
            return
        
        item = self.issues_tree.item(selection[0])
        values = item.get('values', [])
        if len(values) < 14 or values[12] != 'issue':
            messagebox.showwarning("Предупреждение", "Выберите запись неисправности")
            return
        issue_id = values[11]
        issue_description = values[4]
        
        if messagebox.askyesno("Подтверждение", 
                               f"Удалить неисправность '{issue_description}'?"):
            self.db.delete_issue(issue_id)
            self.refresh_issues_list()
            self.refresh_equipment_views()
            self.update_statistics()
            messagebox.showinfo("Успех", "Неисправность удалена")

    def open_issue_resolution_invoice(self):
        """Открытие счета, прикрепленного при устранении неисправности."""
        selection = self.issues_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите неисправность")
            return

        item = self.issues_tree.item(selection[0])
        values = item.get('values', [])
        if len(values) < 14:
            messagebox.showerror("Ошибка", "Не удалось получить путь к файлу счета")
            return
        if values[12] == 'folder':
            self.issues_closed_current_equipment_id = values[13]
            self.refresh_issues_list()
            return

        invoice_paths = self._split_invoice_paths(values[10])
        if not invoice_paths:
            messagebox.showinfo("Информация", "Счет по устранению не прикреплен")
            return
        for idx, invoice_path in enumerate(invoice_paths, start=1):
            self._open_document_file(invoice_path, f"Счет по устранению неисправности #{idx}")
    
    # ===== Методы для экспорта =====
    
    def export_to_excel(self):
        """Экспорт всех данных в Excel"""
        file_path = filedialog.asksaveasfilename(
            defaultextension='.xlsx',
            filetypes=[('Excel files', '*.xlsx')],
            initialfile=f'TO_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
        
        if file_path:
            try:
                self.export_manager.export_all(file_path)
                messagebox.showinfo("Успех", f"Данные экспортированы в:\n{file_path}")
                
                if messagebox.askyesno("Открыть файл?", "Открыть экспортированный файл?"):
                    os.startfile(file_path)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка экспорта:\n{str(e)}")
    
    def export_equipment_only(self):
        """Экспорт только списка техники"""
        file_path = filedialog.asksaveasfilename(
            defaultextension='.xlsx',
            filetypes=[('Excel files', '*.xlsx')],
            initialfile=f'equipment_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
        
        if file_path:
            try:
                self.export_manager.export_equipment(file_path)
                messagebox.showinfo("Успех", f"Данные экспортированы")
                
                if messagebox.askyesno("Открыть файл?", "Открыть экспортированный файл?"):
                    os.startfile(file_path)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка экспорта:\n{str(e)}")
    
    def export_maintenance_only(self):
        """Экспорт истории ТО"""
        file_path = filedialog.asksaveasfilename(
            defaultextension='.xlsx',
            filetypes=[('Excel files', '*.xlsx')],
            initialfile=f'maintenance_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
        
        if file_path:
            try:
                self.export_manager.export_maintenance_history(file_path)
                messagebox.showinfo("Успех", f"Данные экспортированы")
                
                if messagebox.askyesno("Открыть файл?", "Открыть экспортированный файл?"):
                    os.startfile(file_path)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка экспорта:\n{str(e)}")
    
    def export_issues_only(self):
        """Экспорт неисправностей"""
        file_path = filedialog.asksaveasfilename(
            defaultextension='.xlsx',
            filetypes=[('Excel files', '*.xlsx')],
            initialfile=f'issues_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
        
        if file_path:
            try:
                self.export_manager.export_issues(file_path)
                messagebox.showinfo("Успех", f"Данные экспортированы")
                
                if messagebox.askyesno("Открыть файл?", "Открыть экспортированный файл?"):
                    os.startfile(file_path)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка экспорта:\n{str(e)}")
    
    # ===== Методы для работы с пользователями =====
    
    def refresh_users_list(self):
        """Обновление списка пользователей"""
        for item in self.users_tree.get_children():
            self.users_tree.delete(item)
        
        users = self.user_manager.get_all_users()
        
        for user in users:
            # Форматирование роли
            role_names = {
                'superadmin': 'Супер-админ',
                'admin': 'Администратор',
                'manager': 'Менеджер',
                'user': 'Пользователь'
            }
            role = role_names.get(user.get('role', 'user'), user.get('role', 'user'))
            
            # Статус
            status = 'Активен' if user.get('is_active', True) else 'Отключен'
            
            # Форматирование даты
            created_at = user.get('created_at', '')
            if created_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    created_at = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    pass
            
            if self.is_superadmin:
                self.users_tree.insert('', 'end', values=(
                    user['id'],
                    user.get('company_name', '-'),
                    user.get('company_phone', '-'),
                    user.get('company_email', '-'),
                    user['username'],
                    user.get('full_name', ''),
                    role,
                    status,
                    created_at
                ))
            else:
                self.users_tree.insert('', 'end', values=(
                    user['id'],
                    user['username'],
                    user.get('full_name', ''),
                    role,
                    status,
                    created_at
                ))
    
    def add_user(self):
        """Добавление нового пользователя"""
        dialog = UserDialog(self.root, self.auth_manager)
        result = dialog.show()
        
        if result:
            # Создаем пользователя через AuthManager
            user_id = self.auth_manager.create_user(
                username=result['username'],
                password=result['password'],
                full_name=result['full_name'],
                role=result['role']
            )
            
            if user_id:
                # Обновляем статус активности, если нужно
                if not result['is_active']:
                    self.user_manager.update_user(
                        user_id,
                        result['full_name'],
                        result['role'],
                        result['is_active']
                    )
                
                messagebox.showinfo("Успех", "Пользователь успешно добавлен!")
                self.refresh_users_list()
            else:
                messagebox.showerror("Ошибка", "Не удалось создать пользователя.\nВозможно, такой логин уже существует.")
    
    def edit_user(self):
        """Редактирование пользователя"""
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выберите пользователя для редактирования")
            return
        
        user_id = self.users_tree.item(selected[0])['values'][0]
        
        # Нельзя редактировать самого себя (только через смену пароля)
        if user_id == self.auth_manager.current_user['id']:
            messagebox.showwarning(
                "Внимание",
                "Для изменения своих данных используйте меню 'Файл' → 'Сменить пароль'"
            )
            return
        
        dialog = UserDialog(self.root, self.auth_manager, user_id)
        result = dialog.show()
        
        if result:
            if self.user_manager.update_user(
                result['id'],
                result['full_name'],
                result['role'],
                result['is_active']
            ):
                messagebox.showinfo("Успех", "Данные пользователя обновлены!")
                self.refresh_users_list()
            else:
                messagebox.showerror("Ошибка", "Не удалось обновить пользователя")
    
    def reset_user_password(self):
        """Сброс пароля пользователя"""
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выберите пользователя")
            return
        
        user_id = self.users_tree.item(selected[0])['values'][0]
        username = self.users_tree.item(selected[0])['values'][1]
        
        # Нельзя сбросить пароль самому себе
        if user_id == self.auth_manager.current_user['id']:
            messagebox.showwarning("Внимание", "Для изменения своего пароля используйте меню 'Файл' → 'Сменить пароль'")
            return
        
        dialog = ResetPasswordDialog(self.root, username)
        new_password = dialog.show()
        
        if new_password:
            if self.auth_manager.reset_user_password(user_id, new_password):
                messagebox.showinfo(
                    "Успех",
                    f"Пароль пользователя '{username}' успешно сброшен!\n\n"
                    f"Новый пароль: {new_password}\n\n"
                    "ВНИМАНИЕ: Сообщите новый пароль пользователю"
                )
            else:
                messagebox.showerror("Ошибка", "Не удалось сбросить пароль")
    
    def delete_user(self):
        """Удаление пользователя"""
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выберите пользователя для удаления")
            return
        
        user_id = self.users_tree.item(selected[0])['values'][0]
        username = self.users_tree.item(selected[0])['values'][1]
        
        # Нельзя удалить самого себя
        if user_id == self.auth_manager.current_user['id']:
            messagebox.showerror("Ошибка", "Нельзя удалить самого себя!")
            return
        
        if messagebox.askyesno(
            "Подтверждение",
            f"Вы действительно хотите удалить пользователя '{username}'?\n\n"
            "Это действие нельзя отменить!"
        ):
            if self.user_manager.delete_user(user_id):
                messagebox.showinfo("Успех", "Пользователь удален")
                self.refresh_users_list()
            else:
                messagebox.showerror("Ошибка", "Не удалось удалить пользователя")
    
    # ===== Вспомогательные методы =====
    
    def refresh_equipment_views(self):
        """Обновить только таблицу(ы) техники (без остальных вкладок)."""
        if self.equipment_tree is not None:
            self.refresh_equipment_list()
        if self.equipment_sheet_preview is not None:
            self.refresh_equipment_sheet_preview()

    def update_statistics(self):
        """Обновление статистики"""
        if not hasattr(self, 'stats_labels') or not self.stats_labels:
            return
        equipment_list = self.db.get_all_equipment()
        equipment_count = len(equipment_list)
        drivers_count = len(self.db.get_all_drivers())
        maintenance_count = len(self.db.get_all_maintenance_history())
        open_issues_count = len(self.db.get_all_issues(status='open'))
        
        maintenance_needed = 0
        current_month = datetime.now().month
        is_winter = current_month in [10, 11, 12, 1, 2, 3]
        
        for eq in equipment_list:
            interval = eq['maintenance_interval_winter'] if is_winter else eq['maintenance_interval_summer']
            next_maintenance = eq['last_maintenance'] + interval
            if eq['current_value'] >= next_maintenance:
                maintenance_needed += 1
        
        self.stats_labels['total_equipment'].config(text=str(equipment_count))
        self.stats_labels['total_drivers'].config(text=str(drivers_count))
        self.stats_labels['total_maintenance'].config(text=str(maintenance_count))
        self.stats_labels['open_issues'].config(text=str(open_issues_count))
        self.stats_labels['maintenance_needed'].config(text=str(maintenance_needed))

    def _set_maintenance_expanded(self, expanded: bool):
        """Массово развернуть/свернуть группы истории ТО."""
        for item in self.maintenance_tree.get_children():
            self.maintenance_tree.item(item, open=expanded)

    def _driver_name_by_id(self, driver_id):
        for driver in self.db.get_all_drivers():
            if str(driver.get('id')) == str(driver_id):
                return self._row_value(driver, 'name', '')
        return str(driver_id)

    def _get_selected_driver_id(self):
        if self.drivers_tree is None:
            return None
        selection = self.drivers_tree.selection()
        return selection[0] if selection else None
    
    def refresh_all_tabs(self):
        """Обновление всех вкладок"""
        if self.is_superadmin:
            try:
                self.refresh_users_list()
            except Exception as e:
                _startup_log(f"refresh_users_list failed (superadmin): {e!r}")
            return

        failures = []

        try:
            self.refresh_equipment_views()
        except Exception as e:
            failures.append(("Техника", e))
            _startup_log(f"refresh_equipment_views failed: {e!r}")

        try:
            self.refresh_drivers_list()
        except Exception as e:
            failures.append(("Водители", e))
            _startup_log(f"refresh_drivers_list failed: {e!r}")

        try:
            self.refresh_maintenance_list()
        except Exception as e:
            failures.append(("История ТО", e))
            _startup_log(f"refresh_maintenance_list failed: {e!r}")

        try:
            self.refresh_issues_list()
        except Exception as e:
            failures.append(("Неисправности", e))
            _startup_log(f"refresh_issues_list failed: {e!r}")

        if hasattr(self, 'stats_labels'):
            try:
                self.update_statistics()
            except Exception as e:
                failures.append(("Статистика", e))
                _startup_log(f"update_statistics failed: {e!r}")
        
        # Обновляем список пользователей, если есть права
        if self.auth_manager.has_permission('admin'):
            try:
                self.refresh_users_list()
            except Exception as e:
                failures.append(("Пользователи", e))
                _startup_log(f"refresh_users_list failed: {e!r}")

        if failures:
            try:
                joined = ", ".join(name for name, _ in failures)
                messagebox.showwarning(
                    "Проблема подключения",
                    "Часть данных не удалось загрузить из-за временной ошибки сети/Supabase.\n\n"
                    f"Не обновились: {joined}\n"
                    "Попробуйте снова через 10-20 секунд.",
                )
            except Exception:
                pass

    def refresh_equipment_sheet_preview(self):
        """Обновление тестовой вкладки техники с поклеточной подсветкой."""
        if not self.equipment_sheet_preview:
            return

        rows = []
        paint_plan = []
        self._equipment_preview_row_ids = []
        current_date = datetime.now()

        def parse_level_from_cell(cell_text):
            date_part = self._document_cell_date_prefix(cell_text)
            if not date_part:
                return None
            try:
                dt = datetime.strptime(date_part, '%d.%m.%Y')
                return self._severity_for_days((dt - current_date).days)
            except Exception:
                return None

        # Источник №1: напрямую из БД (водители и неисправности — пакетно, без N+1 запросов)
        try:
            equipment_list = self.db.get_all_equipment()
            batch_ok = False
            try:
                issues_by_eq = self.db.get_open_issues_grouped_by_equipment_id()
                driver_by_eq = self.db.get_active_driver_name_by_equipment_id()
                batch_ok = True
            except Exception:
                issues_by_eq = {}
                driver_by_eq = {}
            for idx, eq in enumerate(equipment_list):
                measurement_type = 'Пробег' if eq['measurement_type'] == 'mileage' else 'Моточасы'
                eid = str(eq['id'])
                if batch_ok:
                    drivers_str = driver_by_eq.get(eid, '-')
                    open_issues = issues_by_eq.get(eid, [])
                else:
                    try:
                        drivers = self.db.get_all_drivers_for_equipment_with_shifts(eq['id'])
                        if drivers:
                            active_driver = next((d for d in drivers if d.get('is_active', False)), None)
                            drivers_str = active_driver['name'] if active_driver else '-'
                        else:
                            drivers_str = '-'
                    except Exception:
                        drivers = self.db.get_equipment_drivers(eq['id'])
                        drivers_str = drivers[0]['name'] if drivers else '-'
                    open_issues = self.db.get_equipment_issues(eq['id'], status='open')
                if open_issues:
                    issues_list = []
                    for issue in open_issues:
                        desc = issue['description'][:30] + ('...' if len(issue['description']) > 30 else '')
                        issues_list.append(desc)
                    issues_str = f"[!] {len(open_issues)}: " + '; '.join(issues_list)
                else:
                    issues_str = '-'

                current_month = datetime.now().month
                is_winter = current_month in [11, 12, 1, 2]
                interval = eq['maintenance_interval_winter'] if is_winter else eq['maintenance_interval_summer']
                next_maintenance = eq['last_maintenance'] + interval
                remaining = next_maintenance - eq['current_value']
                warning_threshold = 50 if eq['measurement_type'] == 'motohours' else 500
                critical_threshold = warning_threshold // 2
                if remaining <= 0 or remaining <= critical_threshold:
                    maintenance_level = 2
                    status = f"[КРИТ] {remaining}"
                elif remaining <= warning_threshold:
                    maintenance_level = 1
                    status = f"[ВНИМ] {remaining}"
                else:
                    maintenance_level = 0
                    status = f"[OK] {remaining}"

                insurance_date_text = self._row_value(eq, 'insurance_date', '')
                diagnostic_date_text = self._row_value(eq, 'diagnostic_card_date', '')
                mkad_text = self._row_value(eq, 'mkad_pass_date', '')
                insurance_cell = self._format_document_cell(insurance_date_text, self._row_value(eq, 'insurance_file_path', ''))
                diagnostic_cell = self._format_document_cell(diagnostic_date_text, self._row_value(eq, 'diagnostic_card_file_path', ''))
                sts_cell = self._format_sts_cell(
                    self._row_value(eq, 'sts_certificate', ''),
                    self._row_value(eq, 'sts_file_path', ''),
                )

                rows.append([
                    idx + 1, eq['name'], eq['sts_pts'], sts_cell, eq['reg_number'],
                    drivers_str, issues_str, measurement_type, eq['last_maintenance'],
                    self._format_current_value_cell(eq['current_value'], self._row_value(eq, 'current_value_updated_at', '')),
                    next_maintenance, status,
                    insurance_cell, diagnostic_cell, mkad_text if mkad_text else '-', eq['service'],
                    (
                        self._format_current_value_cell(
                            self._row_value(eq, 'secondary_current_value', 0),
                            self._row_value(eq, 'secondary_current_value_updated_at', ''),
                        )
                        if self._row_value(eq, 'has_kmu', False)
                        else '-'
                    )
                ])
                self._equipment_preview_row_ids.append(str(eq['id']))

                kmu_level = None
                if self._row_value(eq, 'has_kmu', False):
                    kmu_interval = int(self._row_value(eq, 'secondary_maintenance_interval', 250) or 250)
                    kmu_last_to = int(self._row_value(eq, 'secondary_last_maintenance', 0) or 0)
                    kmu_current = int(self._row_value(eq, 'secondary_current_value', 0) or 0)
                    kmu_remaining = (kmu_last_to + kmu_interval) - kmu_current
                    if kmu_remaining <= 50:
                        kmu_level = 2
                    elif kmu_remaining <= 80:
                        kmu_level = 1

                paint_plan.append((
                    maintenance_level,
                    parse_level_from_cell(insurance_cell),
                    parse_level_from_cell(diagnostic_cell),
                    parse_level_from_cell(mkad_text),
                    kmu_level,
                ))
        except Exception:
            rows = []
            paint_plan = []

        # Источник №2 (fallback): копия из рабочей таблицы
        if not rows and hasattr(self.equipment_tree, 'get_children'):
            for item_id in self.equipment_tree.get_children():
                item = self.equipment_tree.item(item_id)
                values = list(item.get('values', []))
                if len(values) < 17:
                    continue
                rows.append(values[:17])
                self._equipment_preview_row_ids.append(str(item_id))
                status_text = str(values[11])
                if "[!]" in status_text or "[КРИТ]" in status_text:
                    maintenance_level = 2
                elif "[ВНИМ]" in status_text:
                    maintenance_level = 1
                else:
                    maintenance_level = 0
                paint_plan.append((
                    maintenance_level,
                    parse_level_from_cell(values[12]),
                    parse_level_from_cell(values[13]),
                    parse_level_from_cell(values[14]),
                    None,
                ))

        self.equipment_sheet_preview.headers(list(self.equipment_columns), reset_col_positions=True, redraw=False)
        self.equipment_sheet_preview.set_sheet_data(rows, reset_col_positions=True, reset_row_positions=True)
        try:
            self.equipment_sheet_preview.refresh()
        except Exception:
            pass
        try:
            self.equipment_sheet_preview.dehighlight("all")
        except Exception:
            pass

        for row_idx, levels in enumerate(paint_plan):
            self._highlight_sheet_preview_cell(row_idx, 11, levels[0])
            self._highlight_sheet_preview_cell(row_idx, 12, levels[1])
            self._highlight_sheet_preview_cell(row_idx, 13, levels[2])
            self._highlight_sheet_preview_cell(row_idx, 14, levels[3])
            if len(levels) > 4:
                self._highlight_sheet_preview_cell(row_idx, 16, levels[4])

        self._reapply_equipment_sheet_column_widths()

    def _reapply_equipment_sheet_column_widths(self):
        """После полного обновления таблицы tksheet сбрасывает ширины — подтягиваем из настроек."""
        if not self.equipment_sheet_preview:
            return
        try:
            import json
            widths_json = self.db.get_setting('equipment_column_widths')
            if not widths_json:
                return
            widths = json.loads(widths_json)
            for idx, col in enumerate(self.equipment_columns):
                if col in widths:
                    try:
                        self.equipment_sheet_preview.column_width(idx, int(widths[col]), redraw=False)
                    except Exception:
                        pass
        except Exception:
            pass

    def _highlight_sheet_preview_cell(self, row_index, col_index, level):
        if level is None:
            return
        bg = '#d8f5d0'
        if level == 2:
            bg = '#ffd0d0'
        elif level == 1:
            bg = '#fff4b8'
        try:
            self.equipment_sheet_preview.highlight_cells(row=row_index, column=col_index, fg='black', bg=bg)
        except Exception:
            pass
    
    def save_column_widths(self, event=None):
        """Сохранение текущих ширин столбцов"""
        try:
            if getattr(self, '_is_dragging_equipment', False):
                return

            widths = {}
            if self.equipment_sheet_preview is not None:
                current_widths = self.equipment_sheet_preview.get_column_widths()
                for idx, col in enumerate(self.equipment_columns):
                    widths[col] = int(current_widths[idx]) if idx < len(current_widths) else 120
            elif getattr(self, 'use_equipment_sheet', False) and self.equipment_tree is not None:
                current_widths = self.equipment_tree.get_column_widths()
                for idx, col in enumerate(self.equipment_columns):
                    widths[col] = int(current_widths[idx]) if idx < len(current_widths) else 120
            elif self.equipment_tree is not None:
                columns = self.equipment_tree['columns']
                for col in columns:
                    width = self.equipment_tree.column(col, 'width')
                    widths[col] = width
            else:
                return
            
            # Сохраняем в настройках как JSON строку
            import json
            self.db.set_setting('equipment_column_widths', json.dumps(widths))
        except Exception as e:
            # Игнорируем ошибки сохранения, чтобы не мешать работе
            pass
    
    def load_column_widths(self):
        """Загрузка сохраненных ширин столбцов"""
        try:
            import json
            widths_json = self.db.get_setting('equipment_column_widths')
            
            if widths_json:
                widths = json.loads(widths_json)
                
                if self.equipment_sheet_preview is not None:
                    for idx, col in enumerate(self.equipment_columns):
                        if col in widths:
                            try:
                                self.equipment_sheet_preview.column_width(idx, int(widths[col]), redraw=False)
                            except Exception:
                                pass
                    try:
                        self.equipment_sheet_preview.refresh()
                    except Exception:
                        pass
                elif getattr(self, 'use_equipment_sheet', False) and self.equipment_tree is not None:
                    for idx, col in enumerate(self.equipment_columns):
                        if col in widths:
                            try:
                                self.equipment_tree.column_width(idx, int(widths[col]), redraw=False)
                            except Exception:
                                pass
                    try:
                        self.equipment_tree.refresh()
                    except Exception:
                        pass
                elif self.equipment_tree is not None:
                    for col, width in widths.items():
                        try:
                            self.equipment_tree.column(col, width=width)
                        except Exception:
                            pass
        except Exception as e:
            # Если не получилось загрузить, используем значения по умолчанию
            pass

    def _bind_treeview_width_persistence(self, tree, setting_key, include_tree=False):
        if tree is None:
            return
        tree.bind(
            '<ButtonRelease-1>',
            lambda _e, t=tree, k=setting_key, it=include_tree: self._save_treeview_column_widths(t, k, it),
            add='+'
        )

    def _save_treeview_column_widths(self, tree, setting_key, include_tree=False):
        try:
            import json
            widths = {}
            if include_tree:
                widths['#0'] = int(tree.column('#0', 'width'))
            for col in tree['columns']:
                widths[col] = int(tree.column(col, 'width'))
            self.db.set_setting(setting_key, json.dumps(widths))
        except Exception:
            pass

    def _load_treeview_column_widths(self, tree, setting_key, include_tree=False):
        if tree is None:
            return
        try:
            import json
            widths_json = self.db.get_setting(setting_key)
            if not widths_json:
                return
            widths = json.loads(widths_json)
            if include_tree and '#0' in widths:
                try:
                    tree.column('#0', width=int(widths['#0']))
                except Exception:
                    pass
            for col in tree['columns']:
                if col in widths:
                    try:
                        tree.column(col, width=int(widths[col]))
                    except Exception:
                        pass
        except Exception:
            pass

    def load_all_column_widths(self):
        """Загрузка ширин колонок для всех таблиц."""
        # В cloud-режиме чтение настроек может зависать при нестабильной сети.
        # Ширины колонок некритичны, поэтому пропускаем этот шаг на старте.
        if getattr(db_config, 'MODE', '') == 'cloud':
            _startup_log("skip load_all_column_widths in cloud mode")
            return
        self.load_column_widths()  # техника
        self._load_treeview_column_widths(self.drivers_tree, 'drivers_column_widths')
        self._load_treeview_column_widths(self.maintenance_tree, 'maintenance_column_widths', include_tree=True)
        self._load_treeview_column_widths(self.issues_tree, 'issues_column_widths', include_tree=True)
        self._load_treeview_column_widths(self.users_tree, 'users_column_widths')
    
    def change_password(self):
        """Диалог смены пароля"""
        dialog = ChangePasswordDialog(self.root, self.auth_manager)
        if dialog.show():
            messagebox.showinfo(
                "Успех",
                "Пароль успешно изменен!",
                parent=self.root
            )
    
    def on_exit(self):
        """Выход из программы"""
        if messagebox.askyesno("Выход", "Вы действительно хотите выйти из программы?"):
            save_window_state(self.root)
            self.auth_manager.logout()
            self.switch_user_requested = False
            self.root.quit()
    
    def switch_user(self):
        """Смена пользователя"""
        if messagebox.askyesno("Смена пользователя", 
                               "Вы действительно хотите сменить пользователя?\n\n"
                               "Текущие несохраненные данные будут потеряны."):
            save_window_state(self.root)
            self.auth_manager.logout()
            self.switch_user_requested = True
            self.root.destroy()
    
    def cleanup_orphan_storage(self):
        """Удаление неиспользуемых объектов в бакете счетов Supabase (ссылки только из БД)."""
        if db_config.MODE != 'cloud':
            messagebox.showinfo(
                "Локальный режим",
                "Очистка Storage доступна только в облачном режиме (MODE=cloud).",
                parent=self.root,
            )
            return
        if not self.auth_manager.has_permission('admin'):
            messagebox.showwarning(
                "Недостаточно прав",
                "Очистка хранилища доступна только администраторам.",
                parent=self.root,
            )
            return
        if not messagebox.askyesno(
            "Подтверждение",
            "Будут удалены файлы в облачном хранилище счетов, на которые "
            "нет ссылок в базе данных (устаревшие вложения после замены).\n\n"
            "Продолжить?",
            parent=self.root,
        ):
            return
        try:
            result = self.db.cleanup_orphan_invoice_storage()
        except Exception as e:
            messagebox.showerror(
                "Ошибка",
                f"Не удалось выполнить очистку: {e}",
                parent=self.root,
            )
            return
        if result.get('skipped'):
            messagebox.showinfo(
                "Очистка",
                "В локальном режиме очистка Storage не выполняется.",
                parent=self.root,
            )
            return
        deleted = result.get('deleted', 0)
        orphans = result.get('orphans_found', 0)
        refs = result.get('referenced_in_db', 0)
        errors = result.get('errors') or []
        msg = (
            f"Удалено файлов: {deleted} из {orphans} найденных «осиротевших».\n"
            f"Ссылок на файлы в базе: {refs}."
        )
        if errors:
            msg += "\n\nОшибки при удалении (первые):\n" + "\n".join(errors[:8])
            messagebox.showwarning("Результат очистки", msg, parent=self.root)
        else:
            messagebox.showinfo("Результат очистки", msg, parent=self.root)
    
    def show_settings(self):
        """Показ окна настроек"""
        dialog = SettingsDialog(self.root, self.db, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    
    def show_about(self):
        """Показ информации о программе"""
        messagebox.showinfo("О программе", 
                          "Maintenance Helper\nВерсия 1.0\n\n"
                          "Программа для отслеживания технического обслуживания техники,\n"
                          "управления водителями и регистрации неисправностей.\n\n"
                          "© 2026")


_instance_lock_file = None


def acquire_single_instance_lock():
    """Запрет второго запуска приложения."""
    global _instance_lock_file
    lock_path = os.path.join(tempfile.gettempdir(), "maintenance_helper.lock")
    f = open(lock_path, "a+")
    if sys.platform == 'win32':
        import msvcrt
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            f.close()
            return False

        def _release():
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
            try:
                f.close()
            except Exception:
                pass
        atexit.register(_release)
    _instance_lock_file = f
    return True


def _startup_log(message):
    """Пишет служебный лог старта в temp для диагностики зависаний EXE."""
    try:
        log_path = os.path.join(tempfile.gettempdir(), "ask_startup.log")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
    except Exception:
        pass


# Запуск приложения
if __name__ == '__main__':
    try:
        _startup_log("app start")
        enable_windows_per_monitor_dpi()
        _startup_log("dpi initialized")
        if not acquire_single_instance_lock():
            _startup_log("second instance blocked")
            _tmp_root = tk.Tk()
            _tmp_root.withdraw()
            messagebox.showwarning("Уже запущено", "Приложение уже открыто. Разрешен только один экземпляр.")
            _tmp_root.destroy()
            sys.exit(0)
        _startup_log("single-instance lock acquired")
        # Инициализация базы данных
        db = Database()
        _startup_log("database initialized")
        
        # Создание менеджера авторизации
        auth_manager = AuthManager(db)
        _startup_log("auth manager initialized")
        
        # Флаг первого запуска для поддержки автоматического входа
        first_run = True
        
        # Цикл для поддержки смены пользователя
        while True:
            _startup_log(f"show login dialog (auto={first_run})")
            # Показ диалога входа (с автоматическим входом только при первом запуске)
            login_dialog = LoginDialog(auth_manager)
            if not login_dialog.show(auto_login=first_run):
                _startup_log("login cancelled; exit")
                # Если отмена входа - выход из программы
                break
            
            # После первого входа отключаем автоматический вход
            first_run = False
            
            # Создание главного окна
            _startup_log("creating main window")
            root = tk.Tk()
            apply_tk_display_scaling(root)
            configure_global_ui_style(root)
            load_window_state(root)
            app = MaintenanceApp(root, auth_manager)
            
            # Обработка закрытия окна
            root.protocol("WM_DELETE_WINDOW", app.on_exit)
            _startup_log("enter mainloop")
            root.mainloop()
            _startup_log("mainloop exited")
            
            # Проверка, была ли запрошена смена пользователя
            if not app.switch_user_requested:
                _startup_log("switch user not requested; exit")
                # Если нет - выход из программы
                break
    except Exception as e:
        _startup_log(f"fatal startup error: {e!r}")
        try:
            _tmp_root = tk.Tk()
            _tmp_root.withdraw()
            messagebox.showerror(
                "Ошибка запуска",
                "Приложение не смогло запуститься.\n"
                f"Текст ошибки: {e}\n\n"
                "Подробности в файле: %TEMP%\\ask_startup.log",
            )
            _tmp_root.destroy()
        except Exception:
            pass
        raise
