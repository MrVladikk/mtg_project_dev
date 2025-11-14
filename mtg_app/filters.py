import django_filters
from django import forms
from django.db import models
from .models import Card, Set

class CardFilter(django_filters.FilterSet):
    
    # 1. Поиск по названию (Select2)
    name_search = django_filters.ModelChoiceFilter(
        queryset=Card.objects.all().order_by('name'),
        label='Название карты (быстрый поиск)',
        # --- ИСПРАВЛЕНИЕ 1: Добавляем 'method' ---
        method='filter_by_selected_card', 
        # --- ИСПРАВЛЕНИЕ 2: Добавляем 'attrs' для CSS ---
        widget=forms.Select(attrs={
            'class': 'form-select card-search-select2',
            'data-placeholder': 'Выберите карту...' # Для Select2
        })
    )
    
    # 2. Поиск по тексту карты
    oracle_text = django_filters.CharFilter(
        field_name='oracle_text',
        lookup_expr='icontains', 
        label='Текст карты (напр. "Deathtouch")',
        # --- ИСПРАВЛЕНИЕ 2: Добавляем 'attrs' ---
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    # 3. Фильтр по цветам (Чекбоксы)
    colors = django_filters.MultipleChoiceFilter(
        label='Цвет',
        choices=(
            ('W', 'White'), ('U', 'Blue'), ('B', 'Black'),
            ('R', 'Red'), ('G', 'Green'), ('C', 'Colorless'),
        ),
        # Виджет для чекбоксов уже стилизован в HTML
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        method='filter_by_colors'
    )

    # 4. Фильтр по CMC
    cmc = django_filters.NumberFilter(
        field_name='cmc', 
        lookup_expr='exact', 
        label='Мана-стоимость (CMC)',
        # --- ИСПРАВЛЕНИЕ 2: Добавляем 'attrs' ---
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Card
        fields = ['name_search', 'oracle_text', 'set', 'rarity', 'cmc', 'colors']

        # --- ИСПРАВЛЕНИЕ 2: Добавляем 'attrs' для 'set' и 'rarity' ---
        filter_overrides = {
            models.ForeignKey: {
                'filter_class': django_filters.ModelChoiceFilter,
                'extra': lambda f: {
                    'queryset': f.related_model.objects.all().order_by('name'),
                    'widget': forms.Select(attrs={'class': 'form-select'}),
                },
            },
            models.CharField: {
                'filter_class': django_filters.ChoiceFilter,
                'extra': lambda f: {
                    'widget': forms.Select(attrs={'class': 'form-select'}),
                },
            },
        }

    # --- ИСПРАВЛЕНИЕ 1: Наша "умная" функция фильтрации ---
    def filter_by_selected_card(self, queryset, name, value):
        # 'value' - это объект Card, который выбрал пользователь.
        # Мы просто фильтруем по его ID (pk).
        if value:
            return queryset.filter(pk=value.pk)
        return queryset

    def filter_by_colors(self, queryset, name, value):
        if 'C' in value:
             queryset = queryset.filter(colors__exact='')
             return queryset
        
        q_objects = models.Q()
        for color in value:
            q_objects |= models.Q(colors__icontains=color)
        
        return queryset.filter(q_objects)