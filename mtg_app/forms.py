from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from .models import Card, Deck, DeckCard


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text="Введите действующий email.")

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class CardForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = '__all__' # Или перечислите поля

class DeckForm(forms.ModelForm):
    class Meta:
        model = Deck
        fields = ['name', 'description', 'is_private'] # Проверьте, какие поля есть у вас в модели Deck
        labels = {
            'name': 'Название колоды',
            'description': 'Описание',
            'is_private': 'Приватная колода',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

# --- ВОТ ЭТОГО КОДА НЕ ХВАТАЛО ---
DeckCardFormSet = inlineformset_factory(
    parent_model=Deck,
    model=DeckCard,
    fields=['card', 'quantity'],
    extra=0, # Не создавать пустые строки автоматически (мы делаем это через JS)
    can_delete=True # Разрешить удаление
)

class Meta:
        model = Deck  # Добавьте это!
        fields = ["name", "description", "cards", "is_private", "owner"]

        # Если нужно настроить виджет для поля cards (например, выбор нескольких карт)
        cards = forms.ModelMultipleChoiceField(
            queryset=Card.objects.all(),
            widget=forms.CheckboxSelectMultiple,  # Виджет для выбора нескольких карт
            required=False,
        )
