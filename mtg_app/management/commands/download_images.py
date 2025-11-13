import csv
import os
import time

import requests
from django.core.management.base import BaseCommand
from tqdm import tqdm


class Command(BaseCommand):
    help = "Загружает изображения карт по их Scryfall ID из CSV файла."

    def handle(self, *args, **options):
        # Папка для сохранения изображений
        IMAGE_FOLDER = r"C:\Users\User\Desktop\mtg_project\mtg_app\static\mtg_app\images\cards"

        # Функция для загрузки изображения по Scryfall ID
        def download_image(scryfall_id, card_name, collector_number):
            url = f"https://api.scryfall.com/cards/{scryfall_id}?format=image"
            response = requests.get(url)

            if response.status_code == 200:
                # Создаем папку для сохранения изображений, если она не существует
                os.makedirs(IMAGE_FOLDER, exist_ok=True)

                # Формируем уникальное имя файла с учетом названия и номера коллекции
                file_name = f"{card_name}_{collector_number}.jpg"
                file_path = os.path.join(IMAGE_FOLDER, file_name)

                with open(file_path, "wb") as f:
                    f.write(response.content)
                self.stdout.write(self.style.SUCCESS(f"Downloaded {file_name}"))
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"Failed to download image for {card_name} (Scryfall ID: {scryfall_id})"
                    )
                )

        # Функция для проверки, существует ли файл с изображением
        def is_image_downloaded(card_name, collector_number):
            file_name = f"{card_name}_{collector_number}.jpg"
            file_path = os.path.join(IMAGE_FOLDER, file_name)
            return os.path.exists(file_path)

        # Чтение CSV файла
        csv_path = r"C:\Users\User\Desktop\mtg_project\mtg_app\management\commands\my_cards.csv"

        with open(csv_path, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)  # Читаем все строки, чтобы корректно посчитать количество карт

            # Используем tqdm для отображения прогресс-бара
            for row in tqdm(rows, total=len(rows), desc="Downloading images"):
                scryfall_id = row["Scryfall ID"]
                card_name = row["Name"].replace("/", "_")  # Заменяем слэши в названии
                collector_number = row["Collector number"]  # Номер коллекции

                # Проверяем, скачано ли изображение
                if not is_image_downloaded(card_name, collector_number):
                    download_image(scryfall_id, card_name, collector_number)
                    time.sleep(0.5)  # Задержка между запросами, чтобы избежать блокировки
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Image for {card_name} (Number: {collector_number}) already exists. Skipping download."
                        )
                    )
