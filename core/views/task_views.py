from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import json

from django.contrib import messages  # type: ignore
from django.contrib.auth import get_user_model  # type: ignore
from django.contrib.auth.decorators import login_required  # type: ignore
from django.core.exceptions import PermissionDenied, ValidationError  # type: ignore
from django.db.models import Q  # type: ignore
from django.http import HttpRequest, HttpResponse, JsonResponse  # type: ignore
from django.shortcuts import get_object_or_404, redirect, render  # type: ignore

from core.forms import SubTaskForm, TaskForm
from core.models import Project, Sprint, SubTask, Task, TaskStatusLog, PlanLimits, check_tasks_limit_or_raise
from core.views.permissions import group_required, is_admin

User = get_user_model()


# -----------------------------
# Helpers
# -----------------------------

@dataclass
class ProjectGroup:
    project: Project
    total: int

    tasks_new: list[Task]
    tasks_in_progress: list[Task]
    tasks_completed: list[Task]

    count_new: int
    count_in_progress: int
    count_completed: int


def _group_tasks_by_project_and_status(tasks: Iterable[Task]) -> list[ProjectGroup]:
    by_project: dict[int, dict[str, list[Task]]] = {}
    project_obj: dict[int, Project] = {}

    for t in tasks:
        pid = t.project_id
        project_obj[pid] = t.project

        if pid not in by_project:
            by_project[pid] = {"new": [], "in_progress": [], "completed": []}

        if t.status == Task.Status.NEW:
            by_project[pid]["new"].append(t)
        elif t.status == Task.Status.IN_PROGRESS:
            by_project[pid]["in_progress"].append(t)
        elif t.status == Task.Status.COMPLETED:
            by_project[pid]["completed"].append(t)
        else:
            by_project[pid]["new"].append(t)

    grouped: list[ProjectGroup] = []
    for pid in sorted(by_project.keys(), key=lambda x: (project_obj[x].name or "").lower()):
        bucket = by_project[pid]
        total = len(bucket["new"]) + len(bucket["in_progress"]) + len(bucket["completed"])
        grouped.append(
            ProjectGroup(
                project=project_obj[pid],
                total=total,
                tasks_new=bucket["new"],
                tasks_in_progress=bucket["in_progress"],
                tasks_completed=bucket["completed"],
                count_new=len(bucket["new"]),
                count_in_progress=len(bucket["in_progress"]),
                count_completed=len(bucket["completed"]),
            )
        )
    return grouped


def _files_count() -> int:
    return SubTask.objects.exclude(Q(attachment="") | Q(attachment__isnull=True)).count()


def _check_files_limit_or_raise():
    limits = PlanLimits.get_solo()
    total_files = _files_count()
    if total_files >= limits.max_files:
        raise ValidationError(
            "Su sesión free no alcanza para seguir cargando archivos. "
            "Contacte con su proveedor de software para cambiar el plan."
        )


# -----------------------------
# Views
# -----------------------------

@login_required
def task_list(request: HttpRequest) -> HttpResponse:
    user = request.user

    tasks = (
        Task.objects
        .select_related("project", "sprint", "epic")
        .prefetch_related("responsibles")
        .all()
    )

    if not is_admin(user):
        tasks = tasks.filter(responsibles=user)

    project_id = request.GET.get("project") or ""
    sprint_id = request.GET.get("sprint") or ""
    responsible_id = request.GET.get("responsible") or ""
    status = request.GET.get("status") or ""
    q = (request.GET.get("q") or "").strip()

    if project_id:
        tasks = tasks.filter(project__id=project_id)
    if sprint_id:
        tasks = tasks.filter(sprint__id=sprint_id)
    if responsible_id:
        tasks = tasks.filter(responsibles__id=responsible_id)
    if status in dict(Task.Status.choices):
        tasks = tasks.filter(status=status)
    if q:
        tasks = tasks.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(project__name__icontains=q)
            | Q(sprint__name__icontains=q)
            | Q(epic__name__icontains=q)
        )

    tasks = tasks.order_by("status", "priority", "-id")

    projects = Project.objects.all().order_by("name")
    sprints = Sprint.objects.all().order_by("-id")
    responsibles = User.objects.all().order_by("username") if is_admin(user) else User.objects.filter(id=user.id)

    grouped = _group_tasks_by_project_and_status(tasks)

    return render(
        request,
        "core/task_list.html",
        {
            "tasks": tasks,
            "grouped": grouped,
            "projects": projects,
            "sprints": sprints,
            "responsibles": responsibles,
            "selected_project": project_id,
            "selected_sprint": sprint_id,
            "selected_responsible": responsible_id,
            "selected_status": status,
            "q": q,
        },
    )

@login_required
@group_required("admin", "leader", "scrum")
def task_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            try:
                # 🔒 LÍMITE FREE
                check_tasks_limit_or_raise(Task)

                task = form.save(commit=False)
                task.created_by = request.user
                task.save()
                form.save_m2m()

                # 🔔 NOTIFICACIÓN: tarea nueva asignada
                if task.status == Task.Status.NEW:
                    from core.models import Notification

                    for user in task.responsibles.all():
                        Notification.objects.create(
                            recipient=user,
                            actor=request.user,
                            verb="task_new_assigned",
                            title="Nueva tarea asignada",
                            message=f"Se te asignó la tarea: {task.title}",
                            url=f"/tasks/{task.pk}/",
                        )

                messages.success(request, "Tarea principal creada correctamente.")
                return redirect("task_list")

            except ValidationError as e:
                msg = e.message if hasattr(e, "message") else str(e)
                messages.error(request, msg)
    else:
        form = TaskForm()

    return render(request, "core/task_form.html", {"form": form, "edit": False})

@login_required
def task_detail(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(Task, pk=pk)

    is_task_responsible = task.responsibles.filter(id=request.user.id).exists()
    admin_user = is_admin(request.user)

    if not admin_user and not is_task_responsible:
        raise PermissionDenied("No tienes permiso para ver esta tarea.")

    can_manage_task = admin_user
    logs = task.status_logs.all()

    # ✅ Comentarios por subtarea
    from core.forms import SubTaskCommentForm

    subtasks_qs = (
        task.subtasks
        .select_related("created_by")
        .prefetch_related("comments__created_by")
        .all()
        .order_by("-id")
    )

    subtasks = []
    for sub in subtasks_qs:
        can_edit_sub = admin_user or sub.created_by_id == request.user.id or is_task_responsible
        can_delete_sub = admin_user

        comments = list(sub.comments.all())  # ordenado por Meta (-created_at)
        first_comment = comments[0] if comments else None
        more_comments = comments[1:] if len(comments) > 1 else []

        subtasks.append(
            {
                "obj": sub,
                "can_manage": can_edit_sub,
                "can_edit": can_edit_sub,
                "can_delete": can_delete_sub,

                # ✅ comentarios
                "first_comment": first_comment,
                "more_comments": more_comments,
                "comments_total": len(comments),

                # ✅ form para comentar (modal)
                "comment_form": SubTaskCommentForm(),
            }
        )

    # ✅ Crear subtarea desde el detalle (incluye archivo)
    if request.method == "POST":
        sub_form = SubTaskForm(request.POST, request.FILES)
        if sub_form.is_valid():
            try:
                sub = sub_form.save(commit=False)

                # 🔒 Si intenta subir archivo, validar cupo
                if sub.attachment:
                    _check_files_limit_or_raise()

                sub.created_by = request.user
                sub.task = task
                sub.save()

                messages.success(request, "Subtarea creada correctamente.")
                return redirect("task_detail", pk=task.pk)

            except ValidationError as e:
                msg = e.message if hasattr(e, "message") else str(e)
                messages.error(request, msg)
        # si no válido, sigue y renderiza con errores
    else:
        sub_form = SubTaskForm()

    return render(
        request,
        "core/task_detail.html",
        {
            "task": task,
            "subtasks": subtasks,
            "sub_form": sub_form,
            "can_manage_task": can_manage_task,
            "is_task_responsible": is_task_responsible,
            "logs": logs,
            "is_admin": admin_user,
        },
    )

@login_required
def task_move(request: HttpRequest, pk: int) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)

    task = get_object_or_404(Task, pk=pk)
    user = request.user

    is_responsible = task.responsibles.filter(id=user.id).exists()
    admin_user = is_admin(user)

    if not admin_user and not is_responsible:
        return JsonResponse({"ok": False, "error": "No tienes permiso"}, status=403)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    new_status = data.get("status")
    comment = (data.get("comment") or "").strip()

    valid_status = {Task.Status.NEW, Task.Status.IN_PROGRESS, Task.Status.COMPLETED}
    if new_status not in valid_status:
        return JsonResponse({"ok": False, "error": "Estado inválido"}, status=400)

    old_status = task.status
    if new_status == old_status:
        return JsonResponse({"ok": True})

    # 🚫 Reglas para no admin
    if not admin_user:
        allowed = {
            Task.Status.NEW: Task.Status.IN_PROGRESS,
            Task.Status.IN_PROGRESS: Task.Status.COMPLETED,
        }
        if old_status not in allowed or allowed[old_status] != new_status:
            return JsonResponse({"ok": False, "error": "Movimiento no permitido"}, status=403)

    # 🔒 Admin: retroceso requiere comentario
    if admin_user:
        is_backward = (
            (old_status == Task.Status.COMPLETED and new_status in {Task.Status.IN_PROGRESS, Task.Status.NEW})
            or (old_status == Task.Status.IN_PROGRESS and new_status == Task.Status.NEW)
        )
        if is_backward and not comment:
            return JsonResponse({"ok": False, "error": "Debe indicar el motivo"}, status=400)

    # Guardar estado
    task.status = new_status
    task.save(update_fields=["status"])

    TaskStatusLog.objects.create(
        task=task,
        from_status=old_status,
        to_status=new_status,
        comment=comment if admin_user else "",
        created_by=user,
    )

    from core.models import Notification

    # 🔔 CASO 1: tarea completada → admins
    if new_status == Task.Status.COMPLETED and not admin_user:
        admins = User.objects.filter(
            Q(is_superuser=True) |
            Q(groups__name__in=["admin", "leader", "scrum"])
        ).distinct()

        for admin in admins:
            Notification.objects.create(
                recipient=admin,
                actor=user,
                verb="task_completed",
                title="Tarea completada",
                message=f"La tarea '{task.title}' fue completada y requiere revisión.",
                url=f"/tasks/{task.pk}/",
            )

    # 🔔 CASO 2: admin devuelve tarea con comentario
    if admin_user and old_status == Task.Status.COMPLETED and new_status == Task.Status.IN_PROGRESS:
        for resp in task.responsibles.all():
            Notification.objects.create(
                recipient=resp,
                actor=user,
                verb="task_returned",
                title="Tarea devuelta a En progreso",
                message=f"La tarea '{task.title}' fue devuelta con observaciones:\n{comment}",
                url=f"/tasks/{task.pk}/",
            )

    return JsonResponse({"ok": True})


@login_required
@group_required("admin", "leader", "scrum")
def task_update(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(Task, pk=pk)

    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, "Tarea actualizada.")
            return redirect("task_detail", pk=pk)
    else:
        form = TaskForm(instance=task)

    return render(request, "core/task_form.html", {"form": form, "edit": True, "task": task})
@login_required
def task_update_status(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(Task, pk=pk)

    if not is_admin(request.user) and not task.responsibles.filter(id=request.user.id).exists():
        raise PermissionDenied("No tienes permiso para actualizar esta tarea.")

    new_status = request.POST.get("status")
    if new_status not in dict(Task.Status.choices):
        messages.error(request, "Estado inválido.")
        return redirect("task_detail", pk=pk)

    old_status = task.status
    if new_status == old_status:
        messages.info(request, "No hubo cambios de estado.")
        return redirect("task_detail", pk=pk)

    # ✅ Guardar
    task.status = new_status  # type: ignore
    task.save(update_fields=["status"])

    # ✅ Log (opcional pero recomendado)
    TaskStatusLog.objects.create(
        task=task,
        from_status=old_status,
        to_status=new_status,
        comment="",  # aquí no tienes comment en este form
        created_by=request.user,
    )

    # ✅ Notificaciones según reglas
    # (import local para NO circular)
    from core.notifications import (
        notify_task_completed_to_admins,
        notify_task_returned_with_comment,
    )

    actor = request.user

    # Regla 2: cualquiera pasa a COMPLETED -> notificar admins
    if new_status == Task.Status.COMPLETED and old_status != Task.Status.COMPLETED:
        notify_task_completed_to_admins(task, actor)

    # Regla 3 SOLO aplica si admin devuelve con comentario.
    # Desde este form no hay campo "comment", entonces NO la disparamos aquí.
    # Eso queda exclusivo del Kanban (task_move), donde sí existe comment.

    messages.success(request, "Estado actualizado.")
    return redirect("task_detail", pk=pk)


@login_required
@group_required("admin", "leader", "scrum")
def task_delete(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(Task, pk=pk)

    if request.method == "POST":
        task.delete()
        messages.success(request, "Tarea eliminada.")
        return redirect("task_list")

    return render(request, "core/confirm_delete.html", {"object": task, "type": "Tarea"})


@login_required
def task_update_status(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(Task, pk=pk)

    if not is_admin(request.user) and not task.responsibles.filter(id=request.user.id).exists():
        raise PermissionDenied("No tienes permiso para actualizar esta tarea.")

    new_status = request.POST.get("status")
    if new_status in dict(Task.Status.choices):
        task.status = new_status  # type: ignore
        task.save(update_fields=["status"])
        messages.success(request, "Estado actualizado.")
    else:
        messages.error(request, "Estado inválido.")

    return redirect("task_detail", pk=pk)


# ---------- CRUD SubTask ----------

@login_required
def subtask_update(request: HttpRequest, pk: int) -> HttpResponse:
    sub = get_object_or_404(
        SubTask.objects.select_related("task", "created_by").prefetch_related("comments__created_by"),
        pk=pk,
    )
    task = sub.task

    can = (
        is_admin(request.user)
        or sub.created_by_id == request.user.id
        or task.responsibles.filter(id=request.user.id).exists()
    )
    if not can:
        raise PermissionDenied("No tienes permiso para editar esta subtarea.")

    # ✅ Comentarios ya listos para mostrar (ordenados por Meta en SubTaskComment)
    comments = list(sub.comments.all())
    first_comment = comments[0] if comments else None
    more_comments = comments[1:] if len(comments) > 1 else []

    from core.forms import SubTaskCommentForm
    comment_form = SubTaskCommentForm()

    if request.method == "POST":
        form = SubTaskForm(request.POST, request.FILES, instance=sub)
        if form.is_valid():
            try:
                # 🔒 Si está subiendo archivo nuevo (antes no tenía y ahora sí), validar cupo
                new_file = request.FILES.get("attachment")
                if new_file and not sub.attachment:
                    _check_files_limit_or_raise()

                form.save()
                messages.success(request, "Subtarea actualizada.")
                return redirect("task_detail", pk=task.pk)

            except ValidationError as e:
                msg = e.message if hasattr(e, "message") else str(e)
                messages.error(request, msg)
    else:
        form = SubTaskForm(instance=sub)

    return render(
        request,
        "core/subtask_form.html",
        {
            "form": form,
            "edit": True,
            "subtask": sub,
            "task": task,

            # ✅ comentarios
            "comments": comments,
            "first_comment": first_comment,
            "more_comments": more_comments,
            "comments_total": len(comments),
            "comment_form": comment_form,
            "is_admin": is_admin(request.user),
        },
    )

@login_required
def subtask_delete(request: HttpRequest, pk: int) -> HttpResponse:
    sub = get_object_or_404(SubTask, pk=pk)
    task = sub.task

    if not is_admin(request.user):
        raise PermissionDenied("No tienes permiso para borrar esta subtarea.")

    if request.method == "POST":
        sub.delete()
        messages.success(request, "Subtarea eliminada correctamente.")
        return redirect("task_detail", pk=task.pk)

    return render(
        request,
        "core/confirm_delete.html",
        {"object": sub, "type": "Subtarea"},
    )

from core.forms import SubTaskCommentForm
from core.models import SubTaskComment

@login_required
def subtask_add_comment(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Agrega comentario a una subtarea.
    Permisos:
      - Admin
      - Creador de la subtarea
      - Responsable de la tarea principal
    """
    if request.method != "POST":
        return redirect("task_list")

    sub = get_object_or_404(SubTask, pk=pk)
    task = sub.task

    can = (
        is_admin(request.user)
        or sub.created_by_id == request.user.id
        or task.responsibles.filter(id=request.user.id).exists()
    )
    if not can:
        raise PermissionDenied("No tienes permiso para comentar esta subtarea.")

    form = SubTaskCommentForm(request.POST)
    if form.is_valid():
        c = form.save(commit=False)
        c.subtask = sub
        c.created_by = request.user
        c.save()
        messages.success(request, "Comentario guardado.")
    else:
        # Mensaje simple (sin romper UI)
        messages.error(request, "No se pudo guardar el comentario. Revisa el texto.")

    return redirect("task_detail", pk=task.pk)
