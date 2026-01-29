from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import threading
import time
import os
import json
import random
import requests

app = Flask(__name__)
app.secret_key = app.secret_key = os.getenv("SECRET_KEY", "CHANGE_ME_TO_SOMETHING_RANDOM")  # чтобы сессии работали стабильно

DB_NAME = "data/employees.db"
NOTIFICATION_HISTORY_FILE = "data/notification_history.json"

# ================= TELEGRAM (встроенный) =================
TELEGRAM_TOKEN = "8357883858:AAEt_Csdcft7Obzv85J15F3WaYsXiZJ-FfQ"
TELEGRAM_CHAT_ID = "-4537586641"
HAS_TELEGRAM = True

def send_telegram_notification(text: str) -> bool:
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
        r = requests.post(url, data=data, timeout=10)
        r.raise_for_status()
        print("✅ Telegram: Уведомление отправлено")
        return True
    except Exception as e:
        print(f"❌ Telegram: Ошибка: {e}")
        return False
# =========================================================

BIRTHDAY_CONGRATS = [
    "🎉 Поздравляем с Днём рождения! Желаем успехов, здоровья и отличного настроения!",
    "🎂 С Днём рождения! Пусть всё получается легко и радостно!",
    "🥳 С Днём рождения! Радости, удачи и крутых достижений!",
    "🎈 С Днём рождения! Пусть будет больше счастья и меньше забот!",
]

REMINDER_TEXTS = [
    "🔔 НАПОМИНАНИЕ! Завтра день рождения у коллеги. Подготовьте поздравления! 🎁",
    "⏰ Завтра у нас день рождения! Не забудьте поздравить! 🎉",
    "📅 Завтра особенный день — готовим поздравления! 🥳",
    "🎈 Завтра ДР у коллеги! 🎂",
]

def get_random_congrat():
    return random.choice(BIRTHDAY_CONGRATS)

def get_random_reminder():
    return random.choice(REMINDER_TEXTS)

def get_age_suffix(age: int) -> str:
    if 11 <= age % 100 <= 19:
        return "лет"
    if age % 10 == 1:
        return "год"
    if 2 <= age % 10 <= 4:
        return "года"
    return "лет"

def load_notification_history():
    if os.path.exists(NOTIFICATION_HISTORY_FILE):
        try:
            with open(NOTIFICATION_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_notification_history(history: dict):
    with open(NOTIFICATION_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def login_required(f):
    @wraps(f)
    def w(*args, **kwargs):
        if not session.get("logged_in"):
            flash("Пожалуйста, войдите в систему", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return w

def admin_required(f):
    @wraps(f)
    def w(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        if not session.get("is_admin"):
            abort(403)
        return f(*args, **kwargs)
    return w

def table_columns(cursor, table_name: str):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [r[1] for r in cursor.fetchall()]

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # users (миграция под is_admin)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    cols = table_columns(cur, "users")
    if "is_admin" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")

    # departments
    cur.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    # employees (миграция под department_id)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dob TEXT NOT NULL
        )
    """)
    emp_cols = table_columns(cur, "employees")
    if "department_id" not in emp_cols:
        cur.execute("ALTER TABLE employees ADD COLUMN department_id INTEGER")

    # default admin
    cur.execute("SELECT id FROM users WHERE username=?", ("admin",))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username, password, is_admin) VALUES (?, ?, 1)",
            ("admin", generate_password_hash("admin123"))
        )
    else:
        cur.execute("UPDATE users SET is_admin=1 WHERE username='admin'")

    # seed departments
    cur.execute("SELECT COUNT(*) FROM departments")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO departments (name) VALUES (?)",
            [("IT",), ("HR",), ("Продажи",)]
        )

    conn.commit()
    conn.close()

def get_departments():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM departments ORDER BY name")
    deps = cur.fetchall()
    conn.close()
    return deps

def check_and_send_birthday_notifications(force_send=False):
    """Авто/ручная проверка. Если force_send=True — игнорируем историю (полезно для ручной проверки)."""
    if not HAS_TELEGRAM:
        return (False, "Telegram не настроен")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT e.id, e.name, e.dob, COALESCE(d.name,'') as dept
        FROM employees e
        LEFT JOIN departments d ON d.id = e.department_id
    """)
    employees = cur.fetchall()
    conn.close()

    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    history = load_notification_history()

    # 1) reminder for tomorrow
    tomorrow_key = f"reminder_{tomorrow.strftime('%Y-%m-%d')}"
    birthdays_tomorrow = []
    for emp_id, name, dob, dept in employees:
        bd = datetime.strptime(dob, "%Y-%m-%d")
        if bd.strftime("%m-%d") == tomorrow.strftime("%m-%d"):
            birthdays_tomorrow.append((emp_id, name, dob, dept))

    if birthdays_tomorrow and (force_send or tomorrow_key not in history):
        msg = "🎯 НАПОМИНАНИЕ 🎯\n\nЗАВТРА ДЕНЬ РОЖДЕНИЯ!\n\nИменинники:\n"
        for _, name, dob, dept in birthdays_tomorrow:
            bd = datetime.strptime(dob, "%Y-%m-%d")
            age = tomorrow.year - bd.year
            if (tomorrow.month, tomorrow.day) < (bd.month, bd.day):
                age -= 1
            if dept:
                msg += f"\n🎈 {name} ({dept})"
            else:
                msg += f"\n🎈 {name}"
            msg += f"\n   🎂 Исполняется: {age} {get_age_suffix(age)}"
            msg += f"\n   📅 {bd.strftime('%d.%m.%Y')}\n"
        msg += "\n" + get_random_reminder()

        if send_telegram_notification(msg) and not force_send:
            history[tomorrow_key] = {"type": "reminder", "sent_at": datetime.now().isoformat()}
            save_notification_history(history)

    # 2) congrats today
    today_key = f"congrat_{today.strftime('%Y-%m-%d')}"
    birthdays_today = []
    for emp_id, name, dob, dept in employees:
        bd = datetime.strptime(dob, "%Y-%m-%d")
        if bd.strftime("%m-%d") == today.strftime("%m-%d"):
            birthdays_today.append((emp_id, name, dob, dept))

    if birthdays_today and (force_send or today_key not in history):
        msg = "🎂 С ДНЁМ РОЖДЕНИЯ! 🎂\n\nСЕГОДНЯ ПРАЗДНУЮТ:\n\n"
        for i, (_, name, dob, dept) in enumerate(birthdays_today, 1):
            bd = datetime.strptime(dob, "%Y-%m-%d")
            age = today.year - bd.year
            if (today.month, today.day) < (bd.month, bd.day):
                age -= 1
            title = f"{name} ({dept})" if dept else name
            msg += f"{i}. 🎈 {title}\n"
            msg += f"   🎊 {age} {get_age_suffix(age)}\n"
            msg += f"   {get_random_congrat()}\n\n"

        if send_telegram_notification(msg) and not force_send:
            history[today_key] = {"type": "congrat", "sent_at": datetime.now().isoformat()}
            save_notification_history(history)

    return (True, "ok")

def background_loop():
    # первая проверка сразу
    try:
        check_and_send_birthday_notifications()
    except Exception as e:
        print("❌ background first run:", e)

    while True:
        try:
            time.sleep(21600)  # 6 часов
            check_and_send_birthday_notifications()
        except Exception as e:
            print("❌ background loop:", e)
            time.sleep(300)

_bg_started = False
def start_bg_once():
    global _bg_started
    if _bg_started:
        return
    _bg_started = True
    t = threading.Thread(target=background_loop, daemon=True)
    t.start()
    print("✅ Фоновая проверка запущена")

# -------------------- ROUTES --------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT id, username, password, is_admin FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["logged_in"] = True
            session["user_id"] = user[0]
            session["username"] = user[1]
            session["is_admin"] = bool(user[3])
            flash("Вы успешно вошли в систему!", "success")
            return redirect(url_for("index"))

        flash("Неверное имя пользователя или пароль", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из системы", "info")
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # add employee
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_employee":
            name = request.form.get("name", "").strip()
            dob = request.form.get("dob", "").strip()
            dept_id = request.form.get("department_id", "").strip() or None

            if not name or not dob:
                flash("Заполните имя и дату рождения", "danger")
                return redirect(url_for("index"))

            bd = datetime.strptime(dob, "%Y-%m-%d")
            if bd > datetime.now():
                flash("Дата рождения не может быть в будущем", "danger")
                return redirect(url_for("index"))

            cur.execute("INSERT INTO employees (name, dob, department_id) VALUES (?, ?, ?)", (name, dob, dept_id))
            conn.commit()
            flash(f"Сотрудник {name} добавлен!", "success")
            return redirect(url_for("index"))

    # list employees + dept name
    cur.execute("""
        SELECT e.id, e.name, e.dob, COALESCE(d.name,'') as department
        FROM employees e
        LEFT JOIN departments d ON d.id = e.department_id
    """)
    rows = cur.fetchall()
    conn.close()

    employees = [{"id": r[0], "name": r[1], "dob": r[2], "department": r[3]} for r in rows]
    employees_sorted = sorted(employees, key=lambda x: datetime.strptime(x["dob"], "%Y-%m-%d").replace(year=1900))

    today_md = datetime.now().strftime("%m-%d")
    tomorrow_md = (datetime.now() + timedelta(days=1)).strftime("%m-%d")

    birthdays_today = [e["name"] for e in employees if datetime.strptime(e["dob"], "%Y-%m-%d").strftime("%m-%d") == today_md]
    birthdays_tomorrow = [e["name"] for e in employees if datetime.strptime(e["dob"], "%Y-%m-%d").strftime("%m-%d") == tomorrow_md]

    return render_template(
        "index.html",
        employees=employees_sorted,
        birthdays_today=birthdays_today,
        birthdays_tomorrow=birthdays_tomorrow,
        username=session.get("username"),
        is_admin=session.get("is_admin"),
        now=datetime.now(),
        get_age_suffix=get_age_suffix,
        departments=get_departments()
    )

@app.route("/get_employee/<int:employee_id>")
@login_required
def get_employee(employee_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name, dob, department_id FROM employees WHERE id=?", (employee_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "not found"}), 404

    return jsonify({"id": row[0], "name": row[1], "dob": row[2], "department_id": row[3]})

@app.route("/update_employee", methods=["POST"])
@login_required
def update_employee():
    employee_id = request.form.get("employee_id")
    name = request.form.get("name", "").strip()
    dob = request.form.get("dob", "").strip()
    dept_id = request.form.get("department_id", "").strip() or None

    if not employee_id or not name or not dob:
        flash("Заполните все поля", "danger")
        return redirect(url_for("index"))

    bd = datetime.strptime(dob, "%Y-%m-%d")
    if bd > datetime.now():
        flash("Дата рождения не может быть в будущем", "danger")
        return redirect(url_for("index"))

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE employees SET name=?, dob=?, department_id=? WHERE id=?", (name, dob, dept_id, employee_id))
    conn.commit()
    conn.close()

    flash("Сотрудник обновлён!", "success")
    return redirect(url_for("index"))

@app.route("/delete_employees", methods=["POST"])
@login_required
def delete_employees():
    ids = request.form.getlist("delete_ids")
    if not ids:
        return redirect(url_for("index"))

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    placeholders = ",".join(["?"] * len(ids))
    cur.execute(f"DELETE FROM employees WHERE id IN ({placeholders})", ids)
    conn.commit()
    conn.close()

    flash("Удалено!", "success")
    return redirect(url_for("index"))

@app.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add_user":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")

            if not username or not password:
                flash("Заполните все поля", "danger")
            elif password != confirm:
                flash("Пароли не совпадают", "danger")
            elif len(password) < 6:
                flash("Пароль минимум 6 символов", "danger")
            else:
                try:
                    cur.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, 0)",
                                (username, generate_password_hash(password)))
                    conn.commit()
                    flash("Пользователь создан", "success")
                except sqlite3.IntegrityError:
                    flash("Такой пользователь уже существует", "danger")

        elif action == "delete_user":
            user_id = request.form.get("user_id")
            cur.execute("SELECT username FROM users WHERE id=?", (user_id,))
            row = cur.fetchone()
            if row and row[0] == "admin":
                flash("Нельзя удалить admin", "warning")
            else:
                cur.execute("DELETE FROM users WHERE id=?", (user_id,))
                conn.commit()
                flash("Пользователь удалён", "success")

    cur.execute("SELECT id, username FROM users ORDER BY id")
    users_list = cur.fetchall()
    conn.close()
    return render_template("users.html", users=users_list)

@app.route("/departments", methods=["GET", "POST"])
@admin_required
def departments():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Название отдела пустое", "danger")
        else:
            try:
                cur.execute("INSERT INTO departments (name) VALUES (?)", (name,))
                conn.commit()
                flash("Отдел добавлен", "success")
            except sqlite3.IntegrityError:
                flash("Такой отдел уже есть", "danger")

    cur.execute("SELECT id, name FROM departments ORDER BY name")
    deps = cur.fetchall()
    conn.close()
    return render_template("departments.html", departments=deps)

@app.route("/check_birthdays_manual")
@login_required
def check_birthdays_manual():
    # ВНИМАНИЕ: без Forbidden — может нажимать любой, но отправка в Telegram только если он включён
    ok, msg = check_and_send_birthday_notifications(force_send=True)
    if not ok:
        flash(msg, "warning")
    else:
        flash("Проверка выполнена (уведомления отправлены, если есть именинники).", "success")
    return redirect(url_for("index"))

@app.route("/send_test_notification")
@login_required
def send_test_notification():
    if not HAS_TELEGRAM:
        return jsonify({"success": False, "error": "Telegram не настроен"})
    ok = send_telegram_notification("🧪 ТЕСТ: система уведомлений работает ✅")
    return jsonify({"success": ok, "error": None if ok else "Ошибка отправки"})

# ===================== API ДЛЯ TELEGRAM-БОТА =====================
API_KEY = os.getenv("BIRTHDAY_API_KEY", "CHANGE_ME_123")

def api_auth() -> bool:
    return request.headers.get("X-API-KEY") == API_KEY

def api_birthdays_payload(target_date: datetime):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT e.id, e.name, e.dob, COALESCE(d.name,'— без отдела —') as dept
        FROM employees e
        LEFT JOIN departments d ON d.id = e.department_id
        ORDER BY e.name
    """)
    rows = cur.fetchall()
    conn.close()

    items = []
    for emp_id, name, dob, dept in rows:
        try:
            bd = datetime.strptime(dob, "%Y-%m-%d")
        except:
            continue

        if bd.strftime("%m-%d") == target_date.strftime("%m-%d"):
            age = target_date.year - bd.year
            if (target_date.month, target_date.day) < (bd.month, bd.day):
                age -= 1

            items.append({
                "id": emp_id,
                "name": name,
                "dob": dob,
                "department": dept,
                "age": age,
                "age_suffix": get_age_suffix(age),
            })

    return {"date": target_date.strftime("%Y-%m-%d"), "birthdays": items}

@app.route("/api/birthdays/today")
def api_birthdays_today():
    if not api_auth():
        return jsonify({"error": "unauthorized"}), 403
    return jsonify(api_birthdays_payload(datetime.now()))

@app.route("/api/birthdays/tomorrow")
def api_birthdays_tomorrow():
    if not api_auth():
        return jsonify({"error": "unauthorized"}), 403
    return jsonify(api_birthdays_payload(datetime.now() + timedelta(days=1)))

@app.route("/api/birthdays/next7")
def api_birthdays_next7():
    """Ближайшие 7 дней (включая сегодня)"""
    if not api_auth():
        return jsonify({"error": "unauthorized"}), 403

    start = datetime.now()
    days = []
    total = 0

    for i in range(0, 7):
        d = start + timedelta(days=i)
        payload = api_birthdays_payload(d)
        cnt = len(payload.get("birthdays", []))
        total += cnt
        days.append(payload)

    return jsonify({
        "from": start.strftime("%Y-%m-%d"),
        "to": (start + timedelta(days=6)).strftime("%Y-%m-%d"),
        "total": total,
        "days": days
    })

@app.route("/api/departments")
def api_departments():
    if not api_auth():
        return jsonify({"error": "unauthorized"}), 403

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM departments ORDER BY name")
    deps = cur.fetchall()

    result = {}
    for dep_id, dep_name in deps:
        cur.execute("SELECT id, name, dob FROM employees WHERE department_id=? ORDER BY name", (dep_id,))
        emps = cur.fetchall()
        result[dep_name] = [{"id": e[0], "name": e[1], "dob": e[2]} for e in emps]

    cur.execute("SELECT id, name, dob FROM employees WHERE department_id IS NULL ORDER BY name")
    emps_no = cur.fetchall()
    result["— без отдела —"] = [{"id": e[0], "name": e[1], "dob": e[2]} for e in emps_no]

    conn.close()
    return jsonify(result)

@app.route("/api/history")
def api_history():
    """последние отправки из notification_history.json"""
    if not api_auth():
        return jsonify({"error": "unauthorized"}), 403

    hist = load_notification_history()
    # превращаем dict в список и сортируем
    items = []
    for k, v in hist.items():
        sent_at = v.get("sent_at", "")
        items.append({"key": k, **v})
    items.sort(key=lambda x: x.get("sent_at",""), reverse=True)
    return jsonify({"count": len(items), "items": items[:30]})

@app.route("/api/congrats/send", methods=["POST"])
def api_send_congrats():
    """
    Отправить поздравление вручную (по умолчанию сегодня).
    Можно передать дату: /api/congrats/send?date=YYYY-MM-DD
    """
    if not api_auth():
        return jsonify({"error": "unauthorized"}), 403

    if not HAS_TELEGRAM:
        return jsonify({"success": False, "error": "Telegram не настроен"}), 500

    date_str = request.args.get("date", "").strip()
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
        except:
            return jsonify({"success": False, "error": "bad date format, use YYYY-MM-DD"}), 400
    else:
        target_date = datetime.now()

    data = api_birthdays_payload(target_date)
    items = data.get("birthdays", [])

    if not items:
        return jsonify({"success": True, "sent": False, "count": 0, "message": "Именинников нет"}), 200

    msg = "🎂 <b>С ДНЁМ РОЖДЕНИЯ!</b> 🎂\n\n<b>ПРАЗДНУЮТ:</b>\n\n"
    for i, emp in enumerate(items, 1):
        name = emp.get("name", "")
        dept = emp.get("department", "—")
        age = emp.get("age", "")
        age_suffix = emp.get("age_suffix", "")
        title = f"{name} ({dept})" if dept else name
        msg += f"{i}. 🎈 <b>{title}</b>\n"
        msg += f"   🎊 {age} {age_suffix}\n"
        msg += f"   {get_random_congrat()}\n\n"

    ok = send_telegram_notification(msg)
    return jsonify({"success": ok, "sent": ok, "count": len(items)}), (200 if ok else 500)

# =================== /API ДЛЯ TELEGRAM-БОТА =====================

# -------------------- START --------------------
init_db()
start_bg_once()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

