# data_processing/services.py
from __future__ import annotations
import csv, os, re, time, requests
from pathlib import Path
from typing import Dict, Tuple, List
from decimal import Decimal, InvalidOperation
from celery import shared_task

# Настройка Django
if "DJANGO_SETTINGS_MODULE" not in os.environ:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mtg_project.settings.dev")
import django
django.setup()

from django.conf import settings
from django.db import transaction
from requests.adapters import HTTPAdapter, Retry
from mtg_app.models import Card, Set

# --- Хелперы (без изменений) ---
def _get_row_val(row: dict, field_map: dict, key: str) -> str:
    key_lower = key.lower()
    if key_lower in field_map:
        return (row.get(field_map[key_lower]) or "").strip()
    aliases = {
        "name": ["card name", "название", "имя"],
        "quantity": ["count", "qty", "количество", "кол-во"],
        "set code": ["set"],
        "set name": ["set name (english)", "название сета", "сет"],
        "collector number": ["card number", "number", "номер", "№"],
        "purchase price": ["price", "cost", "цена", "цена покупки"],
        "purchase price currency": ["currency", "валюта"],
        "scryfall id": ["scryfall_id", "scryfallid", "id"],
        "image url": ["image", "url", "картинка"],
        "foil": ["фольга", "foil"],
        "rarity": ["редкость", "rarity"],
        "language": ["язык", "language"],
        "condition": ["состояние", "condition"],
    }
    for alias in aliases.get(key_lower, []):
        if alias in field_map:
            return (row.get(field_map[alias]) or "").strip()
    return ""

def _ensure_media_cards_dir() -> Tuple[Path, str]:
    from django.conf import settings # Локальный импорт
    media_root = getattr(settings, "MEDIA_ROOT", None)
    if media_root: base = Path(media_root)
    else: base = Path(__file__).resolve().parents[2] / "media"
    save_dir = base / "cards"
    save_dir.mkdir(parents=True, exist_ok=True)
    return save_dir, "cards"

def _sanitize_filename(name: str) -> str:
    name = re.sub(r"[\\/*?\"<>|:#]", "_", name)
    name = re.sub(r"\s+", "_", name).strip("_")
    return name[:150]

def _session_with_retries() -> requests.Session:
    import requests # Локальный импорт
    from requests.adapters import HTTPAdapter, Retry
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s

def _ext_from_content_type(ctype: str) -> str:
    c = (ctype or "").lower()
    if "png" in c: return ".png"
    if "webp" in c: return ".webp"
    return ".jpg"

# --- ОСНОВНАЯ ФУНКЦИЯ (ПЕРЕРАБОТАНА) ---

@shared_task(bind=True)
def process_uploaded_csv(self, file_path: str, *, throttle_sec: float = 0.1) -> Dict[str, int]:
    
    counters = {"created": 0, "updated": 0, "errors": 0, "downloaded": 0, "enriched": 0, "skipped_img_exists": 0}
    errors_list = []
    save_dir, db_prefix = _ensure_media_cards_dir()
    session = _session_with_retries()
    processed_ids_in_run = set()

    print("\n--- [START] УМНЫЙ ИМПОРТ v2 (с починкой картинок) ---")
    
    try:
        # Читаем файл в память, чтобы узнать ОБЩЕЕ КОЛИЧЕСТВО
        with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
            reader_list = list(csv.DictReader(f))
            total_rows = len(reader_list)
        
        field_map = {key.lower().strip(): key for key in (reader_list[0].keys() if total_rows > 0 else [])}
        
        if not field_map: raise ValueError("CSV пуст или не имеет заголовков.")

        for i, row in enumerate(reader_list):
            row_num = i + 2
            card = None 
            
            # --- 1. ОБНОВЛЕНИЕ ПРОГРЕССА ---
            # Сообщаем Celery, что мы на строке i из total_rows
            self.update_state(state='PROGRESS', 
                              meta={'current': i + 1, 'total': total_rows})
            
            try:
                # --- 2. ЧТЕНИЕ ДАННЫХ ИЗ CSV ---
                scryfall_id = _get_row_val(row, field_map, "scryfall id")
                name = _get_row_val(row, field_map, "name")
                set_code = _get_row_val(row, field_map, "set code")
                
                if not scryfall_id or not name or not set_code:
                    msg = f"Строка {row_num}: Нет ID, Имени или Кода Сета. Пропуск."
                    print(f"[ERROR] {msg}")
                    errors_list.append(msg)
                    counters["errors"] += 1
                    continue

                print(f"\n>>> [ROW {row_num}/{total_rows}] Обработка: {name} ({set_code})")
                
                qty_str = _get_row_val(row, field_map, "quantity")
                try: quantity = int(float(qty_str or 1))
                except: quantity = 1
                
                price_str = _get_row_val(row, field_map, "purchase price").replace(",", ".")
                try: price = Decimal(price_str or "0")
                except: price = Decimal("0")

                mtg_set, _ = Set.objects.get_or_create(code=set_code, defaults={"name": _get_row_val(row, field_map, "set name") or set_code})

                # --- 3. РАБОТА С БД ---
                card, created = Card.objects.get_or_create(
                    scryfall_id=scryfall_id,
                    defaults={
                        "name": name, "set": mtg_set,
                        "collector_number": _get_row_val(row, field_map, "collector number"),
                        "rarity": _get_row_val(row, field_map, "rarity"),
                        "language": _get_row_val(row, field_map, "language"),
                        "condition": _get_row_val(row, field_map, "condition"),
                        "foil": _get_row_val(row, field_map, "foil").lower() in ("true", "1", "foil", "yes", "y", "фольга"),
                        "quantity": quantity,
                        "purchase_price": price,
                        "purchase_price_currency": _get_row_val(row, field_map, "purchase price currency").upper() or "RUB",
                    }
                )

                if created:
                    print(f"    [DB] Создана новая карта.")
                    counters["created"] += 1
                elif scryfall_id not in processed_ids_in_run:
                    card.quantity = quantity
                    card.purchase_price = price
                    print(f"    [DB] Найдена. Количество обновлено до {quantity}.")
                    counters["updated"] += 1
                else:
                    card.quantity += quantity
                    print(f"    [DB] Дубликат в файле. Количество увеличено до {card.quantity}.")

                processed_ids_in_run.add(scryfall_id)
                card.save() # Сохраняем изменения (quantity)

                # --- 4. ОБОГАЩЕНИЕ ДАННЫМИ (Scryfall API) ---
                # (Только если текстовых данных нет)
                if card.cmc == 0:
                    print(f"    [API] Текст. данные неполные. Запрос к Scryfall...")
                    try:
                        time.sleep(throttle_sec)
                        api_resp = session.get(f"https://api.scryfall.com/cards/{scryfall_id}", timeout=10)
                        api_resp.raise_for_status()
                        data = api_resp.json()
                        
                        card.cmc = data.get('cmc', 0.0)
                        card.mana_cost = data.get('mana_cost', '')
                        card.type_line = data.get('type_line', '')
                        card.oracle_text = data.get('oracle_text', '')
                        card.colors = "".join(data.get('colors', []))
                        card.save()
                        print(f"    [API] Данные обогащены (CMC: {card.cmc})")
                        counters["enriched"] += 1
                    except Exception as e:
                        print(f"    [API] Ошибка обогащения: {e}")
                
                # --- 5. СКАЧИВАНИЕ ИЗОБРАЖЕНИЯ (ОТДЕЛЬНАЯ ЛОГИКА) ---
                base_filename = _sanitize_filename(f"{name}__{card.collector_number}")
                
                # A. Проверяем, есть ли файл локально
                file_exists = False
                for ext in [".jpg", ".png", ".webp"]:
                    path_check = save_dir / f"{base_filename}{ext}"
                    if path_check.exists():
                        file_exists = True
                        counters["skipped_img_exists"] += 1
                        db_path = f"{db_prefix}/{base_filename}{ext}"
                        if card.image_url != db_path: # Самоисцеление, если путь в БД неверный
                            card.image_url = db_path
                            card.save(update_fields=['image_url'])
                        break
                
                if file_exists:
                    print(f"    [IMG] Файл уже существует. Пропуск.")
                    continue

                # B. Файла НЕТ. Ищем URL.
                print(f"    [IMG] Файл не найден. Поиск URL...")
                image_url_to_download = _get_row_val(row, field_map, "image url")
                
                # C. Если в CSV нет URL, ИДЕМ В API (даже если cmc != 0)
                if not image_url_to_download:
                    print(f"    [API] URL нет в CSV. Запрос к Scryfall...")
                    try:
                        time.sleep(throttle_sec) # Вежливость
                        api_resp = session.get(f"https://api.scryfall.com/cards/{scryfall_id}", timeout=10)
                        api_resp.raise_for_status()
                        data = api_resp.json()
                        if "image_uris" in data:
                            image_url_to_download = data["image_uris"].get("large") or data["image_uris"].get("png")
                        elif "card_faces" in data:
                            image_url_to_download = data["card_faces"][0]["image_uris"].get("large")
                        
                        if image_url_to_download:
                            print(f"    [API] URL картинки получен.")
                    except Exception as e:
                        print(f"    [API] Ошибка получения URL: {e}")

                # D. Скачивание
                if image_url_to_download:
                    print(f"    [DL] Скачивание...")
                    try:
                        dl_resp = session.get(image_url_to_download, timeout=20)
                        dl_resp.raise_for_status()
                        ext = _ext_from_content_type(dl_resp.headers.get("Content-Type"))
                        final_filename = f"{base_filename}{ext}"
                        final_path = save_dir / final_filename
                        
                        with open(final_path, "wb") as f_img:
                            f_img.write(dl_resp.content)
                            
                        card.image_url = f"{db_prefix}/{final_filename}"
                        card.save(update_fields=["image_url"])
                        
                        print(f"    [DL] УСПЕХ! Сохранено как {final_filename}")
                        counters["downloaded"] += 1
                    except Exception as e:
                        print(f"    [DL] Ошибка скачивания: {e}")
                        counters["errors"] += 1
                else:
                    print(f"    [IMG] URL для скачивания не найден.")
                    counters["skipped_img_missing"] += 1 # Новая категория

            except Exception as e:
                msg = f"CRITICAL ERROR в строке {row_num}: {e}"
                print(f"[CRITICAL] {msg}")
                errors_list.append(msg)
                counters["errors"] += 1
    
    except Exception as e:
        msg = f"Не удалось прочитать файл {file_path}: {e}"
        print(f"[CRITICAL] {msg}")
        errors_list.append(msg)
        counters["errors"] += 1
    
    finally:
        print("\n[INFO] --- Цикл завершен, очистка файла ---")
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"[INFO] Временный файл {file_path} успешно удален.")
            except Exception as e:
                print(f"[ERROR] Не удалось удалить временный файл {file_path}: {e}")

    print("[INFO] --- ПРОФЕССИОНАЛЬНЫЙ ИМПОРТ ЗАВЕРШЕН ---")
    return counters