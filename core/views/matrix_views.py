from __future__ import annotations

from io import BytesIO

from django.contrib.auth.decorators import login_required  # type: ignore
from django.http import HttpRequest, HttpResponse  # type: ignore
from django.shortcuts import render  # type: ignore

from reportlab.pdfgen import canvas  # type: ignore

from core.models import Project, Sprint, Task
from core.views.permissions import is_admin
from django.contrib.auth import get_user_model  # type: ignore

User = get_user_model()


@login_required
def matrix_priority(request: HttpRequest) -> HttpResponse:
    tasks = Task.objects.all()

    if not is_admin(request.user):
        tasks = tasks.filter(responsibles=request.user)

    project_id = request.GET.get("project")
    sprint_id = request.GET.get("sprint")
    responsible_id = request.GET.get("responsible")

    if project_id:
        tasks = tasks.filter(project__id=project_id)
    if sprint_id:
        tasks = tasks.filter(sprint__id=sprint_id)
    if responsible_id:
        tasks = tasks.filter(responsibles__id=responsible_id)

    matrix = {
        "do": tasks.filter(priority=Task.Priority.DO),
        "plan": tasks.filter(priority=Task.Priority.PLAN),
        "delegate": tasks.filter(priority=Task.Priority.DELEGATE),
        "eliminate": tasks.filter(priority=Task.Priority.ELIMINATE),
    }

    projects = Project.objects.all().order_by("name")
    sprints = Sprint.objects.all().order_by("-id")
    responsibles = User.objects.all().order_by("username") if is_admin(request.user) else User.objects.filter(id=request.user.id)

    return render(
        request,
        "core/matrix_priority.html",
        {
            "matrix": matrix,
            "projects": projects,
            "sprints": sprints,
            "responsibles": responsibles,
            "selected_project": project_id,
            "selected_sprint": sprint_id,
            "selected_responsible": responsible_id,
        },
    )


@login_required
def matrix_status(request: HttpRequest) -> HttpResponse:
    tasks = Task.objects.all()
    if not is_admin(request.user):
        tasks = tasks.filter(responsibles=request.user)

    matrix = {
        "new": tasks.filter(status=Task.Status.NEW),
        "in_progress": tasks.filter(status=Task.Status.IN_PROGRESS),
        "completed": tasks.filter(status=Task.Status.COMPLETED),
    }
    return render(request, "core/matrix_status.html", {"matrix": matrix})


@login_required
def export_matrix_pdf(request: HttpRequest) -> HttpResponse:
    tasks = Task.objects.all()
    if not is_admin(request.user):
        tasks = tasks.filter(responsibles=request.user)

    matrix = {
        "1) Urgente e Importante ": tasks.filter(priority=Task.Priority.DO),
        "2) Importante no Urgente ": tasks.filter(priority=Task.Priority.PLAN),
        "3) Urgente no Importante ": tasks.filter(priority=Task.Priority.DELEGATE),
        "4) Ni Urgente ni Importante ": tasks.filter(priority=Task.Priority.ELIMINATE),
    }

    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    y = 800

    p.setFont("Helvetica-Bold", 16)
    p.drawString(180, y, "Matriz Eisenhower")
    y -= 40

    for cat, qs in matrix.items():
        p.setFont("Helvetica-Bold", 12)
        p.drawString(40, y, cat)
        y -= 18

        p.setFont("Helvetica", 10)
        if qs.count() == 0:
            p.drawString(60, y, "Sin tareas")
            y -= 14

        for t in qs:
            p.drawString(60, y, f"- {t.title} ({t.get_status_display()}) SP:{t.story_points}")
            y -= 14
            if y < 60:
                p.showPage()
                y = 800

        y -= 10
        if y < 60:
            p.showPage()
            y = 800

    p.showPage()
    p.save()
    buffer.seek(0)

    # django FileResponse si lo usas, si no: HttpResponse
    from django.http import FileResponse  # type: ignore
    return FileResponse(buffer, as_attachment=True, filename="matriz_eisenhower.pdf")
