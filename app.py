from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Секретный ключ для сессий
DB_NAME = "employees.db"

# Декоратор для проверки аутентификации
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблица сотрудников
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dob TEXT NOT NULL
        )
    """)
    
    # Таблица пользователей (админов)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    
    # Создаем дефолтного пользователя, если его нет
    cursor.execute("SELECT * FROM users WHERE username = ?", ('admin',))
    if not cursor.fetchone():
        hashed_password = generate_password_hash('admin123')
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                      ('admin', hashed_password))
        print("Создан дефолтный пользователь: admin / admin123")
    
    conn.commit()
    conn.close()

init_db()

# Маршрут входа в систему
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Если пользователь уже вошел, перенаправляем на главную
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

# Главная страница (только для авторизованных)
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Обработка формы добавления сотрудника
    if request.method == "POST":
        action = request.form.get("action")

        # Добавление сотрудника
        if action == "add_employee":
            name = request.form.get("name")
            dob = request.form.get("dob")
            if name and dob:
                # Проверяем, что дата не в будущем
                birth_date = datetime.strptime(dob, "%Y-%m-%d")
                if birth_date > datetime.now():
                    flash('Дата рождения не может быть в будущем', 'danger')
                else:
                    cursor.execute("INSERT INTO employees (name, dob) VALUES (?, ?)", (name, dob))
                    conn.commit()
                    flash(f'Сотрудник {name} успешно добавлен!', 'success')
            return redirect(url_for('index'))

    # Получение сотрудников
    cursor.execute("SELECT id, name, dob FROM employees")
    rows = cursor.fetchall()
    employees = [{"id": r[0], "name": r[1], "dob": r[2]} for r in rows]

    # Сортировка по месяцу и дню
    employees_sorted = sorted(
        employees,
        key=lambda x: datetime.strptime(x["dob"], "%Y-%m-%d").replace(year=1900)
    )

    # Завтра день рождения
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%m-%d")
    birthdays_tomorrow = [
        e["name"] for e in employees
        if datetime.strptime(e["dob"], "%Y-%m-%d").strftime("%m-%d") == tomorrow
    ]

    # Отправка уведомления, если есть у кого завтра ДР
    if birthdays_tomorrow:
        message = "🎉 Завтра день рождения Пиццаааааааааа Будет Уррррррааааааааааа:\n" + "\n".join(birthdays_tomorrow)
        # Раскомментируйте, если нужно отправлять уведомления
        # send_telegram_notification(message)
        flash(f'Завтра день рождения у {len(birthdays_tomorrow)} сотрудников!', 'info')

    conn.close()

    # Передаем текущую дату для расчета возраста в шаблоне
    return render_template(
        "index.html",
        employees=employees_sorted,
        birthdays_tomorrow=birthdays_tomorrow,
        username=session.get('username'),
        now=datetime.now()  # Важно: передаем текущую дату в шаблон
    )

# Удаление нескольких сотрудников
@app.route("/delete_employees", methods=["POST"])
@login_required
def delete_employees():
    ids_to_delete = request.form.getlist("delete_ids")
    if ids_to_delete:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Получаем имена удаляемых сотрудников для сообщения
        placeholders = ','.join(['?'] * len(ids_to_delete))
        cursor.execute(f"SELECT name FROM employees WHERE id IN ({placeholders})", ids_to_delete)
        deleted_names = [row[0] for row in cursor.fetchall()]
        
        # Удаляем сотрудников
        cursor.execute(f"DELETE FROM employees WHERE id IN ({placeholders})", ids_to_delete)
        conn.commit()
        conn.close()
        
        if deleted_names:
            names_str = ', '.join(deleted_names)
            flash(f'Удалены сотрудники: {names_str}', 'success')
        else:
            flash(f'Удалено {len(ids_to_delete)} сотрудников', 'success')
    return redirect(url_for('index'))

# Маршрут для управления пользователями (только для админа)
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
        
        elif action == "change_password":
            user_id = request.form.get("user_id")
            new_password = request.form.get("new_password")
            confirm_password = request.form.get("confirm_password_new")
            
            if new_password != confirm_password:
                flash('Пароли не совпадают', 'danger')
            elif len(new_password) < 6:
                flash('Пароль должен содержать минимум 6 символов', 'danger')
            else:
                hashed_password = generate_password_hash(new_password)
                cursor.execute("UPDATE users SET password = ? WHERE id = ?", 
                              (hashed_password, user_id))
                conn.commit()
                flash('Пароль успешно изменен', 'success')
    
    # Получение списка пользователей
    cursor.execute("SELECT id, username FROM users")
    users = cursor.fetchall()
    conn.close()
    
    return render_template("users.html", users=users)

# Маршрут для изменения своего пароля
@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Проверяем текущий пароль
        cursor.execute("SELECT password FROM users WHERE id = ?", (session.get('user_id'),))
        user = cursor.fetchone()
        
        if user and check_password_hash(user[0], current_password):
            if new_password != confirm_password:
                flash('Новые пароли не совпадают', 'danger')
            elif len(new_password) < 6:
                flash('Пароль должен содержать минимум 6 символов', 'danger')
            else:
                hashed_password = generate_password_hash(new_password)
                cursor.execute("UPDATE users SET password = ? WHERE id = ?", 
                              (hashed_password, session.get('user_id')))
                conn.commit()
                flash('Пароль успешно изменен!', 'success')
                conn.close()
                return redirect(url_for('index'))
        else:
            flash('Текущий пароль неверен', 'danger')
        
        conn.close()
    
    return render_template("change_password.html", username=session.get('username'))

# Маршрут для просмотра дней рождения в этом месяце
@app.route("/birthdays_this_month")
@login_required
def birthdays_this_month():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    current_month = datetime.now().strftime("%m")
    cursor.execute("SELECT name, dob FROM employees WHERE strftime('%m', dob) = ?", (current_month,))
    birthdays = cursor.fetchall()
    
    # Группируем по дню
    birthdays_by_day = {}
    for name, dob in birthdays:
        day = datetime.strptime(dob, "%Y-%m-%d").strftime("%d")
        if day not in birthdays_by_day:
            birthdays_by_day[day] = []
        birthdays_by_day[day].append(name)
    
    conn.close()
    
    return render_template(
        "birthdays_month.html",
        birthdays_by_day=birthdays_by_day,
        current_month=datetime.now().strftime("%B"),
        username=session.get('username')
    )

# Обработчик 404 ошибок
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# Обработчик 500 ошибок
@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True) 