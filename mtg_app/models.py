import posixpath
from urllib.parse import quote, urlsplit, urlunsplit
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db import models
from django.templatetags.static import static

User = get_user_model()

class Set(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    release_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def card_count(self) -> int:
        return self.cards.count()

class Card(models.Model):
    scryfall_id = models.CharField(max_length=100, unique=True, verbose_name="Scryfall ID")
    name = models.CharField(max_length=200, verbose_name="Название")
    set = models.ForeignKey(Set, on_delete=models.CASCADE, verbose_name="Сет", related_name="cards")
    collector_number = models.CharField(max_length=20, verbose_name="Коллекционный номер")
    foil = models.BooleanField(default=False, verbose_name="Фоил")
    rarity = models.CharField(max_length=50, verbose_name="Редкость")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество") # Общее кол-во в коллекции
    purchase_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Цена покупки"
    )
    language = models.CharField(max_length=50, blank=True, verbose_name="Язык")
    condition = models.CharField(max_length=50, blank=True, verbose_name="Состояние")
    image_url = models.URLField(max_length=500, blank=True, verbose_name="Ссылка на изображение")
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="cards", null=True, blank=True
    )
    cmc = models.FloatField(default=0.0, verbose_name="Мана-стоимость (CMC)")
    mana_cost = models.CharField(max_length=50, blank=True, verbose_name="Символы маны")
    type_line = models.CharField(max_length=255, blank=True, verbose_name="Тип карты")
    oracle_text = models.TextField(blank=True, verbose_name="Текст карты")
    colors = models.CharField(max_length=50, blank=True, verbose_name="Цвета (WUBRG)")
    market_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Рыночная цена")
    purchase_price_currency = models.CharField(max_length=3, default="RUB", verbose_name="Валюта покупки")
    market_price_currency = models.CharField(max_length=3, default="USD", verbose_name="Валюта рынка")

    def __str__(self) -> str:
        return self.name
    
    # (Функция image_src() была здесь, но она не используется в шаблонах, 
    # которые мы сделали, поэтому я ее убрал, чтобы не было ошибок 'posixpath')
    # Если она вам нужна, убедитесь, что импорты posixpath и т.д. есть вверху


class Deck(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название колоды")
    description = models.TextField(blank=True, verbose_name="Описание")
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="decks", null=True, blank=True
    )
    is_private = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # --- ОСТАВЛЕНА ТОЛЬКО ОДНА ПРАВИЛЬНАЯ СВЯЗЬ ---
    cards = models.ManyToManyField(
        Card, 
        through='DeckCard', # <-- Связь через модель DeckCard
        verbose_name="Карты в колоде",
        blank=True
    )

    def __str__(self) -> str:
        return self.name

    def get_total_quantity(self):
        total = 0
        for item in self.deckcard_set.all():
            total += item.quantity
        return total

class DeckCard(models.Model):
    deck = models.ForeignKey(Deck, on_delete=models.CASCADE)
    card = models.ForeignKey(Card, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")

    class Meta:
        unique_together = ('deck', 'card') 

    def __str__(self):
        return f"{self.quantity}x {self.card.name}"