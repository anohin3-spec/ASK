"""
Модуль для обработки горячих клавиш в полях ввода
"""
import tkinter as tk
from tkinter import ttk


def _handle_ctrl_shortcuts(event, widget):
    """Универсальная обработка Ctrl-шорткатов для RU/EN раскладки"""
    keysym = (event.keysym or '').lower()
    char = (event.char or '').lower()
    keycode = event.keycode

    select_all_keys = {'a', 'ф'}
    copy_keys = {'c', 'с'}
    paste_keys = {'v', 'м'}
    cut_keys = {'x', 'ч'}

    is_select_all = keysym in select_all_keys or char in select_all_keys or keycode == 65
    is_copy = keysym in copy_keys or char in copy_keys or keycode == 67
    is_paste = keysym in paste_keys or char in paste_keys or keycode == 86
    is_cut = keysym in cut_keys or char in cut_keys or keycode == 88

    if not (is_select_all or is_copy or is_paste or is_cut):
        return None

    if is_select_all:
        if isinstance(widget, tk.Text):
            widget.tag_add('sel', '1.0', 'end')
            widget.mark_set('insert', '1.0')
            widget.see('insert')
        else:
            widget.select_range(0, tk.END)
        return 'break'

    if is_copy:
        widget.event_generate('<<Copy>>')
        return 'break'

    if is_paste:
        widget.event_generate('<<Paste>>')
        return 'break'

    if is_cut:
        widget.event_generate('<<Cut>>')
        return 'break'

    return None


def bind_entry_shortcuts(widget):
    """
    Привязка стандартных горячих клавиш для полей ввода
    
    Поддерживаемые комбинации:
    - Ctrl+A: Выделить всё
    - Ctrl+C: Копировать
    - Ctrl+V: Вставить
    - Ctrl+X: Вырезать
    
    Args:
        widget: Entry, ttk.Entry или Text виджет
    """
    if isinstance(widget, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text)):
        widget.bind('<Control-KeyPress>', lambda e, w=widget: _handle_ctrl_shortcuts(e, w), add='+')


def bind_date_dd_mm_yyyy(widget):
    """
    Ввод даты ДД.ММ.ГГГГ: цифры набираются подряд, точки ставятся автоматически.
    """
    if not isinstance(widget, (tk.Entry, ttk.Entry)):
        return

    def _reformat(_event=None):
        raw = widget.get()
        digits = ''.join(c for c in raw if c.isdigit())[:8]
        if not digits:
            if raw:
                widget.delete(0, tk.END)
            return
        if len(digits) <= 2:
            formatted = digits
        elif len(digits) <= 4:
            formatted = digits[:2] + '.' + digits[2:]
        else:
            formatted = digits[:2] + '.' + digits[2:4] + '.' + digits[4:]
        if formatted != raw:
            widget.delete(0, tk.END)
            widget.insert(0, formatted)
        widget.icursor(tk.END)

    widget.bind('<KeyRelease>', _reformat, add='+')


def bind_all_entries(parent):
    """
    Автоматически применяет горячие клавиши ко всем Entry и Text виджетам в окне
    
    Args:
        parent: Родительский виджет (окно, фрейм и т.д.)
    """
    for child in parent.winfo_children():
        if isinstance(child, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text)):
            bind_entry_shortcuts(child)
        elif hasattr(child, 'winfo_children'):
            # Рекурсивно обработать дочерние виджеты
            bind_all_entries(child)
