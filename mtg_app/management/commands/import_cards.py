import os
from decimal import Decimal

import pandas as pd
from django.core.management.base import BaseCommand

from mtg_app.models import Card, Set

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
file_path = os.path.join(BASE_DIR, "mtg_app", "management", "commands", "my_cards.csv")


class Command(BaseCommand):
    help = "Import MTG cards from a CSV file"

    def handle(self, *args, **options):
        file_path = r"C:\Users\User\Desktop\mtg_project\mtg_app\management\commands\my_cards.csv"
        df = pd.read_csv(file_path, encoding="utf-8")

        # Заменяем NaN на None
        df["Purchase price"] = df["Purchase price"].where(pd.notnull(df["Purchase price"]), None)
        df["Quantity"] = df["Quantity"].where(pd.notnull(df["Quantity"]), None)

        for _, row in df.iterrows():
            set_obj, _ = Set.objects.get_or_create(
                code=row["Set code"], defaults={"name": row["Set name"]}
            )

            # Преобразуем Purchase price в Decimal
            purchase_price = (
                Decimal(str(row["Purchase price"]))
                if pd.notnull(row["Purchase price"]) and row["Purchase price"] != ""
                else Decimal("0.00")
            )

            foil_value = (
                row["Foil"].strip().lower()
            )  # Убираем пробелы и приводим к нижнему регистру
            foil = (
                True if foil_value == "foil" else False
            )  # Преобразуем "foil" в True, а всё остальное в False

            card, created = Card.objects.get_or_create(
                scryfall_id=row["Scryfall ID"],
                defaults={
                    "name": row["Name"],
                    "set": set_obj,
                    "collector_number": row["Collector number"],
                    "foil": foil,  # <-- Теперь передаётся True/False
                    "rarity": row["Rarity"],
                    "quantity": row["Quantity"],
                    "purchase_price": purchase_price,
                    "language": row["Language"],
                    "condition": row["Condition"],
                },
            )

            if created:
                print(f"Добавлена карта: {card.name} ({card.set.name})")
            else:
                print(f"Карта уже существует: {card.name} ({card.set.name})")
