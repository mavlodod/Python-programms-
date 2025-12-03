import sqlite3

# Подключение к базе
conn = sqlite3.connect("employees.db")
cursor = conn.cursor()

# Удаляем старую таблицу, если есть
cursor.execute("DROP TABLE IF EXISTS employees")

# Создаём новую таблицу
cursor.execute("""
CREATE TABLE employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    dob TEXT NOT NULL
)
""")

conn.commit()
conn.close()

print("База данных и таблица employees созданы заново!")
