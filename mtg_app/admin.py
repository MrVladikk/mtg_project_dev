from django.contrib import admin

from .models import Card, Deck, Set

# Register your models here.


@admin.register(Set)
class SetAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")

    def card_count(self, obj):
        return obj.cards.count()

    card_count.short_description = "Количество карт"


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ("name", "set", "collector_number", "foil", "rarity", "quantity", "scryfall_id")
    search_fields = ("name", "set__name", "scryfall_id")
    list_filter = ("set", "foil", "rarity", "language", "condition")


class DeckCardInline(admin.TabularInline):
    model = Deck.cards.through  # ManyToMany связь через промежуточную таблицу
    extra = 1  # Количество пустых строк для добавления карт


@admin.register(Deck)
class DeckAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)
    inlines = [DeckCardInline]  # Встраиваем редактирование карт в колоде
