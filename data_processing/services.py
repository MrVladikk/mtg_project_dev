# data_processing/services.py
from __future__ import annotations

import csv
import os
import re
import time
from decimal import Decimal
from pathlib import Path

import requests

# Настройка Django
if "DJANGO_SETTINGS_MODULE" not in os.environ:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mtg_project.settings.dev")

import django

django.setup()

from django.conf import settings
from django.db import transaction
from requests.adapters import HTTPAdapter, Retry

from mtg_app.models import Card, Set

# --- ХЕЛПЕРЫ ---


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


def _ensure_media_cards_dir() -> tuple[Path, str]:
    media_root = getattr(settings, "MEDIA_ROOT", None)
    if media_root:
        base = Path(media_root)
    else:
        # Если MEDIA_ROOT не настроен, кидаем в папку проекта (для теста)
        base = Path(__file__).resolve().parents[2] / "media"

    save_dir = base / "cards"
    save_dir.mkdir(parents=True, exist_ok=True)
    return save_dir, "cards"


def _sanitize_filename(name: str) -> str:
    # Убираем плохие символы для Windows/Linux
    name = re.sub(r"[\\/*?\"<>|:#]", "_", name)
    name = re.sub(r"\s+", "_", name).strip("_")
    return name[:150]  # Ограничиваем длину


def _session_with_retries() -> requests.Session:
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s


def _ext_from_content_type(ctype: str) -> str:
    c = (ctype or "").lower()
    if "png" in c:
        return ".png"
    if "webp" in c:
        return ".webp"
    return ".jpg"  # По умолчанию jpg


# --- ОСНОВНАЯ ФУНКЦИЯ ---


@transaction.atomic
def process_uploaded_csv(
    file_path: str, *, throttle_sec: float = 0.15
) -> tuple[dict[str, int], list[str]]:

    counters = {
        "created": 0,
        "updated": 0,
        "errors": 0,
        "downloaded": 0,
        "skipped_img_exists": 0,
        "skipped_img_missing": 0,
        "duplicates_summed": 0,
    }
    errors_list = []

    save_dir, db_prefix = _ensure_media_cards_dir()
    session = _session_with_retries()

    # Кэш для суммирования дубликатов внутри одного файла
    # scryfall_id -> True
    processed_ids_in_run = set()

    print("\n=== [SERVICE] ЗАПУСК ИМПОРТА ===")
    print(f"Файл: {file_path}")
    print(f"Папка сохранения: {save_dir}")

    with open(file_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        field_map = {key.lower().strip(): key for key in (reader.fieldnames or [])}

        if not field_map:
            msg = "CSV файл пуст или не имеет заголовков."
            print(f"[CRITICAL] {msg}")
            return counters, [msg]

        for i, row in enumerate(reader):
            row_num = i + 2

            try:
                # --- 1. ЧТЕНИЕ ДАННЫХ ---
                scryfall_id = _get_row_val(row, field_map, "scryfall id")
                name = _get_row_val(row, field_map, "name")
                set_code = _get_row_val(row, field_map, "set code")
                set_name = _get_row_val(row, field_map, "set name")

                if not scryfall_id or not name:
                    print(f"[ROW {row_num}] ПРОПУСК: Нет ID или Имени.")
                    counters["errors"] += 1
                    continue

                print(f"\n>>> [ROW {row_num}] Обработка: {name} ({set_code})")

                # Парсим числовые поля
                qty_str = _get_row_val(row, field_map, "quantity")
                try:
                    quantity = int(float(qty_str or 1))
                except:
                    quantity = 1

                price_str = _get_row_val(row, field_map, "purchase price").replace(",", ".")
                try:
                    price = Decimal(price_str or "0")
                except:
                    price = Decimal("0")

                foil_raw = _get_row_val(row, field_map, "foil").lower()
                foil = foil_raw in ("true", "1", "foil", "yes", "y", "фольга")

                # --- 2. РАБОТА С БД (Создание / Обновление / Суммирование) ---

                # Создаем сет, если нет
                mtg_set, _ = Set.objects.get_or_create(
                    code=set_code, defaults={"name": set_name or set_code}
                )

                # Проверяем, была ли эта карта уже в ЭТОМ файле
                is_duplicate = scryfall_id in processed_ids_in_run

                if is_duplicate:
                    # Просто добавляем количество к существующей карте
                    card = Card.objects.get(scryfall_id=scryfall_id)
                    card.quantity += quantity
                    card.save(update_fields=["quantity"])
                    print(
                        f"    [DB] Дубликат в файле. Добавлено +{quantity} шт. (Итого: {card.quantity})"
                    )
                    counters["duplicates_summed"] += 1

                else:
                    # Это первое вхождение в файле. Создаем или обновляем.
                    defaults = {
                        "name": name,
                        "set": mtg_set,
                        "collector_number": _get_row_val(row, field_map, "collector number"),
                        "foil": foil,
                        "rarity": _get_row_val(row, field_map, "rarity"),
                        "quantity": quantity,
                        "purchase_price": price,
                        "language": _get_row_val(row, field_map, "language"),
                        "condition": _get_row_val(row, field_map, "condition"),
                    }

                    card, created = Card.objects.get_or_create(
                        scryfall_id=scryfall_id, defaults=defaults
                    )

                    if created:
                        print("    [DB] Создана новая карта.")
                        counters["created"] += 1
                    else:
                        # Обновляем поля существующей карты
                        updated_fields = []
                        # Принудительно обновляем количество на то, что в файле (перезапись)
                        # Если вы хотите СУММИРОВАТЬ с базой, измените строку ниже:
                        # card.quantity += quantity
                        card.quantity = quantity
                        updated_fields.append("quantity")

                        card.name = name
                        card.set = mtg_set
                        card.purchase_price = price
                        card.foil = foil

                        card.save()
                        print("    [DB] Обновлена существующая карта.")
                        counters["updated"] += 1

                    # Запоминаем, что мы видели этот ID
                    processed_ids_in_run.add(scryfall_id)

                # --- 3. РАБОТА С ИЗОБРАЖЕНИЕМ (СКАЧИВАНИЕ) ---
                # Мы проверяем картинку ВСЕГДА, даже для дубликатов

                col_num = card.collector_number or "000"
                base_filename = _sanitize_filename(f"{name}__{col_num}")

                # А. Проверяем физическое наличие файла
                file_exists = False
                for ext in [".jpg", ".png", ".webp"]:
                    physical_path = save_dir / f"{base_filename}{ext}"
                    if physical_path.exists():
                        # Файл есть. Обновляем путь в БД и выходим
                        db_path = f"{db_prefix}/{base_filename}{ext}"
                        if card.image_url != db_path:
                            card.image_url = db_path
                            card.save(update_fields=["image_url"])
                        print(f"    [IMG] Файл найден локально ({physical_path.name}). Пропуск.")
                        counters["skipped_img_exists"] += 1
                        file_exists = True
                        break

                if file_exists:
                    continue  # Переходим к следующей строке

                # Б. Файла НЕТ. Начинаем поиск ссылки.
                print("    [IMG] Файла нет. Ищем URL...")

                url_to_download = _get_row_val(row, field_map, "image url")

                # Если в CSV пусто, идем на Scryfall
                if not url_to_download:
                    print(f"    [API] Запрос к Scryfall (ID: {scryfall_id})...")
                    try:
                        time.sleep(throttle_sec)  # Вежливость
                        api_resp = session.get(
                            f"https://api.scryfall.com/cards/{scryfall_id}", timeout=10
                        )
                        api_resp.raise_for_status()
                        data = api_resp.json()

                        # Логика выбора картинки
                        if "image_uris" in data:
                            url_to_download = data["image_uris"].get("large") or data[
                                "image_uris"
                            ].get("png")
                        elif "card_faces" in data:
                            # Для двусторонних берем первую сторону
                            url_to_download = data["card_faces"][0]["image_uris"].get("large")

                        if url_to_download:
                            print("    [API] URL получен.")
                        else:
                            print("    [API] URL не найден в ответе Scryfall.")
                    except Exception as e:
                        print(f"    [API] Ошибка запроса: {e}")

                # В. Скачивание
                if url_to_download:
                    print(f"    [DL] Скачивание с {url_to_download}...")
                    try:
                        dl_resp = session.get(url_to_download, timeout=20)
                        dl_resp.raise_for_status()

                        # Определяем расширение
                        ext = _ext_from_content_type(dl_resp.headers.get("Content-Type"))
                        final_filename = f"{base_filename}{ext}"
                        final_path = save_dir / final_filename

                        with open(final_path, "wb") as f_img:
                            f_img.write(dl_resp.content)

                        # Сохраняем путь в БД
                        card.image_url = f"{db_prefix}/{final_filename}"
                        card.save(update_fields=["image_url"])

                        print(f"    [DL] УСПЕХ! Сохранено как {final_filename}")
                        counters["downloaded"] += 1

                    except Exception as e:
                        print(f"    [DL] Ошибка скачивания: {e}")
                        counters["errors"] += 1
                else:
                    print("    [IMG] Не удалось найти URL нигде. Пропуск.")
                    counters["skipped_img_missing"] += 1

            except Exception as e:
                msg = f"CRITICAL ERROR в строке {row_num}: {e}"
                print(f"[CRITICAL] {msg}")
                errors_list.append(msg)
                counters["errors"] += 1

    print("\n=== [SERVICE] ИМПОРТ ЗАВЕРШЕН ===")
    return counters, errors_list
