import os
import html
import requests
from dotenv import load_dotenv

load_dotenv()

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("BIRTHDAY_API_KEY", "CHANGE_ME_123")
BASE_URL = os.getenv("FLASK_BASE_URL", "http://10.200.101.50:5000").rstrip("/")


def must_env(name: str, value: str | None):
    if not value:
        raise RuntimeError(f"Env {name} is empty. Put it into .env")


def api_get(path: str) -> dict:
    url = f"{BASE_URL}{path}"
    headers = {"X-API-KEY": API_KEY}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"API {path} -> {r.status_code}: {r.text[:300]}")
    try:
        return r.json()
    except Exception:
        raise RuntimeError(f"API {path} returned not JSON: {r.text[:300]}")


def api_post(path: str) -> dict:
    url = f"{BASE_URL}{path}"
    headers = {"X-API-KEY": API_KEY}
    r = requests.post(url, headers=headers, timeout=15)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"API POST {path} -> {r.status_code}: {r.text[:300]}")
    try:
        return r.json()
    except Exception:
        raise RuntimeError(f"API POST {path} returned not JSON: {r.text[:300]}")


def reply_menu() -> ReplyKeyboardMarkup:
    # Меню снизу, постоянное
    kb = [
        [KeyboardButton("🎂 Сегодня"), KeyboardButton("📅 Завтра")],
        [KeyboardButton("⏰ Ближайшие 7 дней")],
        [KeyboardButton("🏢 Отделы"), KeyboardButton("📩 Поздравить сегодня")],
        [KeyboardButton("📜 История")],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True, is_persistent=True)


def format_birthdays_payload(data: dict, title: str) -> str:
    date = data.get("date", "")
    items = data.get("birthdays", [])

    lines = [f"🎂 <b>{html.escape(title)}</b>", f"📅 Дата: <code>{html.escape(date)}</code>", ""]
    if not items:
        lines.append("✅ Именинников нет.")
        return "\n".join(lines)

    for i, emp in enumerate(items, 1):
        name = html.escape(str(emp.get("name", "")))
        dept = html.escape(str(emp.get("department", "—")))
        age = emp.get("age", "")
        age_suffix = html.escape(str(emp.get("age_suffix", "")))
        dob = html.escape(str(emp.get("dob", "")))

        lines.append(f"{i}. 🎈 <b>{name}</b>")
        lines.append(f"   🏢 {dept}")
        if age != "":
            lines.append(f"   🎊 {age} {age_suffix}")
        lines.append(f"   📌 <code>{dob}</code>")
        lines.append("")

    return "\n".join(lines).strip()


def format_next7(data: dict) -> str:
    total = data.get("total", 0)
    date_from = data.get("from", "")
    date_to = data.get("to", "")
    days = data.get("days", [])

    lines = [
        "⏰ <b>Ближайшие 7 дней</b>",
        f"📅 Период: <code>{html.escape(date_from)}</code> → <code>{html.escape(date_to)}</code>",
        f"👥 Всего именинников: <b>{total}</b>",
        ""
    ]

    if total == 0:
        lines.append("✅ В ближайшие 7 дней именинников нет.")
        return "\n".join(lines)

    for day in days:
        d = day.get("date", "")
        items = day.get("birthdays", [])
        if not items:
            continue

        lines.append(f"📌 <b>{html.escape(d)}</b> — <b>{len(items)}</b>")
        for emp in items:
            name = html.escape(str(emp.get("name", "")))
            dept = html.escape(str(emp.get("department", "—")))
            age = emp.get("age", "")
            age_suffix = html.escape(str(emp.get("age_suffix", "")))
            lines.append(f" • 🎈 <b>{name}</b> ({dept}) — {age} {age_suffix}")
        lines.append("")

    return "\n".join(lines).strip()


def departments_inline(dep_names: list[str]) -> InlineKeyboardMarkup:
    # кнопки отделов
    buttons = []
    for dep_name in dep_names:
        buttons.append([InlineKeyboardButton(dep_name, callback_data=f"dep:{dep_name}")])
    buttons.append([InlineKeyboardButton("⬅️ Назад в меню", callback_data="back_menu")])
    return InlineKeyboardMarkup(buttons)


async def ensure_menu(update: Update):
    # “меню всегда” – на любое сообщение даём меню снизу
    if update.message:
        await update.message.reply_text("Меню готово ✅ Жми кнопки снизу:", reply_markup=reply_menu())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_menu(update)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        _ = api_get("/api/birthdays/today")
        await update.message.reply_text("✅ Бот работает. API доступен.", reply_markup=reply_menu())
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка API: {e}", reply_markup=reply_menu())


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    try:
        if text == "🎂 Сегодня":
            data = api_get("/api/birthdays/today")
            await update.message.reply_text(format_birthdays_payload(data, "Сегодня"), parse_mode="HTML", reply_markup=reply_menu())
            return

        if text == "📅 Завтра":
            data = api_get("/api/birthdays/tomorrow")
            await update.message.reply_text(format_birthdays_payload(data, "Завтра"), parse_mode="HTML", reply_markup=reply_menu())
            return

        if text == "⏰ Ближайшие 7 дней":
            data = api_get("/api/birthdays/next7")
            await update.message.reply_text(format_next7(data), parse_mode="HTML", reply_markup=reply_menu())
            return

        if text == "🏢 Отделы":
            deps_map = api_get("/api/departments")  # {"IT":[...], ...}
            dep_names = list(deps_map.keys())
            await update.message.reply_text("🏢 Выбери отдел:", reply_markup=departments_inline(dep_names))
            return

        if text == "📩 Поздравить сегодня":
            res = api_post("/api/congrats/send")
            if res.get("sent"):
                await update.message.reply_text(f"✅ Поздравление отправлено! 👥 {res.get('count', 0)}", reply_markup=reply_menu())
            else:
                await update.message.reply_text("✅ Сегодня именинников нет — отправлять нечего.", reply_markup=reply_menu())
            return

        if text == "📜 История":
            data = api_get("/api/history")
            items = data.get("items", [])
            if not items:
                await update.message.reply_text("📜 История пустая.", reply_markup=reply_menu())
                return

            lines = ["📜 <b>История (последние 30)</b>", ""]
            for it in items[:10]:
                t = html.escape(str(it.get("type", "")))
                at = html.escape(str(it.get("sent_at", "")))
                k = html.escape(str(it.get("key", "")))
                lines.append(f"• <b>{t}</b> — <code>{at}</code> ({k})")
            lines.append("")
            lines.append("ℹ️ Если нужно — сделаю кнопку «показать ещё».")

            await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=reply_menu())
            return

        # любое другое сообщение — просто показать меню снова
        await ensure_menu(update)

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}", reply_markup=reply_menu())


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        data_key = query.data or ""

        if data_key == "back_menu":
            await query.message.reply_text("Меню готово ✅ Жми кнопки снизу:", reply_markup=reply_menu())
            return

        if data_key.startswith("dep:"):
            dep = data_key.split("dep:", 1)[1]
            deps_map = api_get("/api/departments")
            emps = deps_map.get(dep, [])

            title = html.escape(dep)
            if not emps:
                await query.message.reply_text(f"🏢 <b>{title}</b>\n\n✅ В этом отделе нет сотрудников.", parse_mode="HTML", reply_markup=reply_menu())
                return

            lines = [f"🏢 <b>{title}</b>", f"👥 Сотрудников: <b>{len(emps)}</b>", ""]
            for i, e in enumerate(emps, 1):
                name = html.escape(str(e.get("name", "")))
                dob = html.escape(str(e.get("dob", "")))
                lines.append(f"{i}. {name} — <code>{dob}</code>")

            await query.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=reply_menu())
            return

    except Exception as e:
        await query.message.reply_text(f"❌ Ошибка: {e}", reply_markup=reply_menu())


def main():
    must_env("TELEGRAM_TOKEN", BOT_TOKEN)
    must_env("BIRTHDAY_API_KEY", API_KEY)
    must_env("FLASK_BASE_URL", BASE_URL)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("✅ Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
