import os
from celery import Celery

# Устанавливаем переменную окружения для настроек Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mtg_project.settings.base')

app = Celery('mtg_project')

# Используем конфиг из settings.py (CELERY_BROKER_URL и т.д.)
app.config_from_object('django.conf:settings', namespace='CELERY')

# app.autodiscover_tasks() # Этот метод ищет только файлы с именем tasks.py

# --- ИСПРАВЛЕНИЕ: Указываем задачи вручную ---
# Мы явно говорим Celery загрузить задачи из ОБОИХ файлов.
app.autodiscover_tasks(
    related_name='tasks', # Это найдет data_processing/tasks.py
)
app.autodiscover_tasks(
    related_name='services', # Это найдет data_processing/services.py
)
# ---------------------------------------------