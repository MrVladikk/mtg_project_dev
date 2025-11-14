# 1. Базовый образ
FROM python:3.12-slim-bookworm

# 2. Установка системных зависимостей (для Postgres)
RUN apt-get update \
    && apt-get install -y build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 3. Настройка рабочей директории
WORKDIR /app

# 4. Установка переменных окружения
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 5. Установка Python-библиотек
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Копирование всего проекта
COPY . .