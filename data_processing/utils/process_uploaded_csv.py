import csv
import os
import re
import tempfile

import requests
from django.conf import settings

from mtg_app.models import Card, Set


def sanitize_filename(name: str) -> str:
    """Очистка имени файла от недопустимых символов."""
    name = name.replace("/", "_").replace("//", "__")
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return name.strip() or "unknown_card"


def process_uploaded_csv(file_path: str) -> dict:
    """Обрабатывает CSV-файл с картами, создаёт записи и скачивает изображения."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    # Папка для сохранения изображений
    image_dir = os.path.join(settings.MEDIA_ROOT, "cards")
    os.makedirs(image_dir, exist_ok=True)

    processed_count = 0
    created_count = 0
    updated_count = 0
    error_count = 0
    image_download_success = 0
    image_download_errors = 0
    image_skipped_count = 0

    with open(file_path, encoding="utf-8-sig", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            processed_count += 1
            try:
                name = row.get("Name", "").strip()
                scryfall_id = row.get("Scryfall ID", "").strip()
                set_code = row.get("Set code", "").strip()
                set_name = row.get("Set name", "").strip()
                collector_number = row.get("Collector number", "").strip()

                if not scryfall_id or not set_code or not collector_number:
                    error_count += 1
                    continue

                set_obj, _ = Set.objects.get_or_create(code=set_code, defaults={"name": set_name})
                card, created = Card.objects.update_or_create(
                    scryfall_id=scryfall_id,
                    defaults={
                        "name": name,
                        "set": set_obj,
                        "collector_number": collector_number,
                        "foil": row.get("Foil", "").strip().lower() in ["foil", "true"],
                        "rarity": row.get("Rarity", "common"),
                        "quantity": int(row.get("Quantity", 1)),
                        "purchase_price": float(row.get("Purchase price", 0) or 0),
                        "language": row.get("Language", "English"),
                        "condition": row.get("Condition", "Near Mint"),
                    },
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

                # Скачиваем изображение
                image_url = row.get("Image URL", "").strip()
                if not image_url:
                    continue  # пока без Scryfall API для упрощения

                sanitized_name = sanitize_filename(name)
                image_ext = os.path.splitext(image_url)[1] or ".jpg"
                image_filename = f"{sanitized_name}_{collector_number}{image_ext}"
                image_path = os.path.join(image_dir, image_filename)

                if os.path.exists(image_path):
                    image_skipped_count += 1
                else:
                    try:
                        response = requests.get(image_url, timeout=10)
                        response.raise_for_status()
                        with open(image_path, "wb") as f:
                            f.write(response.content)
                        image_download_success += 1
                        card.image_url = f"cards/{image_filename}"
                        card.save(update_fields=["image_url"])
                    except Exception:
                        image_download_errors += 1

            except Exception as e:
                print(f"Ошибка при обработке строки: {e}")
                error_count += 1

    # Удаление временного файла
    try:
        temp_dir = tempfile.gettempdir()
        if os.path.realpath(file_path).startswith(temp_dir):
            os.remove(file_path)
    except Exception as e:
        print(f"Не удалось удалить временный файл: {e}")

    return {
        "processed": processed_count,
        "created": created_count,
        "updated": updated_count,
        "errors": error_count,
        "images_downloaded": image_download_success,
        "images_skipped": image_skipped_count,
    }
