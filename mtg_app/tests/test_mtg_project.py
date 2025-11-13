from unittest import mock  # Для мокирования

import pandas as pd  # Убедитесь, что pandas установлен в окружении тестов
import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import NoReverseMatch, reverse

from mtg_app.models import Card, Deck, Set


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
def test_card_creation():
    """
    Тестирует создание объекта Card с правильной связью на Set.
    """
    test_set = Set.objects.create(code="LEA", name="Alpha")
    card = Card.objects.create(
        scryfall_id="scry-test-001",
        name="Black Lotus",
        set=test_set,
        collector_number="1",
        foil=False,
        rarity="Rare",
        quantity=1,
        purchase_price="0",
        language="English",
        condition="Near Mint",
        image_url="http://example.com/black_lotus.jpg",
    )
    assert Card.objects.count() == 1
    # Используем переменную card, чтобы избежать F841
    assert Card.objects.filter(pk=card.pk, name="Black Lotus").exists()


@pytest.mark.django_db
def test_deck_creation():
    """
    Тестирует создание объекта Deck.
    """
    deck = Deck.objects.create(name="Vintage Deck")
    assert Deck.objects.count() == 1
    assert Deck.objects.first().name == "Vintage Deck"
    # Используем переменную deck, чтобы избежать F841
    assert deck.name == "Vintage Deck"


@pytest.mark.django_db
def test_set_creation():
    """
    Тестирует создание объекта Set.
    """
    mtg_set = Set.objects.create(code="LEA", name="Alpha")
    assert Set.objects.count() == 1
    assert mtg_set.name == "Alpha"


@pytest.mark.django_db
def test_card_list_view(client):
    """
    Тестирует доступность представления списка карточек.
    """
    url_name_to_try = "card_list"
    try:
        url = reverse(f"mtg_app:{url_name_to_try}")
    except NoReverseMatch:
        try:
            url = reverse(url_name_to_try)
        except NoReverseMatch as e:
            pytest.fail(
                f"NoReverseMatch for '{url_name_to_try}' with and without 'mtg_app' namespace: {e}"
            )
            return

    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_deck_list_view(client):
    """
    Тестирует доступность представления списка колод.
    """
    url_name_to_try = "deck_list"
    try:
        url = reverse(f"mtg_app:{url_name_to_try}")
    except NoReverseMatch:
        try:
            url = reverse(url_name_to_try)
        except NoReverseMatch as e:
            pytest.fail(
                f"NoReverseMatch for '{url_name_to_try}' with and without 'mtg_app' namespace: {e}"
            )
            return

    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
@mock.patch("pandas.read_csv")  # Мокируем pandas.read_csv
def test_import_cards_command(mock_read_csv, tmp_path):
    """
    Тест команды импорта карточек из CSV.

    Команда 'import_cards' использует жестко заданный путь к файлу.
    Мы мокируем pd.read_csv, чтобы подменить данные для импорта.
    Команда вызывается без аргументов, так как она не принимает их.
    """
    # Данные для DataFrame, который вернет мок pd.read_csv
    csv_data = {
        "Set code": ["LEA"],
        "Set name": ["Limited Edition Alpha"],
        "Name": ["Test Card From Mock"],
        "Collector number": ["123"],
        "Foil": ["false"],  # или "foil" для True
        "Rarity": ["Common"],
        "Quantity": [1],
        "Purchase price": ["1.00"],
        "Language": ["English"],
        "Condition": ["Near Mint"],
        "Scryfall ID": ["some-unique-scryfall-id-for-mock"],  # уникальный ID
    }
    mock_df = pd.DataFrame(csv_data)
    mock_read_csv.return_value = mock_df

    # Запускаем команду — она должна прочитать CSV через pd.read_csv (замокировано)
    call_command("import_cards")

    # Проверяем, что карта была создана на основе мокированных данных
    assert Card.objects.filter(name="Test Card From Mock").exists()
    created_card = Card.objects.get(name="Test Card From Mock")
    assert created_card.set.code == "LEA"
    assert created_card.foil is False  # так как "false"

    # Убедимся, что mock_read_csv действительно вызывался
    mock_read_csv.assert_called_once()


@pytest.mark.django_db
@mock.patch("mtg_app.management.commands.update_image_urls.os.path.exists")  # мокируем exists
def test_update_images_command(mock_os_path_exists):
    """
    Тест команды обновления изображений карточек.
    Имя команды: 'update_image_urls'.
    Мокаем os.path.exists, чтобы команда думала, что файл изображения существует.
    """
    mock_os_path_exists.return_value = True

    test_set = Set.objects.create(code="LEA", name="Alpha")
    # Создаём карту с пустым URL — команда должна его обновить
    card = Card.objects.create(
        scryfall_id="scry-image-001",
        name="Test Image Card",
        set=test_set,
        collector_number="imgtst",
        foil=False,
        rarity="Rare",
        quantity=1,
        purchase_price="0",
        language="English",
        condition="Near Mint",
        image_url="",
    )

    call_command("update_image_urls")

    card.refresh_from_db()
    assert card.image_url != "", "Image URL should have been updated by the command"

    # Проверяем, что os.path.exists был вызван
    mock_os_path_exists.assert_called()


@pytest.mark.django_db
def test_add_deck_command(tmp_path):
    """
    Тестирует добавление колоды через команду.
    Команда должна принимать deck_file и deck_name как аргументы.
    """
    deck_file = tmp_path / "deck.txt"
    deck_file.write_text("1 Black Lotus\n")

    test_set, _ = Set.objects.get_or_create(code="LEA", defaults={"name": "Alpha"})
    Card.objects.get_or_create(
        name="Black Lotus",
        set=test_set,
        defaults={
            "scryfall_id": "unique-scryfall-id-for-black-lotus-in-deck-test",
            "collector_number": "1",
            "foil": False,
            "rarity": "Rare",
            "quantity": 1,
            "purchase_price": "0",
            "language": "English",
            "condition": "Near Mint",
            "image_url": "http://example.com/image.jpg",
        },
    )

    call_command("add_deck", "--deck_file", str(deck_file), "--deck_name", "Test Deck")

    assert Deck.objects.filter(name="Test Deck").exists()
