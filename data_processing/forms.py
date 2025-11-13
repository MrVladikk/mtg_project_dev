from django import forms


class CSVUploadForm(forms.Form):
    file = forms.FileField(
        label="CSV файл",
        help_text="Поддерживаются UTF-8 / Windows-1251. Разделители: ; , таб.",
    )
    update_existing = forms.BooleanField(
        required=False,
        initial=True,
        label="Обновлять существующие карты",
        help_text="Если включено — при совпадении имени и сета, запись будет обновлена.",
    )
