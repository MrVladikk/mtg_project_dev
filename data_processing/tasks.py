import os
import time
import requests
from decimal import Decimal
from celery import shared_task
from requests.adapters import HTTPAdapter, Retry

# --- Настройка Django (для запуска вне Django) ---
if "DJANGO_SETTINGS_MODULE" not in os.environ:
    # Убедитесь, что 'mtg_project.settings.dev' - правильный путь
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mtg_project.settings.dev")
import django
django.setup()
# -----------------------------------------------

from mtg_app.models import Card

# Вспомогательная функция для сессии (как в services.py)
def _session_with_retries() -> requests.Session:
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s

@shared_task
def update_all_card_prices():
    """
    Проходит по всем картам в БД и обновляет их *рыночную* цену из Scryfall API.
    """
    print("\n--- [CELERY BEAT] ЗАПУСК: Обновление рыночных цен... ---")
    session = _session_with_retries()
    
    # Получаем все ID карт, у которых есть Scryfall ID
    card_ids = Card.objects.exclude(scryfall_id__isnull=True).values_list('pk', 'name', 'scryfall_id')
    total_cards = card_ids.count()
    print(f"[INFO] Найдено {total_cards} карт для проверки.")
    
    updated_count = 0
    error_count = 0

    # Обрабатываем карты пачками (по одной, чтобы видеть лог)
    for i, (card_pk, card_name, scryfall_id) in enumerate(card_ids.iterator()):
        
        # Логгирование прогресса
        if i % 100 == 0:
            print(f"[INFO] Прогресс: {i} / {total_cards} карт...")
            
        try:
            # 1. Запрос к Scryfall API
            api_url = f"https://api.scryfall.com/cards/{scryfall_id}"
            response = session.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # 2. Поиск цены (приоритет: EUR, затем USD)
            price_str = None
            currency_str = "USD" # Валюта по умолчанию, если EUR нет

            if data.get('prices'):
                # --- ВОТ ЭТОТ БЛОК МЫ ИСПРАВИЛИ ---
                if data['prices'].get('eur'):
                    price_str = data['prices']['eur']
                    currency_str = "EUR"
                elif data['prices'].get('usd'):
                    price_str = data['prices']['usd']
                    currency_str = "USD"
                # ---------------------------------

            if price_str:
                new_price = Decimal(price_str)
                
                # 3. Обновляем цену и валюту в БД
                Card.objects.filter(pk=card_pk).update(
                    market_price=new_price, 
                    market_price_currency=currency_str
                )
                updated_count += 1
            
            # 4. Вежливость к API (100ms задержка)
            time.sleep(0.1) # 10 запросов в секунду

        except Exception as e:
            print(f"[ERROR] Не удалось обновить {card_name} (ID: {scryfall_id}): {e}")
            error_count += 1

    print(f"--- [CELERY BEAT] ЗАВЕРШЕНО ---")
    print(f"Успешно обновлено: {updated_count}, Ошибок: {error_count}")
    return f"Updated: {updated_count}, Errors: {error_count}"