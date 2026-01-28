from __future__ import annotations

from django.contrib import messages  # type: ignore
from django.contrib.auth.decorators import login_required  # type: ignore
from django.core.exceptions import ValidationError  # type: ignore
from django.http import HttpRequest, HttpResponse  # type: ignore
from django.shortcuts import get_object_or_404, redirect, render  # type: ignore

from core.forms import ProjectForm
from core.models import Project, check_projects_limit_or_raise
from core.views.permissions import group_required


@login_required
@group_required("admin", "leader", "scrum")
def project_list(request: HttpRequest) -> HttpResponse:
    projects = Project.objects.all().order_by("-id")
    return render(request, "core/project_list.html", {"projects": projects})


@login_required
@group_required("admin", "leader", "scrum")
def project_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            try:
                # 🔒 LÍMITE FREE
                check_projects_limit_or_raise(Project)

                obj = form.save(commit=False)
                obj.created_by = request.user
                obj.save()
                form.save_m2m()

                messages.success(request, "Proyecto creado correctamente.")
                return redirect("project_list")

            except ValidationError as e:
                msg = e.message if hasattr(e, "message") else str(e)
                messages.error(request, msg)
        # si no es válido, cae y renderiza con errores
    else:
        form = ProjectForm()

    return render(request, "core/project_form.html", {"form": form})


@login_required
@group_required("admin", "leader", "scrum")
def project_update(request: HttpRequest, pk: int) -> HttpResponse:
    project = get_object_or_404(Project, pk=pk)

    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "Proyecto actualizado.")
            return redirect("project_list")
    else:
        form = ProjectForm(instance=project)

    return render(
        request,
        "core/project_form.html",
        {"form": form, "edit": True, "project": project},
    )


@login_required
@group_required("admin", "leader", "scrum")
def project_delete(request: HttpRequest, pk: int) -> HttpResponse:
    project = get_object_or_404(Project, pk=pk)

    if request.method == "POST":
        project.delete()
        messages.success(request, "Proyecto eliminado.")
        return redirect("project_list")

    return render(request, "core/confirm_delete.html", {"object": project, "type": "Proyecto"})
