import csv
import os
import tempfile
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase  # ✅ USE DJANGO'S TESTCASE FOR DB INTERACTIONS

from mtg_app.models import Card, Set

# Assuming csv_command is correctly imported as in your original file:
# import data_processing.management.commands.process_uploaded_csv as csv_command
# For the purpose of this self-contained example, let's mock it if it's not available.
# If data_processing.management.commands.process_uploaded_csv is the actual module,
# ensure the import path is correct for your project structure.
try:
    import data_processing.utils.process_uploaded_csv as csv_command
except ImportError:
    # Mocking csv_command if the actual import fails (e.g., in a standalone environment)
    # In your project, this import should work.
    csv_command = MagicMock()
    csv_command.requests = MagicMock()


CSV_HEADERS = [
    "Name",
    "Set code",
    "Set name",
    "Collector number",
    "Foil",
    "Rarity",
    "Quantity",
    "Scryfall ID",
    "Purchase price",
    "Condition",
    "Language",
    "Image URL",
]


class ProcessCSVCommandTests(TestCase):  # ✅ Inherit from Django's TestCase
    def setUp(self):
        # Create a temporary file object and store its path
        # delete=False means the file isn't deleted automatically on close,
        # allowing the command to read it after we close it, and we manually delete in tearDown.
        self.temp_csv_file = tempfile.NamedTemporaryFile(
            delete=False, mode="w", newline="", encoding="utf-8-sig"
        )
        self.temp_csv_path = self.temp_csv_file.name
        # The file object (self.temp_csv_file) will be used for writing.
        # It will be closed in each test method before calling the command.

    def tearDown(self):
        # Убеждаемся, что файловый объект, созданный в setUp, закрыт
        if hasattr(self, "temp_csv_file") and self.temp_csv_file and not self.temp_csv_file.closed:
            try:
                self.temp_csv_file.close()
            except Exception:
                # Игнорируем ошибки при закрытии, если файл уже проблематичен
                pass

        # Пытаемся удалить временный файл по его пути
        try:
            if (
                hasattr(self, "temp_csv_path")
                and self.temp_csv_path
                and os.path.exists(self.temp_csv_path)
            ):  # Проверяем существование пути и файла
                os.remove(self.temp_csv_path)
        except FileNotFoundError:
            # Файл уже удален или путь не был установлен.
            pass
        except AttributeError:
            # self.temp_csv_path не был установлен (например, если setUp завершился с ошибкой).
            pass
        except PermissionError:
            # Обрабатываем случаи, когда файл может быть заблокирован (WinError 32).
            # Это делает очистку в тесте более надежной, хотя основная причина блокировки
            # может быть в самой команде, если она не освобождает файл.
            print(
                f"Предупреждение: Не удалось удалить временный файл {self.temp_csv_path} в tearDown из-за PermissionError."
            )
            pass

    @patch.object(csv_command.requests, "get")
    def test_card_created_successfully(self, mock_get):
        """Проверка: корректная запись карты"""
        with open(self.temp_csv_path, "w", newline="", encoding="utf-8-sig") as temp_f:
            writer = csv.DictWriter(temp_f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            writer.writerow(
                {
                    "Name": "Black Lotus",
                    "Set code": "LEA",
                    "Set name": "Limited Edition Alpha",
                    "Collector number": "233",
                    "Foil": "",
                    "Rarity": "rare",
                    "Quantity": "1",
                    "Scryfall ID": "abc123",  # Ensure this is unique for the test
                    "Purchase price": "1000000",
                    "Condition": "mint",
                    "Language": "en",
                    "Image URL": "http://example.com/image.jpg",
                }
            )
        # The 'with' statement ensures the file is flushed and closed.

        mock_get.return_value = MagicMock(
            status_code=200,
            iter_content=lambda chunk_size: [b"fakeimage"],  # Corrected iter_content
            headers={"content-type": "image/jpeg"},
        )

        call_command("process_uploaded_csv", self.temp_csv_path)
        self.assertTrue(Card.objects.filter(scryfall_id="abc123").exists())
        self.assertTrue(Set.objects.filter(code="LEA").exists())

    def test_error_if_file_not_found(self):
        """Проверка: ошибка если файл не найден"""
        with self.assertRaises(CommandError):
            call_command("process_uploaded_csv", "nonexistent.csv")

    @patch.object(csv_command.requests, "get")
    def test_skips_row_if_no_scryfall_id(self, mock_get):
        """Проверка: пропускает строку если нет Scryfall ID"""
        with open(self.temp_csv_path, "w", newline="", encoding="utf-8-sig") as temp_f:
            writer = csv.DictWriter(temp_f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            writer.writerow(
                {
                    "Name": "Card Without ID",
                    "Set code": "XYZ",
                    "Set name": "Test Set",
                    "Collector number": "001",
                    "Foil": "",
                    "Rarity": "common",
                    "Quantity": "1",
                    "Scryfall ID": "",  # Empty Scryfall ID
                    "Purchase price": "",
                    "Condition": "",
                    "Language": "",
                    "Image URL": "",
                }
            )
        # The 'with' statement ensures the file is flushed and closed.

        # This mock_get might not be strictly necessary if no image download is attempted
        # when Scryfall ID is missing, but it's good practice to mock external calls.
        mock_get.return_value = MagicMock(status_code=404)  # Or whatever is appropriate

        call_command("process_uploaded_csv", self.temp_csv_path)
        # This assertion now correctly tests if cards are created (it expects 0)
        # If this still fails with "X != 0", it indicates a bug in your command's logic.
        self.assertEqual(Card.objects.count(), 0)

    @patch.object(csv_command.requests, "get")
    def test_image_download_from_scryfall(self, mock_get):
        """Проверяет fallback к Scryfall, если Image URL отсутствует"""
        with open(self.temp_csv_path, "w", newline="", encoding="utf-8-sig") as temp_f:
            writer = csv.DictWriter(temp_f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            writer.writerow(
                {
                    "Name": "Fallback Card",
                    "Set code": "SET1",
                    "Set name": "Fallback Set",
                    "Collector number": "007",
                    "Foil": "",
                    "Rarity": "rare",
                    "Quantity": "1",
                    "Scryfall ID": "scry007",  # Ensure this is unique for the test
                    "Purchase price": "0",
                    "Condition": "good",
                    "Language": "en",
                    "Image URL": "",  # Empty Image URL to trigger fallback
                }
            )
        # The 'with' statement ensures the file is flushed and closed.

        mock_get.side_effect = [
            MagicMock(  # Mock for Scryfall API call to get image URI
                status_code=200,
                json=lambda: {"image_uris": {"png": "http://example.com/fallback.png"}},
                raise_for_status=lambda: None,  # Mock this method if your code calls it
            ),
            MagicMock(  # Mock for actual image download
                status_code=200,
                iter_content=lambda chunk_size: [b"data"],  # Corrected iter_content
                headers={"content-type": "image/png"},
            ),
        ]

        call_command("process_uploaded_csv", self.temp_csv_path)
        card = Card.objects.get(scryfall_id="scry007")
        self.assertIn("Fallback Card", card.name)
        # Add more assertions here, e.g., to check if the image was "downloaded" (mocked)
        # and associated with the card object if your model stores image paths/data.
