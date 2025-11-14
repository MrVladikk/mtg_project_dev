import tempfile
import os
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render
from django.http import JsonResponse
from celery.result import AsyncResult # <-- НОВЫЙ ИМПОРТ

from .forms import CSVUploadForm
from .services import process_uploaded_csv
from .tasks import update_all_card_prices

def _is_staff(user):
    return user.is_staff or user.is_superuser

@login_required
@user_passes_test(_is_staff)
def upload_csv(request):
    if request.method == "POST":
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try: file = form.cleaned_data["file"] 
            except KeyError:
                messages.error(request, "Ошибка: Поле 'file' не найдено.")
                return redirect("data_processing:upload_csv")

            temp_file_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
                    for chunk in file.chunks():
                        temp_file.write(chunk)
                    temp_file_path = temp_file.name

                # --- ИЗМЕНЕНИЕ: ЗАПУСКАЕМ ЗАДАЧУ И СОХРАНЯЕМ ID ---
                task = process_uploaded_csv.delay(temp_file_path)
                
                # Сохраняем ID задачи в сессию пользователя
                request.session['csv_import_task_id'] = task.id
                # -------------------------------------------------

                messages.info(request, f"Импорт файла \"{file.name}\" начался. Это может занять несколько минут.")

            except Exception as e:
                messages.error(request, f"Не удалось запустить импорт: {e}")
            
            return redirect("mtg_app:card_list") # Сразу перенаправляем
    else:
        form = CSVUploadForm()

    return render(request, "data_processing/upload_csv.html", {"form": form})


# --- НОВАЯ ФУНКЦИЯ ДЛЯ AJAX ---
@login_required
def get_task_status(request):
    task_id = request.session.get('csv_import_task_id')
    if not task_id:
        return JsonResponse({'state': 'NOT_FOUND'})

    # Получаем результат задачи из Result Backend (который теперь в БД Django)
    task = AsyncResult(task_id)
    
    response_data = {
        'state': task.state,
        'progress': task.info, # .info содержит словарь {'current': i, 'total': total_rows}
    }

    # Если задача завершена (успешно или с ошибкой), очищаем сессию
    if task.state == 'SUCCESS' or task.state == 'FAILURE':
        del request.session['csv_import_task_id']
        
        # Если успешно, передаем финальные счетчики
        if task.state == 'SUCCESS':
            response_data['results'] = task.result 

    return JsonResponse(response_data)

@login_required
@user_passes_test(_is_staff) # Только админ может это делать
def trigger_price_update(request):
    """
    Ручной запуск фоновой задачи по обновлению цен.
    """
    try:
        # Вызываем нашу задачу .delay() - это отправит ее в очередь Celery
        update_all_card_prices.delay()
        messages.success(request, "Фоновое обновление цен запущено! Прогресс будет виден в консоли Celery.")
    except Exception as e:
        messages.error(request, f"Не удалось запустить задачу: {e}")
    
    # Возвращаем пользователя обратно на страницу, откуда он пришел
    return redirect('data_processing:upload_csv')