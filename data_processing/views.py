import os
import tempfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render

from .forms import CSVUploadForm
from .services import process_uploaded_csv


def _is_staff(user):
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(_is_staff)
def upload_csv(request):
    if request.method == "POST":
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                file = form.cleaned_data["file"]
            except KeyError:
                messages.error(request, "Ошибка: Поле 'file' не найдено в форме.")
                return redirect("data_processing:upload_csv")

            temp_file_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
                    for chunk in file.chunks():
                        temp_file.write(chunk)
                    temp_file_path = temp_file.name

                # --- ОТЛАДКА: Пишем в консоль перед запуску ---
                print("\n=== [VIEW] Запуск обработки CSV... ===")

                # Вызываем сервис
                results, errors_list = process_uploaded_csv(temp_file_path)

                # --- ОТЛАДКА: Смотрим, что вернул сервис ---
                print("=== [VIEW] Обработка завершена. Результаты: ===")
                print(f"Errors count (в словаре): {results.get('errors')}")
                print(f"Errors list len (длина списка): {len(errors_list)}")
                if errors_list:
                    print(f"ПЕРВАЯ ОШИБКА: {errors_list[0]}")
                print("==========================================\n")

                results_str = (
                    f"Создано: {results.get('created', 0)}, "
                    f"Обновлено: {results.get('updated', 0)}, "
                    f"Ошибок: {results.get('errors', 0)}, "
                    f"Скачано: {results.get('downloaded', 0)}, "
                    f"Найдено локально: {results.get('skipped_img', 0)}."
                )

                # Логика сообщений для сайта
                if results.get("errors", 0) > 0:
                    messages.warning(request, f"Импорт завершён с ошибками. {results_str}")
                else:
                    messages.success(request, f"Импорт успешно завершён. {results_str}")

                # Вывод ошибок на сайт
                if errors_list:
                    messages.error(
                        request, f"Обнаружено {len(errors_list)} ошибок (показаны первые 5):"
                    )
                    for error_msg in errors_list[:5]:
                        messages.error(request, error_msg)

            except ValueError as ve:
                messages.error(request, f"Ошибка в файле: {ve}")
                print(f"[VIEW ERROR] ValueError: {ve}")
            except Exception as e:
                messages.error(request, f"Произошла непредвиденная ошибка: {e}")
                print(f"[VIEW ERROR] Exception: {e}")
            finally:
                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

            return redirect("mtg_app:card_list")
    else:
        form = CSVUploadForm()

    return render(request, "data_processing/upload_csv.html", {"form": form})
