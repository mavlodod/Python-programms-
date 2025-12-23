from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import os
from functools import wraps
import threading
import time
import atexit
import json
import random

app = Flask(__name__)
app.secret_key = os.urandom(24)
DB_NAME = "employees.db"

# ================ TELEGRAM ФУНКЦИЯ ПРЯМО ЗДЕСЬ ================
import requests

TELEGRAM_TOKEN = "8357883858:AAEt_Csdcft7Obzv85J15F3WaYsXiZJ-FfQ"
TELEGRAM_CHAT_ID = "-4537586641"

def send_telegram_notification(text):
    """Отправка уведомления в Telegram."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        print(f"✅ Telegram: Уведомление отправлено")
        return True
    except Exception as e:
        print(f"❌ Telegram: Ошибка: {e}")
        return False

HAS_TELEGRAM = True
print("✅ Telegram функции загружены (встроенные)")
# ================ КОНЕЦ TELEGRAM ФУНКЦИЙ ================

# Файл для хранения истории отправки
NOTIFICATION_HISTORY_FILE = "notification_history.json"

# Коллекция поздравительных текстов
BIRTHDAY_CONGRATS = [
    "🎉 Уважаемый коллега! Поздравляем с Днём рождения! Желаем профессиональных успехов, крепкого здоровья и благополучия!",
    "🎂 Дорогой сотрудник! От всей души поздравляем с Днём рождения! Пусть работа приносит радость, а жизнь будет полна счастливых моментов!",
    "🥳 С Днём рождения! Желаем, чтобы каждый день был наполнен радостью, а каждый проект приносил удовлетворение и успех!",
    "🎈 С Днём рождения! 🎈 Пусть сбываются мечты, окружают верные друзья, а в делах сопутствует удача! Будь счастлив(а)!",
    "🎁 Поздравляю с Днём рождения! 🎁 Желаю море улыбок, гору подарков и океан позитива! Пусть всё получается легко и радостно!",
    "✨ С Днём рождения! ✨ Пусть жизнь будет яркой, как фейерверк, сладкой, как торт, и счастливой, как этот день!",
    "💖 Дорогой коллега, с Днём рождения! 💖 Пусть сердце наполняется радостью, душа поёт от счастья, а каждый день приносит что-то хорошее!",
    "🔥 С Днём рождения! 🔥 Новый год жизни - новые возможности! Вперёд к достижениям и свершениям!",
    "🏢 От всего коллектива поздравляем с Днём рождения! 🏢 Ценим тебя как профессионала и уважаем как человека! Успехов!",
    "🌠 С Днём рождения! Желаем: здоровья - богатырского, счастья - бесконечного, удачи - оглушительной!"
]

REMINDER_TEXTS = [
    "🔔 НАПОМИНАНИЕ! Завтра день рождения у нашего коллеги. Приготовьте поздравления! 🎁",
    "⏰ Внимание! Завтра празднуем день рождения! Не забудьте поздравить! 🎉",
    "📅 Завтра особенный день! Готовим поздравления для именинника! 🥳",
    "🎈 Завтра повод для радости! День рождения нашего коллеги! 🎂",
    "🌟 Завтра звёздный час для нашего сотрудника! Готовим сюрпризы! ✨"
]

def get_random_congrat():
    """Возвращает случайное поздравление."""
    return random.choice(BIRTHDAY_CONGRATS)

def get_random_reminder():
    """Возвращает случайное напоминание."""
    return random.choice(REMINDER_TEXTS)

def get_age_suffix(age):
    """Возвращает правильное окончание для возраста."""
    if 11 <= age % 100 <= 19:
        return "лет"
    elif age % 10 == 1:
        return "год"
    elif 2 <= age % 10 <= 4:
        return "года"
    else:
        return "лет"

# Загружаем историю уведомлений
def load_notification_history():
    if os.path.exists(NOTIFICATION_HISTORY_FILE):
        try:
            with open(NOTIFICATION_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_notification_history(history):
    with open(NOTIFICATION_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# Декоратор для проверки аутентификации
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def check_and_send_birthday_notifications():
    """Проверяет дни рождения и отправляет уведомления."""
    if not HAS_TELEGRAM:
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Проверяем структуру таблицы
    cursor.execute("PRAGMA table_info(employees)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Выбираем только существующие колонки
    if 'position' in columns and 'department' in columns and 'email' in columns and 'phone' in columns:
        cursor.execute("SELECT id, name, dob FROM employees")
    else:
        cursor.execute("SELECT id, name, dob FROM employees")
    
    employees = cursor.fetchall()
    conn.close()
    
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    
    # Загружаем историю
    history = load_notification_history()
    
    # 1. НАПОМИНАНИЕ на завтра
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")
    birthdays_tomorrow = []
    
    for emp_id, name, dob in employees:
        birth_date = datetime.strptime(dob, "%Y-%m-%d")
        if birth_date.strftime("%m-%d") == tomorrow.strftime("%m-%d"):
            birthdays_tomorrow.append((emp_id, name, dob))
    
    if birthdays_tomorrow:
        reminder_sent_key = f"reminder_{tomorrow_str}"
        
        if reminder_sent_key not in history:
            # Создаем красивое напоминание
            message = "🎯 НАПОМИНАНИЕ 🎯\n\n"
            message += "ЗАВТРА ДЕНЬ РОЖДЕНИЯ!\n\n"
            
            message += "Именинники:\n"
            for emp_id, name, dob in birthdays_tomorrow:
                birth_date = datetime.strptime(dob, "%Y-%m-%d")
                age = tomorrow.year - birth_date.year
                if (tomorrow.month, tomorrow.day) < (birth_date.month, birth_date.day):
                    age -= 1
                
                message += f"\n🎈 {name}"
                message += f"\n   🎂 Исполняется: {age} {get_age_suffix(age)}"
                message += f"\n   📅 {birth_date.strftime('%d.%m.%Y')}\n"
            
            message += "\n" + get_random_reminder()
            message += "\n\nПриготовьте поздравления! 🎁"
            
            try:
                send_telegram_notification(message)
                
                # Сохраняем в историю
                history[reminder_sent_key] = {
                    "type": "reminder",
                    "date": tomorrow_str,
                    "sent_at": datetime.now().isoformat(),
                    "employees": [name for _, name, _ in birthdays_tomorrow],
                    "message": "Напоминание о днях рождения завтра"
                }
                save_notification_history(history)
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 📢 Отправлено напоминание о {len(birthdays_tomorrow)} днях рождения на завтра")
            except Exception as e:
                print(f"❌ Ошибка отправки напоминания: {e}")
    
    # 2. ПОЗДРАВЛЕНИЯ на сегодня
    today_str = today.strftime("%Y-%m-%d")
    birthdays_today = []
    
    for emp_id, name, dob in employees:
        birth_date = datetime.strptime(dob, "%Y-%m-%d")
        if birth_date.strftime("%m-%d") == today.strftime("%m-%d"):
            birthdays_today.append((emp_id, name, dob))
    
    if birthdays_today:
        congrat_sent_key = f"congrat_{today_str}"
        
        if congrat_sent_key not in history:
            # Создаем красивые поздравления
            message = "🎂 С ДНЁМ РОЖДЕНИЯ! 🎂\n\n"
            
            message += "СЕГОДНЯ СВОЙ ПРАЗДНИК ОТМЕЧАЮТ:\n\n"
            
            for idx, (emp_id, name, dob) in enumerate(birthdays_today, 1):
                birth_date = datetime.strptime(dob, "%Y-%m-%d")
                age = today.year - birth_date.year
                if (today.month, today.day) < (birth_date.month, birth_date.day):
                    age -= 1
                
                message += f"{idx}. 🎈 {name}\n"
                message += f"   🎊 {age} {get_age_suffix(age)}!\n"
                message += f"   📅 {birth_date.strftime('%d.%m.%Y')}\n"
                message += f"   {get_random_congrat()}\n\n"
            
            message += "Желаем счастья, здоровья и успехов!\n"
            message += "Пусть этот день будет незабываемым! 🥳"
            
            try:
                send_telegram_notification(message)
                
                # Сохраняем в историю
                history[congrat_sent_key] = {
                    "type": "congratulation",
                    "date": today_str,
                    "sent_at": datetime.now().isoformat(),
                    "employees": [name for _, name, _ in birthdays_today],
                    "message": "Поздравления с днем рождения сегодня"
                }
                save_notification_history(history)
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🎉 Отправлены поздравления {len(birthdays_today)} именинникам")
            except Exception as e:
                print(f"❌ Ошибка отправки поздравлений: {e}")

def background_birthday_check():
    """Фоновая проверка дней рождения."""
    print("🔄 Фоновая проверка дней рождения запущена")
    
    # Первая проверка сразу при старте
    check_and_send_birthday_notifications()
    
    # Затем проверяем каждые 6 часов
    while True:
        try:
            # Ждем 6 часов (21600 секунд)
            time.sleep(21600)
            check_and_send_birthday_notifications()
        except Exception as e:
            print(f"❌ Ошибка в фоновой проверке: {e}")
            time.sleep(300)

def start_background_check():
    """Запуск фоновой проверки."""
    thread = threading.Thread(target=background_birthday_check, daemon=True)
    thread.start()
    print("✅ Фоновая проверка запущена в отдельном потоке")
    return thread

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Создаем таблицу сотрудников (простая версия)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dob TEXT NOT NULL
        )
    """)
    
    # Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    
    # Проверяем наличие дефолтного пользователя
    cursor.execute("SELECT * FROM users WHERE username = ?", ('admin',))
    if not cursor.fetchone():
        hashed_password = generate_password_hash('admin123')
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                      ('admin', hashed_password))
        print("👤 Создан дефолтный пользователь: admin / admin123")
    
    conn.commit()
    conn.close()

init_db()

# Запускаем фоновую проверку при старте
bg_thread = start_background_check()

# Маршрут входа в систему
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'logged_in' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            session['logged_in'] = True
            session['username'] = username
            session['user_id'] = user[0]
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
    
    return render_template('login.html')

# Маршрут выхода
@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))

# Главная страница
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add_employee":
            name = request.form.get("name")
            dob = request.form.get("dob")
            
            if name and dob:
                birth_date = datetime.strptime(dob, "%Y-%m-%d")
                if birth_date > datetime.now():
                    flash('Дата рождения не может быть в будущем', 'danger')
                else:
                    cursor.execute("INSERT INTO employees (name, dob) VALUES (?, ?)", (name, dob))
                    conn.commit()
                    flash(f'Сотрудник {name} успешно добавлен!', 'success')
            return redirect(url_for('index'))

    # Получение сотрудников - используем только существующие колонки
    try:
        cursor.execute("SELECT id, name, dob FROM employees")
    except sqlite3.OperationalError:
        # Если ошибка, создаем таблицу заново
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                dob TEXT NOT NULL
            )
        """)
        cursor.execute("SELECT id, name, dob FROM employees")
    
    rows = cursor.fetchall()
    employees = [
        {
            "id": r[0], 
            "name": r[1], 
            "dob": r[2]
        } for r in rows
    ]

    # Сортировка по месяцу и дню
    employees_sorted = sorted(
        employees,
        key=lambda x: datetime.strptime(x["dob"], "%Y-%m-%d").replace(year=1900)
    )

    # Дни рождения завтра
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%m-%d")
    birthdays_tomorrow = [
        e["name"] for e in employees
        if datetime.strptime(e["dob"], "%Y-%m-%d").strftime("%m-%d") == tomorrow
    ]

    # Дни рождения сегодня
    today = datetime.now().strftime("%m-%d")
    birthdays_today = [
        e["name"] for e in employees
        if datetime.strptime(e["dob"], "%Y-%m-%d").strftime("%m-%d") == today
    ]

    conn.close()

    return render_template(
        "index.html",
        employees=employees_sorted,
        birthdays_tomorrow=birthdays_tomorrow,
        birthdays_today=birthdays_today,
        username=session.get('username'),
        now=datetime.now(),
        get_age_suffix=get_age_suffix
    )

# API для получения данных сотрудника
@app.route("/get_employee/<int:employee_id>")
@login_required
def get_employee(employee_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, name, dob FROM employees WHERE id = ?", (employee_id,))
    except sqlite3.OperationalError:
        return jsonify({"error": "Ошибка базы данных"}), 500
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        employee = {
            "id": row[0],
            "name": row[1],
            "dob": row[2]
        }
        return jsonify(employee)
    else:
        return jsonify({"error": "Сотрудник не найден"}), 404

# Обновление данных сотрудника
@app.route("/update_employee", methods=["POST"])
@login_required
def update_employee():
    try:
        employee_id = request.form.get("employee_id")
        name = request.form.get("name")
        dob = request.form.get("dob")
        
        if not employee_id or not name or not dob:
            flash('Обязательные поля не заполнены', 'danger')
            return redirect(url_for('index'))
        
        birth_date = datetime.strptime(dob, "%Y-%m-%d")
        if birth_date > datetime.now():
            flash('Дата рождения не может быть в будущем', 'danger')
            return redirect(url_for('index'))
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute("UPDATE employees SET name = ?, dob = ? WHERE id = ?", (name, dob, employee_id))
        
        conn.commit()
        conn.close()
        
        flash(f'Данные сотрудника {name} успешно обновлены!', 'success')
        
    except Exception as e:
        flash(f'Ошибка при обновлении: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

# Удаление сотрудников
@app.route("/delete_employees", methods=["POST"])
@login_required
def delete_employees():
    ids_to_delete = request.form.getlist("delete_ids")
    if ids_to_delete:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(ids_to_delete))
        
        # Получаем имена удаляемых сотрудников
        cursor.execute(f"SELECT name FROM employees WHERE id IN ({placeholders})", ids_to_delete)
        deleted_names = [row[0] for row in cursor.fetchall()]
        
        # Удаляем сотрудников
        cursor.execute(f"DELETE FROM employees WHERE id IN ({placeholders})", ids_to_delete)
        conn.commit()
        conn.close()
        
        if deleted_names:
            names_str = ', '.join(deleted_names[:3])
            if len(deleted_names) > 3:
                names_str += f" и ещё {len(deleted_names) - 3}"
            flash(f'Удалены сотрудники: {names_str}', 'success')
    return redirect(url_for('index'))

# Управление пользователями
@app.route("/users", methods=["GET", "POST"])
@login_required
def manage_users():
    if session.get('username') != 'admin':
        flash('У вас нет прав для управления пользователями', 'danger')
        return redirect(url_for('index'))
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "add_user":
            username = request.form.get("username")
            password = request.form.get("password")
            confirm_password = request.form.get("confirm_password")
            
            if not username or not password:
                flash('Заполните все поля', 'danger')
            elif password != confirm_password:
                flash('Пароли не совпадают', 'danger')
            elif len(password) < 6:
                flash('Пароль должен содержать минимум 6 символов', 'danger')
            else:
                hashed_password = generate_password_hash(password)
                try:
                    cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                                  (username, hashed_password))
                    conn.commit()
                    flash(f'Пользователь {username} успешно создан!', 'success')
                except sqlite3.IntegrityError:
                    flash('Пользователь с таким именем уже существует', 'danger')
        
        elif action == "delete_user":
            user_id = request.form.get("user_id")
            if user_id != '1':  # Нельзя удалить дефолтного админа
                cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                flash('Пользователь удален', 'success')
            else:
                flash('Нельзя удалить дефолтного администратора', 'warning')
    
    cursor.execute("SELECT id, username FROM users")
    users = cursor.fetchall()
    conn.close()
    
    return render_template("users.html", users=users)

# Ручная проверка дней рождения
@app.route("/check_birthdays_manual")
@login_required
def check_birthdays_manual():
    """Ручная проверка с отправкой обоих типов уведомлений."""
    if session.get('username') != 'admin':
        flash('У вас нет прав для этой операции', 'danger')
        return redirect(url_for('index'))
    
    if not HAS_TELEGRAM:
        flash('Модуль Telegram уведомлений не настроен', 'warning')
        return redirect(url_for('index'))
    
    try:
        # Загружаем сотрудников
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT name, dob FROM employees")
        employees = cursor.fetchall()
        conn.close()
        
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        
        # 1. Напоминание на завтра
        birthdays_tomorrow = []
        for name, dob in employees:
            birth_date = datetime.strptime(dob, "%Y-%m-%d")
            if birth_date.strftime("%m-%d") == tomorrow.strftime("%m-%d"):
                birthdays_tomorrow.append((name, dob))
        
        if birthdays_tomorrow:
            message = "🎯 РУЧНАЯ ПРОВЕРКА: НАПОМИНАНИЕ 🎯\n\n"
            message += "ЗАВТРА ДЕНЬ РОЖДЕНИЯ!\n\n"
            
            message += "Именинники:\n"
            for name, dob in birthdays_tomorrow:
                birth_date = datetime.strptime(dob, "%Y-%m-%d")
                age = tomorrow.year - birth_date.year
                if (tomorrow.month, tomorrow.day) < (birth_date.month, birth_date.day):
                    age -= 1
                
                message += f"\n🎈 {name}"
                message += f"\n   🎂 Исполняется: {age} {get_age_suffix(age)}"
                message += f"\n   📅 {birth_date.strftime('%d.%m.%Y')}\n"
            
            message += "\n" + get_random_reminder()
            
            send_telegram_notification(message)
            flash(f'✅ Отправлено напоминание о {len(birthdays_tomorrow)} днях рождения завтра', 'success')
        else:
            flash('ℹ️  Завтра никто не празднует день рождения', 'info')
        
        # 2. Поздравления на сегодня
        birthdays_today = []
        for name, dob in employees:
            birth_date = datetime.strptime(dob, "%Y-%m-%d")
            if birth_date.strftime("%m-%d") == today.strftime("%m-%d"):
                birthdays_today.append((name, dob))
        
        if birthdays_today:
            message = "🎂 РУЧНАЯ ПРОВЕРКА: С ДНЁМ РОЖДЕНИЯ! 🎂\n\n"
            
            message += "СЕГОДНЯ СВОЙ ПРАЗДНИК ОТМЕЧАЮТ:\n\n"
            
            for idx, (name, dob) in enumerate(birthdays_today, 1):
                birth_date = datetime.strptime(dob, "%Y-%m-%d")
                age = today.year - birth_date.year
                if (today.month, today.day) < (birth_date.month, birth_date.day):
                    age -= 1
                
                message += f"{idx}. 🎈 {name}\n"
                message += f"   🎊 {age} {get_age_suffix(age)}!\n"
                message += f"   📅 {birth_date.strftime('%d.%m.%Y')}\n"
                message += f"   {get_random_congrat()}\n\n"
            
            message += "Желаем счастья, здоровья и успехов! 🥳"
            
            send_telegram_notification(message)
            flash(f'✅ Отправлены поздравления {len(birthdays_today)} именинникам', 'success')
        else:
            flash('ℹ️  Сегодня никто не празднует день рождения', 'info')
        
    except Exception as e:
        flash(f'❌ Ошибка при отправке: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

# Тестовое уведомление
@app.route("/send_test_notification")
@login_required
def send_test_notification():
    """Отправляет тестовое уведомление."""
    if not HAS_TELEGRAM:
        return jsonify({"success": False, "error": "Telegram модуль не настроен"})
    
    try:
        test_message = f"🧪 ТЕСТОВОЕ УВЕДОМЛЕНИЕ\n\n"
        test_message += f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        test_message += "Система уведомлений работает корректно!\n\n"
        test_message += "✅ Напоминания отправляются за день до ДР\n"
        test_message += "✅ Поздравления отправляются в день ДР"
        
        send_telegram_notification(test_message)
        
        return jsonify({"success": True, "message": "Тестовое уведомление отправлено"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ================ КОД ЗАПУСКА ВСЕГДА ВЫПОЛНЯЕТСЯ ================

print("\n" + "=" * 60)
print("🎂 СИСТЕМА УЧЁТА ДНЕЙ РОЖДЕНИЯ СОТРУДНИКОВ")
print("=" * 60)
print(f"📱 Telegram уведомления: {'✅ ВКЛЮЧЕНЫ' if HAS_TELEGRAM else '❌ ВЫКЛЮЧЕНЫ'}")
print("🔔 Типы уведомлений:")
print("   1. Напоминание за день до ДР")
print("   2. Поздравление в день ДР")
print("⏰ Автопроверка: каждые 6 часов")
print("🌐 Веб-интерфейс: http://localhost:5000")
print("👤 Логин: admin | 🔑 Пароль: admin123")
print("=" * 60)

# Отправляем уведомление о запуске
if HAS_TELEGRAM:
    try:
        startup_msg = f"🚀 СИСТЕМА ЗАПУЩЕНА\n\n"
        startup_msg += f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        startup_msg += "Система учета дней рождения сотрудников активна!\n\n"
        startup_msg += "Теперь уведомления будут приходить:\n"
        startup_msg += "1️⃣ За день до дня рождения (напоминание)\n"
        startup_msg += "2️⃣ В день рождения (поздравление)"
        
        send_telegram_notification(startup_msg)
        print("✅ Уведомление о запуске отправлено")
    except Exception as e:
        print(f"⚠️  Не удалось отправить уведомление о запуске: {e}")

# Запускаем Flask ВНЕ условий
app.run(host="0.0.0.0", port=5000, debug=False)
# ================ КОНЕЦ ================
