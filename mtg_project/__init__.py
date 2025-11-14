# Это гарантирует, что Celery загрузится при старте Django
from .celery import app as celery_app

__all__ = ('celery_app',)