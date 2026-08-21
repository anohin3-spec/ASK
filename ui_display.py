"""
Экран и интерфейс: DPI Windows, масштаб Tk, сохранение геометрии главного окна.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk


def _state_path() -> Path:
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or str(Path.home() / 'AppData' / 'Local')
    else:
        base = os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')
    d = Path(base) / 'MaintenanceHelper'
    d.mkdir(parents=True, exist_ok=True)
    return d / 'window_state.json'


def enable_windows_per_monitor_dpi() -> None:
    """Вызывать до tk.Tk(): убирает «мыльность» при масштабе Windows (125%, 150%…)."""
    if sys.platform != 'win32':
        return
    import ctypes
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def apply_tk_display_scaling(root: tk.Tk) -> None:
    """Подгоняет tk scaling под фактический DPI экрана (после создания корня)."""
    try:
        root.update_idletasks()
        dpi = float(root.winfo_fpixels('1i'))
        if dpi > 1:
            scale = dpi / 72.0
            root.tk.call('tk', 'scaling', scale)
    except (tk.TclError, ValueError, ZeroDivisionError):
        pass


def ui_font(size: int = 10, weight: str = 'normal') -> tuple:
    """Системный шрифт: на Windows — Segoe UI (лучше смотрится при разном DPI)."""
    if sys.platform == 'win32':
        fam = 'Segoe UI'
    elif sys.platform == 'darwin':
        fam = 'Helvetica Neue'
    else:
        fam = 'Arial'
    if weight and weight != 'normal':
        return (fam, size, weight)
    return (fam, size)


def _apply_named_tk_fonts(family: str, size: int) -> None:
    """Именованные шрифты Tk (меню, текст); нельзя option_add('Segoe UI 10') — пробел ломает Tcl."""
    for name in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont'):
        try:
            fn = tkfont.nametofont(name)
            fn.configure(family=family, size=size)
        except tk.TclError:
            pass


def configure_global_ui_style(root: tk.Tk) -> None:
    """Базовые шрифты ttk и виджетов Tk без правки каждого диалога."""
    f = ui_font(10)
    f_bold = ui_font(10, 'bold')
    _apply_named_tk_fonts(f[0], int(f[1]))
    style = ttk.Style(root)
    try:
        if sys.platform == 'win32':
            style.theme_use('vista')
    except tk.TclError:
        pass
    style.configure('.', font=f)
    style.configure('TLabel', font=f)
    style.configure('TButton', font=f)
    style.configure('TEntry', font=f)
    style.configure('TCombobox', font=f)
    style.configure('Treeview', font=f, rowheight=max(22, int(f[1]) + 12))
    style.configure('Treeview.Heading', font=f_bold)
    style.configure('TNotebook.Tab', font=f)
    style.configure('TLabelframe.Label', font=f)


_GEO_RE = re.compile(r'^(\d+)x(\d+)([+-]\d+)([+-]\d+)$')


def _clamp_geometry(geom: str, screen_w: int, screen_h: int) -> Optional[str]:
    m = _GEO_RE.match(geom.strip())
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    xs, ys = m.group(3), m.group(4)
    # Только разумные границы размера; позицию не трогаем (второй монитор, отрицательные X/Y).
    w = max(480, min(w, max(screen_w * 3, 480)))
    h = max(360, min(h, max(screen_h * 3, 360)))
    return f'{w}x{h}{xs}{ys}'


def load_window_state(root: tk.Tk) -> None:
    """Восстанавливает размер/позицию (и развёрнутое состояние на Windows)."""
    path = _state_path()
    if not path.is_file():
        root.geometry('1400x800')
        return
    try:
        data: Dict[str, Any] = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        root.geometry('1400x800')
        return
    geom = data.get('geometry')
    if not geom or not isinstance(geom, str):
        root.geometry('1400x800')
        return
    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    fixed = _clamp_geometry(geom, sw, sh)
    if fixed:
        root.geometry(fixed)
    else:
        root.geometry('1400x800')
    if data.get('zoomed') and sys.platform == 'win32':
        try:
            root.state('zoomed')
        except tk.TclError:
            pass


def save_window_state(root: tk.Tk) -> None:
    """Сохраняет геометрию в %LOCALAPPDATA%\\MaintenanceHelper\\window_state.json."""
    try:
        root.update_idletasks()
        zoomed = False
        if sys.platform == 'win32':
            try:
                zoomed = root.state() == 'zoomed'
            except tk.TclError:
                pass
        data = {
            'geometry': root.winfo_geometry(),
            'zoomed': zoomed,
        }
        path = _state_path()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding='utf-8')
    except (OSError, tk.TclError, TypeError):
        pass
