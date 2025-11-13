
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden
from django.http import JsonResponse
from django.conf import settings

from mtg_app.models import Card, Deck, Set

from .forms import CardForm, DeckForm
from .forms import DeckForm, DeckCardFormSet, CardForm


def home(request):
    latest_cards = Card.objects.all().order_by("-id")[:10]
    popular_sets = Set.objects.all()[:5]
    return render(
        request,
        "mtg_app/home.html",
        {"latest_cards": latest_cards, "popular_sets": popular_sets},
    )


def card_list(request):
    query = request.GET.get("q")
    sort = request.GET.get("sort")

    if query:
        cards = Card.objects.filter(
            Q(name__icontains=query) | Q(set__name__icontains=query) | Q(rarity__icontains=query)
        )
        total_cards = cards.aggregate(total=Sum("quantity"))["total"] or 0
    else:
        cards = Card.objects.all()
        total_cards = Card.objects.aggregate(total=Sum("quantity"))["total"] or 0

    if sort == "alphabetical":
        cards = cards.order_by("name")
    elif sort == "price":
        cards = cards.order_by("purchase_price")
    elif sort == "price_desc":
        cards = cards.order_by("-purchase_price")
    else:
        cards = cards.order_by("-id")

    return render(
        request,
        "mtg_app/card_list.html",
        {"cards": cards, "query": query, "total_cards": total_cards, "sort": sort},
    )


def card_detail(request, pk):
    card = get_object_or_404(Card, id=pk)
    return render(request, "mtg_app/card_detail.html", {"card": card})


def set_list(request):
    sort = request.GET.get("sort", "")
    sets = Set.objects.annotate(total_cards=Count("cards"))

    if sort == "alphabetical":
        sets = sets.order_by("name")
    else:
        sets = sets.order_by("-id")

    return render(request, "mtg_app/set_list.html", {"sets": sets, "sort": sort})


def set_detail(request, pk):
    set_obj = get_object_or_404(Set, id=pk)
    cards = set_obj.cards.all()
    sort = request.GET.get("sort")

    if sort == "alphabetical":
        cards = cards.order_by("name")
    elif sort == "price":
        cards = cards.order_by("purchase_price")
    elif sort == "price_desc":
        cards = cards.order_by("-purchase_price")
    else:
        cards = cards.order_by("-id")

    total_cards = cards.aggregate(total=Sum("quantity"))["total"] or 0

    return render(
        request,
        "mtg_app/set_detail.html",
        {"set": set_obj, "cards": cards, "sort": sort, "total_cards": total_cards},
    )


def deck_list(request):
    if request.user.is_authenticated:
        decks = Deck.objects.filter(Q(is_private=False) | Q(owner=request.user))
    else:
        decks = Deck.objects.filter(is_private=False)

    sort = request.GET.get("sort")
    if sort == "alphabetical":
        decks = decks.order_by("name")
    else:
        decks = decks.order_by("-created_at")

    return render(request, "mtg_app/deck_list.html", {"decks": decks, "sort": sort})


def deck_detail(request, pk):
    deck = get_object_or_404(Deck, id=pk)

    if deck.is_private and deck.owner != request.user:
        raise Http404("Колода не найдена")

    cards = deck.cards.all()
    sort = request.GET.get("sort")

    if sort == "alphabetical":
        cards = cards.order_by("name")
    elif sort == "purchase_price":
        cards = cards.order_by("purchase_price")
    elif sort == "purchase_price_desc":
        cards = cards.order_by("-purchase_price")
    else:
        cards = cards.order_by("-id")

    return render(request, "mtg_app/deck_detail.html", {"deck": deck, "cards": cards, "sort": sort})


def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Аккаунт создан! Теперь можете войти.")
            # Используем стандартный auth url 'login' (без namespace mtg_app)
            return redirect("login")
    else:
        form = UserCreationForm()
    return render(request, "mtg_app/register.html", {"form": form})


@login_required
def add_card(request):
    if request.method == "POST":
        form = CardForm(request.POST, request.FILES)
        if form.is_valid():
            card = form.save(commit=False)
            card.owner = request.user
            card.save()
            return redirect("mtg_app:cards_list")
    else:
        form = CardForm()
    return render(request, "mtg_app/add_card.html", {"form": form})


@login_required
def add_deck(request):
    if request.method == "POST":
        form = DeckForm(request.POST)
        # prefix='deck_cards' обязателен, так как он прописан в JS
        formset = DeckCardFormSet(request.POST, prefix='deck_cards')
        
        if form.is_valid() and formset.is_valid():
            # 1. Сохраняем саму колоду
            deck = form.save(commit=False)
            deck.owner = request.user
            deck.save()
            
            # 2. Сохраняем карты (ЯВНЫЙ МЕТОД)
            # Получаем объекты, но пока не пишем в базу
            cards = formset.save(commit=False)
            
            # Проходим по каждому и вручную привязываем к колоде
            for deck_card in cards:
                deck_card.deck = deck
                deck_card.save()
            
            # 3. Удаляем те, что были помечены на удаление (актуально для редактирования)
            for obj in formset.deleted_objects:
                obj.delete()
                
            messages.success(request, f"Колода \"{deck.name}\" сохранена! ({len(cards)} карт)")
            return redirect('mtg_app:deck_detail', pk=deck.pk)
        else:
            # Вывод ошибок в консоль, чтобы мы знали правду
            print("--- ОШИБКИ ВАЛИДАЦИИ ---")
            print("Form:", form.errors)
            print("Formset:", formset.errors)
            print("Formset Non-form:", formset.non_form_errors())
            messages.error(request, "Ошибка сохранения. Проверьте данные.")
    else:
        form = DeckForm()
        formset = DeckCardFormSet(prefix='deck_cards')
        
    return render(request, 'mtg_app/add_deck.html', {
        'form': form,
        'formset': formset
    })


def custom_logout(request):
    logout(request)
    return redirect("mtg_app:home")


@login_required
@require_POST
def delete_deck(request, pk):
    deck = get_object_or_404(Deck, id=pk)
    if deck.owner != request.user:
        raise Http404("У вас нет прав на удаление этой колоды")
    deck.delete()
    return redirect("mtg_app:deck_list")


@login_required
def deck_edit(request, pk):
    deck = get_object_or_404(Deck, pk=pk)
    
    if deck.owner != request.user:
        return HttpResponseForbidden("Вы не владелец этой колоды.")
    
    if request.method == "POST":
        form = DeckForm(request.POST, instance=deck)
        formset = DeckCardFormSet(request.POST, instance=deck, prefix='deck_cards')
        
        if form.is_valid() and formset.is_valid():
            form.save()
            
            # Тот же надежный метод сохранения
            cards = formset.save(commit=False)
            for deck_card in cards:
                deck_card.deck = deck
                deck_card.save()
                
            for obj in formset.deleted_objects:
                obj.delete()
                
            messages.success(request, "Колода обновлена!")
            return redirect('mtg_app:deck_detail', pk=deck.pk)
        else:
            print("Errors:", formset.errors)
    else:
        form = DeckForm(instance=deck)
        formset = DeckCardFormSet(instance=deck, prefix='deck_cards')
    
    return render(request, 'mtg_app/add_deck.html', {
        'form': form, 
        'deck': deck,
        'formset': formset
    })

@login_required
def deck_delete(request, pk):
    deck = get_object_or_404(Deck, pk=pk)
    
    if deck.owner != request.user:
        return HttpResponseForbidden("Вы не можете удалить чужую колоду.")
    
    if request.method == "POST":
        deck.delete()
        messages.success(request, f"Колода \"{deck.name}\" удалена.")
        return redirect('mtg_app:deck_list')
        
    return render(request, 'mtg_app/deck_confirm_delete.html', {'deck': deck})

def get_card_image(request):
    """API для получения URL картинки по ID карты (для AJAX)"""
    card_id = request.GET.get('id')
    if card_id:
        try:
            card = Card.objects.get(pk=card_id)
            
            # 1. Проверяем, есть ли физическое поле 'image' и есть ли в нем файл
            if hasattr(card, 'image') and card.image:
                return JsonResponse({'url': card.image.url})
            
            # 2. Если нет, проверяем поле ссылки 'image_url' (от CSV импорта)
            elif hasattr(card, 'image_url') and card.image_url:
                if card.image_url.startswith('http') or card.image_url.startswith('/'):
                    return JsonResponse({'url': card.image_url})
                else:
                    return JsonResponse({'url': f"{settings.MEDIA_URL}{card.image_url}"})
                    
        except Card.DoesNotExist:
            pass
            
    return JsonResponse({'url': None})