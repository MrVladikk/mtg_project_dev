from django.urls import path

from . import views

app_name = "data_processing"  # Пространство имен для URL (хорошая практика)

urlpatterns = [
    path("upload/", views.upload_csv, name="upload_csv"),
]
