

from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime, timedelta
from send_notification import send_telegram_notification  # Телеграм отправка

app = Flask(__name__)

DB_NAME = "employees.db"

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dob TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.route("/", methods=["GET", "POST"])
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
                cursor.execute("INSERT INTO employees (name, dob) VALUES (?, ?)", (name, dob))
                conn.commit()
            return redirect(url_for('index'))

    # Получение сотрудников
    cursor.execute("SELECT name, dob FROM employees")
    rows = cursor.fetchall()
    employees = [{"name": r[0], "dob": r[1]} for r in rows]

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
        message = "🎉 Завтра день рождения:\n" + "\n".join(birthdays_tomorrow)
        send_telegram_notification(message)

    conn.close()

    return render_template(
        "index.html",
        employees=employees_sorted,
        birthdays_tomorrow=birthdays_tomorrow
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

