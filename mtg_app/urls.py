from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "mtg_app"

urlpatterns = [
    path("", views.home, name="home"),
    # Карты
    path("cards/", views.card_list, name="cards_list"),
    path("cards/", views.card_list, name="card_list"),  # алиас для старых шаблонов
    path("cards/<int:pk>/", views.card_detail, name="card_detail"),
    path("cards/<int:pk>/", views.card_detail, name="cards_detail"),  # алиас
    # Сеты
    path("sets/", views.set_list, name="sets_list"),
    path("sets/", views.set_list, name="set_list"),  # алиас
    path("sets/<int:pk>/", views.set_detail, name="set_detail"),
    # Колоды
    path("decks/", views.deck_list, name="deck_list"),
    path("decks/", views.deck_list, name="decks_list"),  # алиас
    path("decks/<int:pk>/", views.deck_detail, name="deck_detail"),
    path("decks/<int:pk>/delete/", views.delete_deck, name="deck_delete"),
    path("decks/<int:pk>/delete/", views.delete_deck, name="decks_delete"),  # алиас
    # Добавление
    path("add-card/", views.add_card, name="add_card"),
    path("add-deck/", views.add_deck, name="add_deck"),
    # Аутентификация
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", views.custom_logout, name="logout"),
    path("register/", views.register, name="register"),
    
    # ...
    path('deck/<int:pk>/edit/', views.deck_edit, name='deck_edit'),
    path('deck/<int:pk>/delete/', views.deck_delete, name='deck_delete'),
    # ...
    path('api/get_card_image/', views.get_card_image, name='get_card_image'),
    
    # --- ДОБАВЬТЕ ЭТИ ДВЕ СТРОКИ (лучше в конец) ---
    path('api/get_user_decks/', views.get_user_decks, name='get_user_decks'),
    path('api/add_card_to_deck/', views.add_card_to_deck, name='add_card_to_deck'),
]
