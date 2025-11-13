
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from mtg_app.models import Card, Deck, Set

from .forms import CardForm, DeckForm


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
        if form.is_valid():
            deck = form.save(commit=False)
            deck.owner = request.user
            deck.save()
            form.save_m2m()
            return redirect("mtg_app:deck_list")
    else:
        form = DeckForm()
    return render(request, "mtg_app/add_deck.html", {"form": form})


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
