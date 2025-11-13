import posixpath
from urllib.parse import quote, urlsplit, urlunsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db import models
from django.templatetags.static import static

User = get_user_model()


class Set(models.Model):
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=100)

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
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")
    purchase_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Цена покупки"
    )
    language = models.CharField(max_length=50, verbose_name="Язык")
    condition = models.CharField(max_length=50, verbose_name="Состояние")
    image_url = models.URLField(max_length=500, blank=True, verbose_name="Ссылка на изображение")
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="cards", null=True, blank=True
    )

    def image_src(self) -> str:
        """
        Корректный src для <img>:
        - Абсолютные URL (http/https/data, а также //host/...) — отдаем как есть.
        - Относительные приводим к пути в сторадже (под cards/), проверяем существование
          через default_storage.exists(), и отдаем default_storage.url().
        - Если файла нет — плейсхолдер из static.
        """
        placeholder = static("mtg_app/images/placeholder_card.png")

        raw = (self.image_url or "").strip()
        if not raw:
            return placeholder

        # Абсолютные URL?
        sp = urlsplit(raw)
        if sp.scheme in ("http", "https", "data") or (sp.scheme == "" and raw.startswith("//")):
            return raw

        # Приводим относительный путь к POSIX-формату
        p = raw.lstrip("/").replace("\\", "/")

        # Срезаем варианты префикса медиа-URL, если вдруг они попали в БД/вход
        media_url = (settings.MEDIA_URL or "").lstrip("/")
        if media_url and p.startswith(media_url):
            p = p[len(media_url) :].lstrip("/")
        if p.startswith("media/"):
            p = p[len("media/") :]

        # Удаляем старый промежуточный префикс проекта
        if p.startswith("mtg_app/images/"):
            p = p.split("mtg_app/images/", 1)[1]

        # Нормализация и защита от ../
        p = posixpath.normpath(p).lstrip("./")

        # Если это только имя файла (без слэшей) — складываем под cards/
        if "/" not in p:
            p = f"cards/{p}"

        # Финальная нормализация и запрет на выход выше корня
        p = posixpath.normpath(p).replace("\\", "/")
        if p.startswith("../"):
            p = p.lstrip("../")

        # Проверяем наличие в сторадже
        if not default_storage.exists(p):
            return placeholder

        # Получаем URL от стораджа
        url = default_storage.url(p)

        # Аккуратно экранируем path-часть (на случай пробелов и не-ASCII в локальном FileSystemStorage)
        usp = urlsplit(url)
        safe_path = quote(usp.path, safe="/%")
        return urlunsplit((usp.scheme, usp.netloc, safe_path, usp.query, usp.fragment))

    def __str__(self) -> str:
        return self.name


class Deck(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название колоды")
    description = models.TextField(blank=True, verbose_name="Описание")
    cards = models.ManyToManyField(Card, verbose_name="Карты в колоде", blank=True)
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="decks", null=True, blank=True
    )
    is_private = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    cards = models.ManyToManyField(Card, through='DeckCard')

    def __str__(self) -> str:
        return self.name

    def get_total_quantity(self):
        """Считает сумму всех карт (учитывая количество каждой)"""
        total = 0
        for item in self.deckcard_set.all():
            total += item.quantity
        return total

class DeckCard(models.Model):
    deck = models.ForeignKey(Deck, on_delete=models.CASCADE)
    card = models.ForeignKey(Card, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")

    class Meta:
        # Гарантирует, что одна и та же карта не дублируется в списке (только увеличивается кол-во)
        unique_together = ('deck', 'card')
        verbose_name = "Карта в колоде"
        verbose_name_plural = "Карты в колодах"

    def __str__(self):
        return f"{self.quantity}x {self.card.name} ({self.deck.name})"