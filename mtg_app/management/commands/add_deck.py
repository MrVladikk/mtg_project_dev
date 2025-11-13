import os

from django.core.management.base import BaseCommand, CommandError

from mtg_app.models import Card, Deck


class Command(BaseCommand):
    help = "Импортирует колоду из текстового файла и добавляет карты в базу данных."

    def add_arguments(self, parser):
        parser.add_argument(
            "--deck_file",
            "-f",
            type=str,
            required=True,
            help="Путь к текстовому файлу с описанием колоды (например, 'ashiok.txt').",
        )
        parser.add_argument("--deck_name", "-n", type=str, required=True, help="Название колоды.")
        parser.add_argument(
            "--deck_description",
            "-d",
            type=str,
            default="",
            help="Описание колоды (необязательно).",
        )

    def handle(self, *args, **options):
        deck_file = options["deck_file"]
        deck_name = options["deck_name"]
        deck_description = options["deck_description"]

        # Создаем колоду
        deck = Deck.objects.create(name=deck_name, description=deck_description)

        # Проверка наличия файла
        if not os.path.exists(deck_file):
            raise CommandError(f"Файл '{deck_file}' не найден.")

        try:
            with open(deck_file, encoding="utf-8") as file:
                for line in file:
                    line = line.strip()
                    if not line:
                        continue

                    # Если строка начинается с цифры, отделяем количество и название
                    if line[0].isdigit():
                        parts = line.split(" ", 1)
                        if len(parts) == 2:
                            # количество нам сейчас не нужно — игнорируем
                            _, card_name = parts
                        else:
                            card_name = parts[0]
                    else:
                        card_name = line

                    # Убираем лишние суффиксы вида " (foil)" и т.п.
                    card_name = card_name.split(" (")[0]

                    # Ищем карту в базе
                    card = Card.objects.filter(name__icontains=card_name).first()
                    if card:
                        deck.cards.add(card)
                        self.stdout.write(self.style.SUCCESS(f"Добавлена карта: {card.name}"))
                    else:
                        self.stdout.write(self.style.WARNING(f"Карта не найдена: {card_name}"))

            self.stdout.write(self.style.SUCCESS(f"Колода '{deck.name}' успешно создана!"))

        except Exception as err:
            # B904: важно указывать `from err`, чтобы сохранить цепочку исключений
            raise CommandError(f"Ошибка при добавлении колоды: {err}") from err
