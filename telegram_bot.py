"""
Telegram-бот для просмотра данных по технике/неисправностям.
"""
from __future__ import annotations

import json
import importlib.util
import os
import re
import tempfile
import urllib.request
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from database import Database, MODE


load_dotenv()

TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    or os.getenv("BOT_TOKEN", "").strip()
    or os.getenv("API_TOKEN", "").strip()
)
ALLOWED_IDS_RAW = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").strip()
COMPANY_ID = os.getenv("TELEGRAM_COMPANY_ID", "").strip()
ACCESS_CODE = os.getenv("TELEGRAM_ACCESS_CODE", "").strip()
OWNER_IDS_RAW = os.getenv("TELEGRAM_OWNER_USER_IDS", "").strip()
ADMIN_PASSWORD = os.getenv("TELEGRAM_ADMIN_PASSWORD", "12345").strip()
WEEKLY_BROADCAST_WEEKDAY = int(os.getenv("TELEGRAM_WEEKLY_BROADCAST_WEEKDAY", "3") or "3")  # 0=Mon, 3=Thu
WEEKLY_BROADCAST_HOUR = int(os.getenv("TELEGRAM_WEEKLY_BROADCAST_HOUR", "12") or "12")
WEEKLY_BROADCAST_MINUTE = int(os.getenv("TELEGRAM_WEEKLY_BROADCAST_MINUTE", "0") or "0")
WEEKLY_BROADCAST_INTERVAL_WEEKS = int(os.getenv("TELEGRAM_WEEKLY_BROADCAST_INTERVAL_WEEKS", "2") or "2")
REMINDER_INTERVAL_MINUTES = int(os.getenv("TELEGRAM_REMINDER_INTERVAL_MINUTES", "30") or "30")
SESSIONS_PATH = os.path.join(os.path.dirname(__file__), "telegram_sessions.json")
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")


def _split_invoice_paths(value: Any) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    normalized = raw.replace("\r", "\n").replace(";", "\n")
    return [p.strip() for p in normalized.split("\n") if p.strip()]


def _fmt_iso(value: Any) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(value)


def _fmt_value_with_update(eq: dict[str, Any]) -> str:
    unit = "км" if str(eq.get("measurement_type") or "mileage") != "motohours" else "м/ч"
    value = str(eq.get("current_value", "-"))
    updated = str(eq.get("current_value_updated_at") or "").strip()
    return f"{value} {unit} (Обновлено {updated})" if updated else f"{value} {unit}"


def _fmt_secondary_value(eq: dict[str, Any]) -> str:
    value = str(eq.get("secondary_current_value", "0"))
    updated = str(eq.get("secondary_current_value_updated_at") or "").strip()
    return f"{value} м/ч (Обновлено {updated})" if updated else f"{value} м/ч"


def _allowed_ids() -> set[int]:
    out: set[int] = set()
    for part in ALLOWED_IDS_RAW.split(","):
        p = part.strip()
        if not p:
            continue
        try:
            out.add(int(p))
        except ValueError:
            pass
    return out


def _owner_ids() -> set[int]:
    out: set[int] = set()
    for part in OWNER_IDS_RAW.split(","):
        p = part.strip()
        if not p:
            continue
        try:
            out.add(int(p))
        except ValueError:
            pass
    return out


_EMPTY_SESSIONS = {
    "allowed_user_ids": [],
    "driver_bindings": {},
    "owner_mode_overrides": {},
    "admin_user_ids": [],
    "pending_value_requests": {},
}
# In-memory sessions: нужны на хостинге, где запись telegram_sessions.json может быть недоступна.
_SESSIONS_CACHE: dict[str, Any] | None = None


def _normalize_sessions(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}
    out = dict(_EMPTY_SESSIONS)
    out.update(payload)
    out.setdefault("allowed_user_ids", [])
    out.setdefault("driver_bindings", {})
    out.setdefault("owner_mode_overrides", {})
    out.setdefault("admin_user_ids", [])
    out.setdefault("pending_value_requests", {})
    return out


def _load_sessions() -> dict[str, Any]:
    global _SESSIONS_CACHE
    if _SESSIONS_CACHE is not None:
        return _SESSIONS_CACHE
    if not os.path.exists(SESSIONS_PATH):
        _SESSIONS_CACHE = dict(_EMPTY_SESSIONS)
        return _SESSIONS_CACHE
    try:
        with open(SESSIONS_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        _SESSIONS_CACHE = _normalize_sessions(payload)
        return _SESSIONS_CACHE
    except Exception:
        _SESSIONS_CACHE = dict(_EMPTY_SESSIONS)
        return _SESSIONS_CACHE


def _save_sessions(payload: dict[str, Any]) -> None:
    global _SESSIONS_CACHE
    normalized = _normalize_sessions(payload)
    _SESSIONS_CACHE = normalized
    try:
        with open(SESSIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)
    except Exception as e:
        # На Docker/хостинге файл может быть read-only — продолжаем в памяти.
        print(f"Telegram bot: sessions kept in memory only ({e})")


def _load_granted_ids() -> set[int]:
    payload = _load_sessions()
    ids = payload.get("allowed_user_ids", [])
    out = set()
    for x in ids:
        try:
            out.add(int(x))
        except Exception:
            pass
    return out


def _save_granted_ids(ids: set[int]) -> None:
    payload = _load_sessions()
    payload["allowed_user_ids"] = sorted(list(ids))
    _save_sessions(payload)


def _set_driver_binding(user_id: int, binding: dict[str, Any]) -> None:
    payload = _load_sessions()
    bindings = payload.get("driver_bindings", {})
    bindings[str(user_id)] = binding
    payload["driver_bindings"] = bindings
    _save_sessions(payload)


def _get_driver_binding(user_id: int) -> dict[str, Any] | None:
    payload = _load_sessions()
    bindings = payload.get("driver_bindings", {})
    binding = bindings.get(str(user_id))
    return binding if isinstance(binding, dict) else None


def _clear_driver_binding(user_id: int) -> None:
    payload = _load_sessions()
    bindings = payload.get("driver_bindings", {})
    if str(user_id) in bindings:
        del bindings[str(user_id)]
    payload["driver_bindings"] = bindings
    _save_sessions(payload)


def _set_owner_mode_override(user_id: int, mode: str | None) -> None:
    payload = _load_sessions()
    overrides = payload.get("owner_mode_overrides", {})
    key = str(user_id)
    if mode is None:
        overrides.pop(key, None)
    else:
        overrides[key] = mode
    payload["owner_mode_overrides"] = overrides
    _save_sessions(payload)


def _is_admin_user(user_id: int) -> bool:
    payload = _load_sessions()
    raw = payload.get("admin_user_ids", [])
    ids = set()
    for x in raw:
        try:
            ids.add(int(x))
        except Exception:
            pass
    return int(user_id) in ids


def _set_admin_user(user_id: int, enabled: bool) -> None:
    payload = _load_sessions()
    raw = payload.get("admin_user_ids", [])
    ids = set()
    for x in raw:
        try:
            ids.add(int(x))
        except Exception:
            pass
    if enabled:
        ids.add(int(user_id))
    else:
        ids.discard(int(user_id))
    payload["admin_user_ids"] = sorted(list(ids))
    _save_sessions(payload)


def _get_owner_mode_override(user_id: int) -> str | None:
    payload = _load_sessions()
    overrides = payload.get("owner_mode_overrides", {})
    mode = overrides.get(str(user_id))
    if mode in ("owner", "driver"):
        return mode
    return None


def _is_allowed(user_id: int) -> bool:
    static_ids = _allowed_ids()
    if user_id in static_ids:
        return True
    if ACCESS_CODE:
        return user_id in _load_granted_ids()
    if not static_ids:
        return True
    return False


class FleetBot:
    def __init__(self) -> None:
        self.db = Database()
        if MODE == "cloud" and hasattr(self.db, "set_company"):
            self._configure_company()

    def _configure_company(self) -> None:
        """Настраивает company_id для cloud-режима, даже если в .env введено не-UUID."""
        if COMPANY_ID and UUID_RE.match(COMPANY_ID):
            self.db.set_company(COMPANY_ID)
            return
        try:
            result = self.db.client.table("companies").select("id").limit(1).execute()
            if result.data:
                detected = str(result.data[0].get("id", "")).strip()
                if detected and UUID_RE.match(detected):
                    self.db.set_company(detected)
                    print(f"Telegram bot: auto-detected company_id={detected}")
                    return
        except Exception as e:
            print(f"Telegram bot: failed to auto-detect company_id: {e}")
        # fallback: оставляем company_id как есть в DatabaseCloud (дефолтное).

    def _try_switch_company_from_equipment(self) -> bool:
        """Пробует взять company_id из существующей техники и переключиться."""
        if MODE != "cloud" or not hasattr(self.db, "set_company"):
            return False
        try:
            result = self.db.client.table("equipment").select("company_id").limit(1).execute()
            if result.data:
                cid = str(result.data[0].get("company_id", "")).strip()
                if cid and UUID_RE.match(cid):
                    self.db.set_company(cid)
                    print(f"Telegram bot: switched company_id from equipment -> {cid}")
                    return True
        except Exception as e:
            print(f"Telegram bot: cannot detect company_id from equipment: {e}")
        return False

    def _is_owner_user(self, user_id: int) -> bool:
        override = _get_owner_mode_override(int(user_id))
        if override == "driver":
            return False
        if override == "owner":
            return True
        if _is_admin_user(int(user_id)):
            return True
        return int(user_id) in _owner_ids()

    def _set_pending_value_request(self, user_id: int, active: bool) -> None:
        payload = _load_sessions()
        pending = payload.get("pending_value_requests", {})
        if not isinstance(pending, dict):
            pending = {}
        key = str(int(user_id))
        if active:
            pending[key] = {"requested_at": datetime.now().isoformat()}
        else:
            pending.pop(key, None)
        payload["pending_value_requests"] = pending
        _save_sessions(payload)

    def _pending_value_request_ids(self) -> list[int]:
        payload = _load_sessions()
        pending = payload.get("pending_value_requests", {})
        out: list[int] = []
        if isinstance(pending, dict):
            for key in pending.keys():
                try:
                    out.append(int(key))
                except Exception:
                    pass
        return out

    def _resolve_driver_snapshot(self, driver_id: str) -> dict[str, str]:
        driver_name = "-"
        equipment_text = "не привязана"
        try:
            driver = self.db.get_driver(driver_id)
        except Exception:
            driver = None
        if driver:
            try:
                driver_name = str(driver.get("name", "-"))
            except Exception:
                driver_name = str(driver["name"]) if driver and "name" in driver else "-"
        try:
            equipment_list = self.db.get_driver_equipment(driver_id) or []
        except Exception:
            equipment_list = []
        if equipment_list:
            eq = equipment_list[0]
            try:
                equipment_text = f"{eq.get('name', '-')} ({eq.get('reg_number', '-')})"
            except Exception:
                equipment_text = "не привязана"
        return {"driver_name": driver_name, "equipment_text": equipment_text}

    async def _send_equipment_list(
        self,
        target,
        context: ContextTypes.DEFAULT_TYPE,
        text: str = "Выберите технику:",
        allow_edit: bool = False,
    ):
        equipment = self.db.get_all_equipment() or []
        if not equipment and self._try_switch_company_from_equipment():
            equipment = self.db.get_all_equipment() or []
        if not equipment:
            await target.reply_text("Техника не найдена для текущей компании. Проверьте TELEGRAM_COMPANY_ID в .env.")
            return
        keyboard = []
        for eq in equipment:
            eid = str(eq.get("id"))
            label = f"{eq.get('reg_number', '-')} • {eq.get('name', '-')}"
            keyboard.append([InlineKeyboardButton(label[:64], callback_data=f"eq:{eid}")])
        markup = InlineKeyboardMarkup(keyboard)
        # В callback-режиме переиспользуем текущее сообщение, чтобы не плодить историю.
        if allow_edit:
            try:
                await target.edit_text(text, reply_markup=markup)
                return
            except Exception:
                pass
        await target.reply_text(text, reply_markup=markup)

    async def _cleanup_transient_messages(self, context: ContextTypes.DEFAULT_TYPE):
        """Удаляет ранее отправленные ботом вложения/доп. сообщения."""
        items = context.user_data.get("transient_messages", [])
        if not items:
            return
        bot = context.bot
        kept = []
        for item in items:
            chat_id = item.get("chat_id")
            mid = item.get("message_id")
            if chat_id is None or mid is None:
                continue
            try:
                await bot.delete_message(chat_id=chat_id, message_id=mid)
            except Exception as e:
                # Иногда Telegram не дает удалить очень старые/чужие сообщения — оставляем в очереди один ретрай.
                print(f"Telegram bot: cannot delete message chat_id={chat_id}, message_id={mid}: {e}")
                kept.append({"chat_id": chat_id, "message_id": mid})
        context.user_data["transient_messages"] = kept[-20:]

    async def _remember_transient_message(self, context: ContextTypes.DEFAULT_TYPE, message) -> None:
        if not message:
            return
        items = context.user_data.get("transient_messages", [])
        items.append({"chat_id": message.chat_id, "message_id": message.message_id})
        # Ограничиваем буфер, чтобы не разрастался.
        context.user_data["transient_messages"] = items[-20:]

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user:
            return
        if not user or not _is_allowed(user.id):
            kb = [[InlineKeyboardButton("Вход", callback_data="auth:start")]]
            await update.message.reply_text(
                "Чтобы войти, нажмите кнопку ниже.",
                reply_markup=InlineKeyboardMarkup(kb),
            )
            return
        await self._cleanup_transient_messages(context)
        if self._is_owner_user(user.id):
            await update.message.reply_text("Режим владельца активен.")
            await self._send_equipment_list(update.message, context)
            return

        binding = _get_driver_binding(user.id)
        if not binding:
            await update.message.reply_text("Выберите себя из списка водителей:")
            await self._send_driver_picker(update.message)
            return
        snapshot = self._resolve_driver_snapshot(str(binding.get("driver_id", "")))

        await update.message.reply_text(
            f"Режим водителя активирован.\n"
            f"Вы: {snapshot.get('driver_name', '-')}\n"
            f"Ваша техника: {snapshot.get('equipment_text', '-')}"
        )
        await self._send_driver_main_menu(update, context)

    async def login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user:
            return
        if not ACCESS_CODE:
            await update.message.reply_text("Код доступа не настроен. Вход по /login отключен.")
            return
        if not context.args:
            await update.message.reply_text("Использование: /login <код>")
            return
        code = str(context.args[0]).strip()
        if code != ACCESS_CODE:
            await update.message.reply_text("Неверный код.")
            return
        ids = _load_granted_ids()
        ids.add(int(user.id))
        _save_granted_ids(ids)
        context.user_data["awaiting_role_choice"] = True
        kb = [
            [InlineKeyboardButton("🚚 Водитель", callback_data="auth:role:driver")],
            [InlineKeyboardButton("🛡️ Администрация", callback_data="auth:role:admin")],
        ]
        await update.message.reply_text(
            "Вход выполнен. Выберите режим:",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    async def logout(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or not update.message:
            return
        # Максимально очищаем бот-сообщения в текущем чате.
        await self._cleanup_transient_messages(context)
        ids = _load_granted_ids()
        if int(user.id) in ids:
            ids.remove(int(user.id))
            _save_granted_ids(ids)
        _clear_driver_binding(int(user.id))
        _set_owner_mode_override(int(user.id), None)
        _set_admin_user(int(user.id), False)
        self._set_pending_value_request(int(user.id), False)
        context.user_data.pop("awaiting_access_code", None)
        context.user_data.pop("awaiting_role_choice", None)
        context.user_data.pop("awaiting_admin_password", None)
        context.user_data.pop("awaiting_value_input", None)
        # Пытаемся удалить сообщение пользователя с /logout (Telegram может не дать, это ок).
        try:
            await update.message.delete()
        except Exception:
            pass
        kb = [[InlineKeyboardButton("Вход", callback_data="auth:start")]]
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="Вы вышли из системы.\nНажмите кнопку ниже для нового входа.",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    async def myid(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user:
            return
        await update.message.reply_text(f"Ваш Telegram ID: {user.id}")

    async def as_driver_test(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or not update.message:
            return
        if int(user.id) not in _owner_ids():
            await update.message.reply_text("Команда доступна только владельцу.")
            return
        arg = (context.args[0].strip().lower() if context.args else "status")
        if arg in ("on", "driver", "1"):
            _set_owner_mode_override(int(user.id), "driver")
            await update.message.reply_text(
                "Тест-режим водителя включен.\n"
                "Теперь вы будете как водитель.\n"
                "Нажмите /start."
            )
            return
        if arg in ("off", "owner", "0"):
            _set_owner_mode_override(int(user.id), "owner")
            await update.message.reply_text(
                "Режим владельца включен.\n"
                "Нажмите /start."
            )
            return
        if arg in ("clear", "reset"):
            _set_owner_mode_override(int(user.id), None)
            await update.message.reply_text(
                "Override очищен. Режим снова берется из TELEGRAM_OWNER_USER_IDS.\n"
                "Нажмите /start."
            )
            return
        current = _get_owner_mode_override(int(user.id))
        effective = "owner" if self._is_owner_user(int(user.id)) else "driver"
        await update.message.reply_text(
            f"Override: {current or '-'}\n"
            f"Текущий режим: {effective}\n\n"
            "Использование:\n"
            "/as_driver_test on — как водитель\n"
            "/as_driver_test off — как владелец\n"
            "/as_driver_test clear — по .env"
        )

    async def send_value_request_now(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or not update.message:
            return
        if not self._is_owner_user(int(user.id)):
            await update.message.reply_text("Команда доступна только владельцу.")
            return
        sent = await self._broadcast_value_requests_once(context)
        await update.message.reply_text(f"Готово. Отправлено уведомлений: {sent}")

    async def send_value_request_me(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or not update.message:
            return
        if not _is_allowed(int(user.id)):
            await update.message.reply_text("Доступ запрещен.")
            return
        binding = _get_driver_binding(int(user.id))
        if not binding:
            await update.message.reply_text("Вы не привязаны как водитель. Сначала пройдите /start и выбор водителя.")
            return
        snapshot = self._resolve_driver_snapshot(str(binding.get("driver_id", "")))
        kb = [[InlineKeyboardButton("Ввести текущий пробег", callback_data="val:req")]]
        try:
            await context.bot.send_message(
                chat_id=int(user.id),
                text=f"{snapshot.get('driver_name', 'Водитель')}, пожалуйста введите текущий пробег техники.",
                reply_markup=InlineKeyboardMarkup(kb),
            )
            await update.message.reply_text("Тестовый запрос отправлен вам ✅")
        except Exception as e:
            await update.message.reply_text(f"Не удалось отправить тестовый запрос: {e}")

    async def on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        try:
            await q.answer()
        except Exception:
            # Просроченный callback (кнопка нажата слишком поздно) — просто игнорируем.
            return
        data = q.data or ""
        if data == "auth:start":
            context.user_data["awaiting_access_code"] = True
            await q.edit_message_text("Введите код доступа (например, ASK1):")
            return
        if data == "auth:role:driver":
            context.user_data["awaiting_role_choice"] = False
            _set_admin_user(int(q.from_user.id), False)
            _set_owner_mode_override(int(q.from_user.id), "driver")
            await self._send_driver_picker(q.message, allow_edit=True)
            return
        if data == "auth:role:admin":
            context.user_data["awaiting_role_choice"] = False
            context.user_data["awaiting_admin_password"] = True
            await q.edit_message_text("Введите пароль администратора:")
            return
        user = update.effective_user
        if not user or not _is_allowed(user.id):
            tip = "Доступ запрещен."
            if ACCESS_CODE:
                tip += "\n\nВыполните вход: /login <код>"
            await q.edit_message_text(tip)
            return
        await self._cleanup_transient_messages(context)
        if data.startswith("auth:driver:"):
            driver_id = data.split(":", 2)[2]
            await self._confirm_driver_binding(q, context, driver_id)
            return
        if data.startswith("auth:confirm:"):
            driver_id = data.split(":", 2)[2]
            await self._apply_driver_binding(q, context, driver_id)
            return
        if data == "auth:pick":
            await self._send_driver_picker(q.message, allow_edit=True)
            return
        if data == "val:req":
            await self._show_value_request_targets(q, context)
            return
        if data.startswith("val:eq:"):
            await self._show_counter_picker(q, context, data.split(":", 2)[2])
            return
        if data.startswith("val:set:"):
            parts = data.split(":", 3)
            if len(parts) < 4:
                await q.answer("Некорректная кнопка", show_alert=True)
                return
            await self._start_value_input(q, context, parts[2], parts[3])
            return
        if data == "drv:menu":
            kb = [
                [InlineKeyboardButton("Ввести текущий пробег", callback_data="val:req")],
                [InlineKeyboardButton("Открыть список техники", callback_data="eq:list")],
                [InlineKeyboardButton("Моя машина", callback_data="drv:mycar")],
            ]
            await q.edit_message_text("Главное меню водителя:", reply_markup=InlineKeyboardMarkup(kb))
            return
        if data == "drv:mycar":
            binding = _get_driver_binding(int(q.from_user.id))
            if not binding:
                await q.edit_message_text("Сначала авторизуйтесь как водитель: /start")
                return
            rows = self._driver_equipment_rows(str(binding.get("driver_id", "")))
            if not rows:
                await q.edit_message_text("За вами не закреплена техника.")
                return
            eq_id = str(rows[0].get("id", ""))
            if not eq_id:
                await q.edit_message_text("Не удалось определить вашу технику.")
                return
            await self._show_equipment_card(q, eq_id)
            return
        if data == "eq:list":
            await self._send_equipment_list(q.message, context, "Выберите технику:", allow_edit=True)
            return
        if data.startswith("eq:"):
            await self._show_equipment_card(q, data.split(":", 1)[1])
            return
        if data.startswith("doc:"):
            _, doc_type, eq_id = data.split(":", 2)
            await self._send_equipment_doc(q, context, eq_id, doc_type)
            return
        if data.startswith("mnt:list:"):
            await self._show_maintenance_list(q, context, data.split(":", 2)[2])
            return
        if data.startswith("mnt:item:"):
            key = data.split(":", 2)[2]
            m = context.user_data.get("mnt_map", {}) or {}
            payload = m.get(key)
            if not payload:
                await q.answer("Запись устарела. Откройте ТО заново.", show_alert=True)
                return
            eq_id, maint_id = payload
            await self._send_maintenance_invoice(q, context, eq_id, maint_id)
            return
        if data.startswith("iss:list:"):
            await self._show_issues_list(q, data.split(":", 2)[2])
            return
        if data.startswith("iss:item:"):
            await self._show_issue_item(q, data.split(":", 2)[2])
            return
        if data.startswith("iss:inv:"):
            await self._send_issue_invoice(q, context, data.split(":", 2)[2])
            return

    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or not update.message:
            return
        text = (update.message.text or "").strip()
        if not text:
            return
        if context.user_data.get("awaiting_access_code"):
            if not ACCESS_CODE:
                context.user_data["awaiting_access_code"] = False
                await update.message.reply_text("Код доступа не настроен.")
                return
            if text != ACCESS_CODE:
                await update.message.reply_text("Неверный код. Попробуйте еще раз.")
                return
            context.user_data["awaiting_access_code"] = False
            ids = _load_granted_ids()
            ids.add(int(user.id))
            _save_granted_ids(ids)
            context.user_data["awaiting_role_choice"] = True
            kb = [
                [InlineKeyboardButton("🚚 Водитель", callback_data="auth:role:driver")],
                [InlineKeyboardButton("🛡️ Администрация", callback_data="auth:role:admin")],
            ]
            await update.message.reply_text(
                "Выберите режим входа:",
                reply_markup=InlineKeyboardMarkup(kb),
            )
            return
        if context.user_data.get("awaiting_admin_password"):
            if text != ADMIN_PASSWORD:
                await update.message.reply_text("Неверный пароль администратора. Попробуйте еще раз.")
                return
            context.user_data["awaiting_admin_password"] = False
            _set_admin_user(int(user.id), True)
            # Сбрасываем тестовый override=driver, чтобы админ-вход всегда открывал меню всей техники.
            _set_owner_mode_override(int(user.id), "owner")
            await update.message.reply_text("Режим администрации активирован. Нажмите /start")
            return
        pending = context.user_data.get("awaiting_value_input")
        if pending:
            await self._handle_value_input(update, context, pending, text)
            return

    def _driver_equipment_rows(self, driver_id: str) -> list[dict[str, Any]]:
        rows = self.db.get_driver_equipment(driver_id) or []
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                out.append(dict(row))
            except Exception:
                out.append(row)
        return out

    async def _show_value_request_targets(self, q, context: ContextTypes.DEFAULT_TYPE):
        user = q.from_user
        if not user:
            return
        binding = _get_driver_binding(int(user.id))
        if not binding:
            await q.edit_message_text("Сначала выберите себя как водителя: /start")
            return
        rows = self._driver_equipment_rows(str(binding.get("driver_id", "")))
        if not rows:
            await q.edit_message_text("За вами не закреплена техника.")
            return
        kb = []
        for eq in rows[:20]:
            eq_id = str(eq.get("id", ""))
            label = f"{eq.get('reg_number', '-')} • {eq.get('name', '-')}"
            kb.append([InlineKeyboardButton(label[:64], callback_data=f"val:eq:{eq_id}")])
        kb.append([InlineKeyboardButton("Назад", callback_data="eq:list")])
        await q.edit_message_text(
            "По какой технике ввести текущее значение?",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    async def _show_counter_picker(self, q, context: ContextTypes.DEFAULT_TYPE, eq_id: str):
        user = q.from_user
        if not user:
            return
        binding = _get_driver_binding(int(user.id))
        if not binding:
            await q.answer("Сначала авторизуйтесь как водитель", show_alert=True)
            return
        rows = self._driver_equipment_rows(str(binding.get("driver_id", "")))
        allowed_ids = {str(r.get("id", "")) for r in rows}
        if str(eq_id) not in allowed_ids:
            await q.answer("Эта техника не закреплена за вами", show_alert=True)
            return
        eq = self.db.get_equipment(eq_id)
        if not eq:
            await q.answer("Техника не найдена", show_alert=True)
            return
        kb = [
            [InlineKeyboardButton("Пробег транспортного средства", callback_data=f"val:set:{eq_id}:primary")],
        ]
        if bool(eq.get("has_kmu")):
            kb.append([InlineKeyboardButton("Моточасы КМУ", callback_data=f"val:set:{eq_id}:kmu")])
        kb.append([InlineKeyboardButton("Назад к выбору техники", callback_data="val:req")])
        await q.edit_message_text(
            f"Выбрана техника: {eq.get('name', '-')} ({eq.get('reg_number', '-')})\n"
            f"Что обновить?",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    async def _start_value_input(self, q, context: ContextTypes.DEFAULT_TYPE, eq_id: str, counter_type: str):
        eq = self.db.get_equipment(eq_id)
        if not eq:
            await q.answer("Техника не найдена", show_alert=True)
            return
        normalized = "kmu" if str(counter_type).strip().lower() == "kmu" else "primary"
        if normalized == "kmu" and not bool(eq.get("has_kmu")):
            await q.answer("Для этой техники КМУ не включен", show_alert=True)
            return
        prompt = (
            f"Введите текущие моточасы КМУ для {eq.get('reg_number', '-')}:"
            if normalized == "kmu"
            else f"Введите текущий пробег/значение для {eq.get('reg_number', '-')}:"
        )
        context.user_data["awaiting_value_input"] = {
            "equipment_id": str(eq_id),
            "counter_type": normalized,
        }
        kb = [[InlineKeyboardButton("↩️ Назад к выбору счетчика", callback_data=f"val:eq:{eq_id}")]]
        text = (
            f"{prompt}\n\n"
            f"Отправьте одним сообщением только число.\n"
            f"Пример: 302450"
        )
        # Пользователь просил отдельный новый экран: удаляем прошлое меню и отправляем новое сообщение.
        try:
            if q.message:
                await q.message.delete()
        except Exception:
            pass
        if q.message:
            await context.bot.send_message(
                chat_id=q.message.chat_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(kb),
            )
        else:
            await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

    async def _handle_value_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, pending: dict[str, Any], text: str):
        user = update.effective_user
        if not user:
            return
        binding = _get_driver_binding(int(user.id))
        if not binding:
            context.user_data.pop("awaiting_value_input", None)
            await update.message.reply_text("Сессия водителя не найдена. Нажмите /start")
            return
        value_str = "".join(ch for ch in str(text) if ch.isdigit())
        if not value_str:
            await update.message.reply_text("Нужно отправить число, например 302450")
            return
        value = int(value_str)
        eq_id = str(pending.get("equipment_id", ""))
        counter_type = str(pending.get("counter_type", "primary"))
        rows = self._driver_equipment_rows(str(binding.get("driver_id", "")))
        allowed_ids = {str(r.get("id", "")) for r in rows}
        if eq_id not in allowed_ids:
            context.user_data.pop("awaiting_value_input", None)
            await update.message.reply_text("Эта техника не закреплена за вами.")
            return
        now_short = datetime.now().strftime("%d.%m")
        eq = self.db.get_equipment(eq_id) or {}
        if counter_type == "kmu":
            prev_value = int(eq.get("secondary_current_value") or 0)
            self.db.update_equipment(
                eq_id,
                secondary_current_value=value,
                secondary_current_value_updated_at=now_short,
            )
            eq_after = self.db.get_equipment(eq_id) or {}
            new_value = int(eq_after.get("secondary_current_value") or 0)
            new_updated = str(eq_after.get("secondary_current_value_updated_at") or now_short)
            await update.message.reply_text(
                f"Принято ✅ КМУ обновлено: было {prev_value}, стало {new_value} м/ч (Обновлено {new_updated})"
            )
            self._set_pending_value_request(int(user.id), False)
            await self._send_driver_main_menu(update, context)
        else:
            prev_value = int(eq.get("current_value") or 0)
            self.db.update_equipment(
                eq_id,
                current_value=value,
                current_value_updated_at=now_short,
            )
            eq_after = self.db.get_equipment(eq_id) or {}
            new_value = int(eq_after.get("current_value") or 0)
            new_updated = str(eq_after.get("current_value_updated_at") or now_short)
            await update.message.reply_text(
                f"Принято ✅ Текущее значение обновлено: было {prev_value}, стало {new_value} (Обновлено {new_updated})"
            )
            self._set_pending_value_request(int(user.id), False)
            if bool(eq.get("has_kmu")):
                kb = [
                    [InlineKeyboardButton("Ввести моточасы КМУ", callback_data=f"val:set:{eq_id}:kmu")],
                    [InlineKeyboardButton("В главное меню", callback_data="drv:menu")],
                ]
                await update.message.reply_text(
                    "Хотите сразу ввести счетчик КМУ?",
                    reply_markup=InlineKeyboardMarkup(kb),
                )
            else:
                await self._send_driver_main_menu(update, context)
        context.user_data.pop("awaiting_value_input", None)

    async def _send_driver_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = update.message
        if not msg:
            return
        kb = [
            [InlineKeyboardButton("Ввести текущий пробег", callback_data="val:req")],
            [InlineKeyboardButton("Открыть список техники", callback_data="eq:list")],
            [InlineKeyboardButton("Моя машина", callback_data="drv:mycar")],
        ]
        await msg.reply_text("Главное меню водителя:", reply_markup=InlineKeyboardMarkup(kb))

    async def _send_driver_main_menu_chat(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
        kb = [
            [InlineKeyboardButton("Ввести текущий пробег", callback_data="val:req")],
            [InlineKeyboardButton("Открыть список техники", callback_data="eq:list")],
            [InlineKeyboardButton("Моя машина", callback_data="drv:mycar")],
        ]
        await context.bot.send_message(
            chat_id=chat_id,
            text="Главное меню водителя:",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    async def broadcast_value_requests(self, context: ContextTypes.DEFAULT_TYPE):
        await self._broadcast_value_requests_once(context)

    async def _broadcast_value_requests_once(self, context: ContextTypes.DEFAULT_TYPE) -> int:
        payload = _load_sessions()
        bindings = payload.get("driver_bindings", {})
        if not isinstance(bindings, dict):
            return 0
        sent_count = 0
        for user_id_str, binding in bindings.items():
            try:
                user_id = int(user_id_str)
            except Exception:
                continue
            if self._is_owner_user(user_id):
                continue
            if not isinstance(binding, dict):
                continue
            snapshot = self._resolve_driver_snapshot(str(binding.get("driver_id", "")))
            kb = [[InlineKeyboardButton("Ввести текущий пробег", callback_data="val:req")]]
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"{snapshot.get('driver_name', 'Водитель')}, пожалуйста введите текущий пробег техники.",
                    reply_markup=InlineKeyboardMarkup(kb),
                )
                self._set_pending_value_request(user_id, True)
                sent_count += 1
            except Exception as e:
                print(f"Telegram bot: cannot send periodic request to {user_id}: {e}")
        return sent_count

    async def weekly_value_requests(self, context: ContextTypes.DEFAULT_TYPE):
        now = datetime.now()
        if now.weekday() != WEEKLY_BROADCAST_WEEKDAY:
            return
        if now.hour != WEEKLY_BROADCAST_HOUR or now.minute != WEEKLY_BROADCAST_MINUTE:
            return
        interval_weeks = max(1, WEEKLY_BROADCAST_INTERVAL_WEEKS)
        if interval_weeks > 1:
            iso_week = now.isocalendar().week
            if (iso_week - 1) % interval_weeks != 0:
                return
        sent = await self._broadcast_value_requests_once(context)
        if sent:
            print(f"Telegram bot: scheduled broadcast sent to {sent} drivers")

    async def remind_pending_value_requests(self, context: ContextTypes.DEFAULT_TYPE):
        ids = self._pending_value_request_ids()
        if not ids:
            return
        kb = [[InlineKeyboardButton("Ввести текущие значения", callback_data="val:req")]]
        for user_id in ids:
            if self._is_owner_user(user_id):
                self._set_pending_value_request(user_id, False)
                continue
            binding = _get_driver_binding(user_id)
            if not binding:
                self._set_pending_value_request(user_id, False)
                continue
            snapshot = self._resolve_driver_snapshot(str(binding.get("driver_id", "")))
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"{snapshot.get('driver_name', 'Водитель')}, напоминаем: нужно ввести текущий пробег.\n"
                        "Если уже ввели — это напоминание скоро прекратится."
                    ),
                    reply_markup=InlineKeyboardMarkup(kb),
                )
            except Exception as e:
                print(f"Telegram bot: cannot send reminder to {user_id}: {e}")

    async def _send_driver_picker(self, target, allow_edit: bool = False):
        drivers = self.db.get_all_drivers() or []
        if not drivers and self._try_switch_company_from_equipment():
            drivers = self.db.get_all_drivers() or []
        if not drivers:
            text = "Водители не найдены в базе."
            if allow_edit:
                await target.edit_text(text)
            else:
                await target.reply_text(text)
            return
        kb = []
        for d in drivers[:60]:
            driver_id = str(d.get("id"))
            name = str(d.get("name") or "-")
            kb.append([InlineKeyboardButton(name[:64], callback_data=f"auth:driver:{driver_id}")])
        text = "Выберите себя из списка водителей:"
        if allow_edit:
            await target.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))
        else:
            await target.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

    async def _confirm_driver_binding(self, q, context: ContextTypes.DEFAULT_TYPE, driver_id: str):
        driver = self.db.get_driver(driver_id)
        if not driver:
            await q.answer("Водитель не найден", show_alert=True)
            return
        equipment_list = self.db.get_driver_equipment(driver_id) or []
        if equipment_list:
            eq = equipment_list[0]
            eq_text = f"{eq.get('name', '-')} ({eq.get('reg_number', '-')})"
        else:
            eq_text = "не привязана"
        context.user_data["pending_driver_binding"] = {
            "driver_id": str(driver_id),
            "driver_name": str(driver.get("name", "-")),
            "equipment_text": eq_text,
        }
        kb = [
            [InlineKeyboardButton("✅ Подтвердить", callback_data=f"auth:confirm:{driver_id}")],
            [InlineKeyboardButton("↩️ Выбрать заново", callback_data="auth:pick")],
        ]
        await q.edit_message_text(
            f"Вы водитель: *{driver.get('name', '-')}*\n"
            f"Техника: *{eq_text}*\n\n"
            f"Подтвердить?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    async def _apply_driver_binding(self, q, context: ContextTypes.DEFAULT_TYPE, driver_id: str):
        user = q.from_user
        if not user:
            return
        pending = context.user_data.get("pending_driver_binding") or {}
        if str(pending.get("driver_id", "")) != str(driver_id):
            await q.answer("Выбор устарел. Выберите себя заново.", show_alert=True)
            return
        _set_driver_binding(
            int(user.id),
            {
                "driver_id": str(driver_id),
                "bound_at": datetime.now().isoformat(),
            },
        )
        snapshot = self._resolve_driver_snapshot(str(driver_id))
        kb = [
            [InlineKeyboardButton("Ввести текущий пробег", callback_data="val:req")],
            [InlineKeyboardButton("Открыть список техники", callback_data="eq:list")],
            [InlineKeyboardButton("Моя машина", callback_data="drv:mycar")],
        ]
        await q.edit_message_text(
            f"Режим водителя активирован.\n"
            f"Вы: {snapshot.get('driver_name', '-')}\n"
            f"Ваша техника: {snapshot.get('equipment_text', '-')}\n\n"
            f"Главное меню водителя:",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    async def _show_equipment_card(self, q, eq_id: str):
        eq = self.db.get_equipment(eq_id)
        if not eq:
            await q.edit_message_text("Техника не найдена.")
            return
        active_driver = "-"
        try:
            dmap = self.db.get_active_driver_name_by_equipment_id() or {}
            active_driver = dmap.get(str(eq_id), "-")
        except Exception:
            pass

        has_kmu = bool(eq.get("has_kmu"))
        current_month = datetime.now().month
        is_winter = current_month in [11, 12, 1, 2]
        interval = eq.get('maintenance_interval_winter') if is_winter else eq.get('maintenance_interval_summer')
        chassis_unit = "км" if str(eq.get("measurement_type") or "mileage") != "motohours" else "м/ч"
        try:
            next_maintenance = int(eq.get('last_maintenance') or 0) + int(interval or 0)
        except Exception:
            next_maintenance = "-"
        lines = [
            f"*{eq.get('name', '-') }* ({eq.get('reg_number', '-')})",
            f"1) VIN: `{eq.get('sts_pts', '-')}`",
            f"2) СТС: `{eq.get('sts_certificate', '-')}`",
            f"3) Текущий пробег(шасси): *{_fmt_value_with_update(eq)}*",
            f"4) Последнее ТО: *{eq.get('last_maintenance', '-')} {chassis_unit}*",
            f"5) Следующее ТО: *{next_maintenance} {chassis_unit}*",
        ]
        next_idx = 6
        if has_kmu:
            lines.append(f"{next_idx}) Текущие моточасы КМУ: *{_fmt_secondary_value(eq)}*")
            next_idx += 1
            lines.append(f"{next_idx}) Последнее ТО КМУ: *{eq.get('secondary_last_maintenance', '-') } м/ч*")
            next_idx += 1
        lines.extend([
            f"{next_idx}) Текущий водитель: *{active_driver}*",
            f"{next_idx + 1}) Страховка до: *{eq.get('insurance_date') or '-'}*",
            f"{next_idx + 2}) Диаг. карта до: *{eq.get('diagnostic_card_date') or '-'}*",
            f"{next_idx + 3}) Пропуск до: *{eq.get('mkad_pass_date') or '-'}*",
        ])
        text = "\n".join(lines)

        kb = [
            [
                InlineKeyboardButton("Показать СТС", callback_data=f"doc:sts:{eq_id}"),
                InlineKeyboardButton("Показать Диаг карту", callback_data=f"doc:diag:{eq_id}"),
            ],
            [
                InlineKeyboardButton("Показать Страховку", callback_data=f"doc:ins:{eq_id}"),
                InlineKeyboardButton("ТО", callback_data=f"mnt:list:{eq_id}"),
            ],
            [
                InlineKeyboardButton("Неисправности", callback_data=f"iss:list:{eq_id}"),
            ],
            [InlineKeyboardButton("Назад к списку", callback_data="eq:list")],
        ]
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    def _get_equipment_maintenance_records(self, eq_id: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        try:
            if hasattr(self.db, "get_equipment_maintenance_history"):
                records = self.db.get_equipment_maintenance_history(eq_id) or []
            elif hasattr(self.db, "get_maintenance_history"):
                records = self.db.get_maintenance_history(eq_id) or []
            else:
                all_rows = self.db.get_all_maintenance_history() or []
                records = [r for r in all_rows if str(r.get("equipment_id")) == str(eq_id)]
        except Exception:
            records = []
        out: list[dict[str, Any]] = []
        for r in records:
            try:
                out.append(dict(r))
            except Exception:
                out.append(r)
        out.sort(key=lambda x: str(x.get("maintenance_date") or ""), reverse=True)
        return out

    async def _show_maintenance_list(self, q, context: ContextTypes.DEFAULT_TYPE, eq_id: str):
        eq = self.db.get_equipment(eq_id)
        if not eq:
            await q.edit_message_text("Техника не найдена.")
            return
        records = self._get_equipment_maintenance_records(eq_id)
        if not records:
            kb = [[InlineKeyboardButton("Назад к технике", callback_data=f"eq:{eq_id}")]]
            await q.edit_message_text("История ТО пуста.", reply_markup=InlineKeyboardMarkup(kb))
            return
        kb = []
        mnt_map: dict[str, tuple[str, str]] = {}
        for row in records[:60]:
            mid = str(row.get("id", ""))
            value = row.get("maintenance_value", "-")
            counter_type = str(row.get("counter_type") or "primary").strip().lower()
            date_txt = _fmt_iso(row.get("maintenance_date")).split(" ")[0]
            scope = "КМУ" if counter_type == "kmu" else "Шасси"
            label = f"{scope}: ТО на {value} дата {date_txt}"
            key = f"m{len(mnt_map)}"
            mnt_map[key] = (str(eq_id), mid)
            kb.append([InlineKeyboardButton(label[:64], callback_data=f"mnt:item:{key}")])
        context.user_data["mnt_map"] = mnt_map
        kb.append([InlineKeyboardButton("Назад к технике", callback_data=f"eq:{eq_id}")])
        await q.edit_message_text(
            f"История ТО: {eq.get('name', '-')}",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    async def _send_maintenance_invoice(self, q, context: ContextTypes.DEFAULT_TYPE, eq_id: str, maint_id: str):
        records = self._get_equipment_maintenance_records(eq_id)
        row = next((x for x in records if str(x.get("id")) == str(maint_id)), None)
        if not row:
            await q.answer("Запись ТО не найдена", show_alert=True)
            return
        path = row.get("invoice_path", "")
        if not path:
            await q.answer("Счет к этому ТО не прикреплен", show_alert=True)
            return
        await self._send_file_by_path(q, context, path, "Счет по ТО")

    async def _send_file_by_path(self, q, context: ContextTypes.DEFAULT_TYPE, file_path: str, title: str):
        if not file_path:
            await q.answer("Файл не прикреплен", show_alert=True)
            return
        try:
            if str(file_path).startswith("supabase://") and hasattr(self.db, "resolve_invoice_path"):
                url = self.db.resolve_invoice_path(file_path)
                if not url:
                    raise RuntimeError("Нет URL к файлу")
                suffix = "." + file_path.rsplit(".", 1)[-1] if "." in file_path else ".pdf"
                fd, tmp_path = tempfile.mkstemp(suffix=suffix)
                os.close(fd)
                urllib.request.urlretrieve(url, tmp_path)
                with open(tmp_path, "rb") as f:
                    sent = await q.message.reply_document(document=f, filename=os.path.basename(file_path), caption=title)
                    await self._remember_transient_message(context, sent)
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                return

            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    sent = await q.message.reply_document(document=f, filename=os.path.basename(file_path), caption=title)
                    await self._remember_transient_message(context, sent)
                return
            await q.answer("Файл не найден", show_alert=True)
        except Exception as e:
            await q.answer(f"Ошибка файла: {e}", show_alert=True)

    async def _send_equipment_doc(self, q, context: ContextTypes.DEFAULT_TYPE, eq_id: str, doc_type: str):
        eq = self.db.get_equipment(eq_id)
        if not eq:
            await q.answer("Техника не найдена", show_alert=True)
            return
        if doc_type == "sts":
            await self._send_file_by_path(q, context, eq.get("sts_file_path", ""), "СТС")
        elif doc_type == "diag":
            await self._send_file_by_path(q, context, eq.get("diagnostic_card_file_path", ""), "Диагностическая карта")
        elif doc_type == "ins":
            await self._send_file_by_path(q, context, eq.get("insurance_file_path", ""), "Страховка")

    async def _show_issues_list(self, q, eq_id: str):
        eq = self.db.get_equipment(eq_id)
        issues = self.db.get_equipment_issues(eq_id) or []
        if not eq:
            await q.edit_message_text("Техника не найдена.")
            return
        if not issues:
            kb = [[InlineKeyboardButton("Назад к технике", callback_data=f"eq:{eq_id}")]]
            await q.edit_message_text(f"Неисправностей нет: {eq.get('name', '-')}", reply_markup=InlineKeyboardMarkup(kb))
            return
        kb = []
        for iss in issues:
            iid = str(iss.get("id"))
            status = "Откр" if iss.get("status") == "open" else "Закр"
            d = _fmt_iso(iss.get("reported_date"))
            desc = str(iss.get("description", "")).strip().replace("\n", " ")
            label = f"{status} • {d} • {desc[:28]}"
            kb.append([InlineKeyboardButton(label[:64], callback_data=f"iss:item:{iid}")])
        kb.append([InlineKeyboardButton("Назад к технике", callback_data=f"eq:{eq_id}")])
        await q.edit_message_text(
            f"Неисправности: {eq.get('name', '-')}",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    async def _show_issue_item(self, q, issue_id: str):
        all_issues = self.db.get_all_issues() or []
        issue = next((x for x in all_issues if str(x.get("id")) == str(issue_id)), None)
        if not issue:
            await q.answer("Неисправность не найдена", show_alert=True)
            return
        eq_id = str(issue.get("equipment_id", ""))
        status = "Открыта" if issue.get("status") == "open" else "Закрыта"
        txt = (
            f"*Неисправность #{issue.get('id')}*\n"
            f"Статус: *{status}*\n"
            f"Дата: *{_fmt_iso(issue.get('reported_date'))}*\n"
            f"Описание:\n{issue.get('description', '-')}\n\n"
            f"Решение: {issue.get('resolution_comment') or '-'}"
        )
        kb = []
        inv_paths = _split_invoice_paths(issue.get("resolution_invoice_path", ""))
        if inv_paths:
            kb.append([InlineKeyboardButton("Показать счет решения", callback_data=f"iss:inv:{issue_id}")])
        kb.append([InlineKeyboardButton("Назад к неисправностям", callback_data=f"iss:list:{eq_id}")])
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    async def _send_issue_invoice(self, q, context: ContextTypes.DEFAULT_TYPE, issue_id: str):
        all_issues = self.db.get_all_issues() or []
        issue = next((x for x in all_issues if str(x.get("id")) == str(issue_id)), None)
        if not issue:
            await q.answer("Неисправность не найдена", show_alert=True)
            return
        paths = _split_invoice_paths(issue.get("resolution_invoice_path", ""))
        if not paths:
            await q.answer("Счет не прикреплен", show_alert=True)
            return
        for idx, path in enumerate(paths, start=1):
            await self._send_file_by_path(q, context, path, f"Счет решения #{idx}")


def main():
    if not TOKEN:
        raise RuntimeError(
            "Не задан токен бота. Укажите TELEGRAM_BOT_TOKEN или BOT_TOKEN в переменных окружения."
        )
    print(f"Telegram bot: token loaded (id prefix {TOKEN.split(':', 1)[0]})")
    bot = FleetBot()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("login", bot.login))
    app.add_handler(CommandHandler("logout", bot.logout))
    app.add_handler(CommandHandler("myid", bot.myid))
    app.add_handler(CommandHandler("as_driver_test", bot.as_driver_test))
    app.add_handler(CommandHandler("send_value_request_now", bot.send_value_request_now))
    app.add_handler(CommandHandler("send_value_request_me", bot.send_value_request_me))
    app.add_handler(CallbackQueryHandler(bot.on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.on_text))
    # JobQueue в PTB требует доп. зависимость (apscheduler).
    # Проверяем пакет до обращения к app.job_queue, чтобы не ловить PTBUserWarning.
    if importlib.util.find_spec("apscheduler") is not None and app.job_queue is not None:
        app.job_queue.run_repeating(bot.weekly_value_requests, interval=60, first=10)
        reminder_interval = max(5, REMINDER_INTERVAL_MINUTES) * 60
        app.job_queue.run_repeating(bot.remind_pending_value_requests, interval=reminder_interval, first=40)
        print(
            "Telegram bot: scheduled requests enabled "
            f"(every {max(1, WEEKLY_BROADCAST_INTERVAL_WEEKS)} week(s), "
            f"weekday={WEEKLY_BROADCAST_WEEKDAY}, time={WEEKLY_BROADCAST_HOUR:02d}:{WEEKLY_BROADCAST_MINUTE:02d})"
        )
        print(f"Telegram bot: reminders every {max(5, REMINDER_INTERVAL_MINUTES)} minutes")
    else:
        print("Telegram bot: periodic requests disabled (install python-telegram-bot[job-queue])")
    async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            print(f"Telegram bot error: {context.error}")
        except Exception:
            pass
    app.add_error_handler(_on_error)
    print("Telegram bot started.")
    # Сбрасываем webhook и старые апдейты — иначе polling на хостинге может «молчать».
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

