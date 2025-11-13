import os

from django.core.management.base import BaseCommand

from mtg_app.models import Card


class Command(BaseCommand):
    help = "Обновляет пути к изображениям карт в базе данных."

    def handle(self, *args, **options):
        # Папка для сохранения изображений
        image_folder = os.path.join("mtg_app", "static", "mtg_app", "images", "cards")

        # Получаем все карты из базы данных
        cards = Card.objects.all()

        for card in cards:
            # Формируем имя файла на основе названия карты и номера коллекции
            image_name = f"{card.name.replace('//', '__')}_{card.collector_number}.jpg"

            # Путь к изображению относительно папки static
            image_path = os.path.join("mtg_app", "images", "cards", image_name)

            # Полный путь к изображению на диске
            full_path = os.path.join(image_folder, image_name)

            # Проверяем, существует ли файл
            if os.path.exists(full_path):
                # Обновляем ссылку на изображение в базе данных
                card.image_url = image_path
                card.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Обновлено изображение для карты: {card.name} (Number: {card.collector_number}) -> {image_path}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Изображение не найдено для карты: {card.name} (Number: {card.collector_number}) (путь: {full_path})"
                    )
                )
