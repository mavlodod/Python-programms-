# Базовый образ
FROM python:3.11-slim

# Рабочая директория
WORKDIR /app

# Копируем файлы проекта
COPY . /app

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Открываем порт
EXPOSE 5000

# Команда запуска
CMD ["python", "app.py"]
