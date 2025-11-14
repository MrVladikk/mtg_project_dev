from django.urls import path
from . import views

app_name = "data_processing"

urlpatterns = [
    path("upload/", views.upload_csv, name="upload_csv"),
    # --- ДОБАВЬТЕ ЭТУ СТРОКУ ---
    path("api/get_task_status/", views.get_task_status, name="get_task_status"),
    path("trigger-price-update/", views.trigger_price_update, name="trigger_price_update"),
]