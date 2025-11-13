from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PostForm, ThreadForm
from .models import Post, Thread


def thread_list(request):
    threads = Thread.objects.all().order_by("-created_at")
    return render(request, "forum/thread_list.html", {"threads": threads})


def thread_detail(request, pk):
    thread = get_object_or_404(Thread, pk=pk)
    posts = thread.posts.all().order_by("created_at")

    # Форма для быстрого ответа внизу темы
    if request.method == "POST" and request.user.is_authenticated:
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.thread = thread
            post.author = request.user
            post.save()
            return redirect("forum:thread_detail", pk=pk)
    else:
        form = PostForm()

    return render(
        request, "forum/thread_detail.html", {"thread": thread, "posts": posts, "form": form}
    )


@login_required
def thread_create(request):
    if request.method == "POST":
        form = ThreadForm(request.POST)
        if form.is_valid():
            # --- ИСПРАВЛЕНИЕ НАЧАЛО ---
            # 1. Создаем объект, но не сохраняем в БД (commit=False)
            thread = form.save(commit=False)
            # 2. Присваиваем текущего пользователя как автора
            thread.author = request.user
            # 3. Сохраняем окончательно
            thread.save()
            # --- ИСПРАВЛЕНИЕ КОНЕЦ ---
            return redirect("forum:thread_list")
    else:
        form = ThreadForm()
    return render(request, "forum/thread_create.html", {"form": form})


@login_required
def post_create(request, pk):
    thread = get_object_or_404(Thread, pk=pk)
    if request.method == "POST":
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.thread = thread
            post.author = request.user
            post.save()
            return redirect("forum:thread_detail", pk=pk)
    else:
        form = PostForm()
    return render(request, "forum/post_create.html", {"form": form, "thread": thread})


@login_required
def delete_thread(request, pk):
    thread = get_object_or_404(Thread, pk=pk)

    # Проверка прав: удалять может только автор или администратор
    if thread.author != request.user and not request.user.is_staff:
        return HttpResponseForbidden("Вы не можете удалить эту тему.")

    if request.method == "POST":
        thread.delete()
        return redirect("forum:thread_list")

    # Страница подтверждения удаления
    return render(request, "forum/thread_delete.html", {"thread": thread})


@login_required
def delete_post(request, pk):
    post = get_object_or_404(Post, pk=pk)
    thread_pk = post.thread.pk  # Сохраняем ID темы, чтобы вернуться в нее

    # Проверка прав: удалять может автор поста, автор темы или админ
    # (или только автор поста и админ, как решите)
    if post.author != request.user and not request.user.is_staff:
        return HttpResponseForbidden("Вы не можете удалить этот ответ.")

    if request.method == "POST":
        post.delete()
        return redirect("forum:thread_detail", pk=thread_pk)

    # Страница подтверждения удаления поста
    return render(request, "forum/post_delete.html", {"post": post})
