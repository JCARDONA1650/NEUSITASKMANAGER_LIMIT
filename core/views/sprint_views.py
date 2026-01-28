from __future__ import annotations

from django.contrib import messages  # type: ignore
from django.contrib.auth.decorators import login_required  # type: ignore
from django.http import HttpRequest, HttpResponse  # type: ignore
from django.shortcuts import get_object_or_404, redirect, render  # type: ignore

from core.forms import SprintForm
from core.models import Sprint
from core.views.permissions import group_required


@login_required
@group_required("admin", "leader", "scrum")
def sprint_list(request: HttpRequest) -> HttpResponse:
    sprints = Sprint.objects.select_related("project").order_by("-id")
    return render(request, "core/sprint_list.html", {"sprints": sprints})


@login_required
@group_required("admin", "leader", "scrum")
def sprint_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = SprintForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, "Sprint creado correctamente.")
            return redirect("sprint_list")
    else:
        form = SprintForm()
    return render(request, "core/sprint_form.html", {"form": form})


@login_required
@group_required("admin", "leader", "scrum")
def sprint_update(request: HttpRequest, pk: int) -> HttpResponse:
    sprint = get_object_or_404(Sprint, pk=pk)
    if request.method == "POST":
        form = SprintForm(request.POST, instance=sprint)
        if form.is_valid():
            form.save()
            messages.success(request, "Sprint actualizado.")
            return redirect("sprint_list")
    else:
        form = SprintForm(instance=sprint)
    return render(request, "core/sprint_form.html", {"form": form, "edit": True, "sprint": sprint})


@login_required
@group_required("admin", "leader", "scrum")
def sprint_delete(request: HttpRequest, pk: int) -> HttpResponse:
    sprint = get_object_or_404(Sprint, pk=pk)
    if request.method == "POST":
        sprint.delete()
        messages.success(request, "Sprint eliminado.")
        return redirect("sprint_list")
    return render(request, "core/confirm_delete.html", {"object": sprint, "type": "Sprint"})
