from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.forms import inlineformset_factory # Важный импорт
from .models import Card, Deck, DeckCard # Важный импорт

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text="Введите действующий email.")
    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

class CardForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = '__all__'

# --- ЭТО ФОРМА ДЛЯ САМОЙ КОЛОДЫ ---
class DeckForm(forms.ModelForm):
    class Meta:
        model = Deck
        # В этой форме НЕ ДОЛЖНО быть поля 'cards'
        fields = ['name', 'description', 'is_private']
        labels = {
            'name': 'Название колоды',
            'description': 'Описание',
            'is_private': 'Приватная (видна только вам)',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'is_private': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# --- ЭТО ФОРМСЕТ ДЛЯ СПИСКА КАРТ В КОЛОДЕ ---
# (Он был сломан из-за мусора в файле)
DeckCardFormSet = inlineformset_factory(
    parent_model=Deck,    # Главная модель
    model=DeckCard,       # Модель связи
    fields=['card', 'quantity'], # Поля, которые мы редактируем
    extra=0,              # Не показывать пустые строки по умолчанию
    can_delete=True,
    widgets={
        # Задаем стиль по умолчанию для поля количества
        'quantity': forms.NumberInput(attrs={'value': 1, 'min': 1}),
    }
)