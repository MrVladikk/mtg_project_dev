from django.urls import path

from . import views

app_name = "forum"

urlpatterns = [
    path("", views.thread_list, name="thread_list"),
    # Деталь: принимаем pk (текущая схема)
    path("thread/<int:pk>/", views.thread_detail, name="thread_detail"),
    # Алиас для старых вызовов reverse(..., kwargs={"thread_id": ...})
    path("thread/<int:thread_id>/", views.thread_detail, name="thread_detail_by_id"),
    path("thread/create/", views.thread_create, name="thread_create"),
    # Удаление темы (pk и алиас с thread_id)
    path("thread/<int:pk>/delete/", views.delete_thread, name="thread_delete"),
    path("thread/<int:thread_id>/delete/", views.delete_thread, name="thread_delete_by_id"),
    # Удаление поста (pk — как было в шаблоне)
    path("post/<int:pk>/delete/", views.delete_post, name="post_delete"),
]
