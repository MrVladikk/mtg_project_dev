import os
from pathlib import Path
from urllib.parse import urlparse
from celery.schedules import crontab
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv()
# Безопасность и режим
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "insecure")
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"
ALLOWED_HOSTS_STR = os.environ.get('ALLOWED_HOSTS', '')

ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # ваши приложения:
    "mtg_app.apps.MtgAppConfig",
    "forum.apps.ForumConfig",
    "data_processing.apps.DataProcessingConfig",
    "django_filters",
    'bootstrap5',
    'django_celery_results',
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "mtg_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.media",
            ],
        },
    }
]

WSGI_APPLICATION = "mtg_project.wsgi.application"
ASGI_APPLICATION = "mtg_project.asgi.application"

# БД: если задан DATABASE_URL — используем Postgres; иначе SQLite.
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    url = urlparse(DATABASE_URL)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": url.path[1:],
            "USER": url.username,
            "PASSWORD": url.password,
            "HOST": url.hostname,
            "PORT": url.port or 5432,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [BASE_DIR / "mtg_app" / "static"]


MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_REDIRECT_URL = "mtg_app:home"
LOGOUT_REDIRECT_URL = "mtg_app:home"

# --- CELERY SETTINGS ---
# Указываем, что Redis (наш брокер) работает на стандартном порту
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'django-db' # <-- Теперь Celery будет писать в вашу базу
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE # Используем часовой пояс из Django

# --- CELERY BEAT SCHEDULE ---
CELERY_BEAT_SCHEDULE = {
    'update-card-prices-daily': {
        'task': 'data_processing.tasks.update_all_card_prices',
        # crontab(minute=0, hour=4) = запускать в 4:00 ночи
        'schedule': crontab(minute=0, hour=4), 
    },
}