from __future__ import annotations

from django.contrib import messages  # type: ignore
from django.contrib.auth.decorators import login_required  # type: ignore
from django.http import HttpRequest, HttpResponse  # type: ignore
from django.shortcuts import get_object_or_404, redirect, render  # type: ignore

from core.forms import EpicForm
from core.models import Epic
from core.views.permissions import group_required


@login_required
@group_required("admin", "leader", "scrum")
def epic_list(request: HttpRequest) -> HttpResponse:
    epics = Epic.objects.select_related("project").order_by("-id")
    return render(request, "core/epic_list.html", {"epics": epics})


@login_required
@group_required("admin", "leader", "scrum")
def epic_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = EpicForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, "Épica creada correctamente.")
            return redirect("epic_list")
    else:
        form = EpicForm()
    return render(request, "core/epic_form.html", {"form": form})


@login_required
@group_required("admin", "leader", "scrum")
def epic_update(request: HttpRequest, pk: int) -> HttpResponse:
    epic = get_object_or_404(Epic, pk=pk)
    if request.method == "POST":
        form = EpicForm(request.POST, instance=epic)
        if form.is_valid():
            form.save()
            messages.success(request, "Épica actualizada.")
            return redirect("epic_list")
    else:
        form = EpicForm(instance=epic)
    return render(request, "core/epic_form.html", {"form": form, "edit": True, "epic": epic})


@login_required
@group_required("admin", "leader", "scrum")
def epic_delete(request: HttpRequest, pk: int) -> HttpResponse:
    epic = get_object_or_404(Epic, pk=pk)
    if request.method == "POST":
        epic.delete()
        messages.success(request, "Épica eliminada.")
        return redirect("epic_list")
    return render(request, "core/confirm_delete.html", {"object": epic, "type": "Épica"})
