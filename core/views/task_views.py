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

from core.forms import (
    SubTaskAttachmentsForm,
    SubTaskCommentForm,
    SubTaskForm,
    TaskForm,
)
from core.models import (
    PlanLimits,
    Project,
    Sprint,
    SubTask,
    SubTaskAttachment,
    SubTaskComment,
    Task,
    TaskStatusLog,
    check_tasks_limit_or_raise,
)
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
    return SubTaskAttachment.objects.count()


def _check_files_limit_or_raise(extra_files: int = 1) -> None:
    limits = PlanLimits.get_solo()
    total_files = _files_count()
    if total_files + int(extra_files) > limits.max_files:
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
                check_tasks_limit_or_raise(Task)

                obj = form.save(commit=False)
                obj.created_by = request.user
                obj.save()
                form.save_m2m()

                # Notificaciones (si existen en tu proyecto)
                if obj.status == Task.Status.NEW and obj.responsibles.exists():
                    from core.notifications import notify_task_assigned_new
                    notify_task_assigned_new(obj, request.user)

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

    subtasks_qs = task.subtasks.all().order_by("-id")
    subtasks = []
    for sub in subtasks_qs:
        can_edit_sub = admin_user or sub.created_by_id == request.user.id or is_task_responsible
        can_delete_sub = admin_user
        subtasks.append({"obj": sub, "can_manage": can_edit_sub, "can_edit": can_edit_sub, "can_delete": can_delete_sub})

    # Crear subtarea + multi-archivos desde detalle
    if request.method == "POST":
        sub_form = SubTaskForm(request.POST)
        files_form = SubTaskAttachmentsForm(request.POST, request.FILES)

        if sub_form.is_valid() and files_form.is_valid():
            try:
                sub = sub_form.save(commit=False)
                sub.created_by = request.user
                sub.task = task
                sub.save()

                files = files_form.cleaned_data.get("attachments") or []
                if files:
                    _check_files_limit_or_raise(extra_files=len(files))
                    SubTaskAttachment.objects.bulk_create(
                        [SubTaskAttachment(subtask=sub, uploaded_by=request.user, file=f) for f in files]
                    )

                messages.success(request, "Subtarea creada correctamente.")
                return redirect("task_detail", pk=task.pk)

            except ValidationError as e:
                msg = e.message if hasattr(e, "message") else str(e)
                messages.error(request, msg)
        else:
            messages.error(request, "Revisa los campos / archivos.")
    else:
        sub_form = SubTaskForm()
        files_form = SubTaskAttachmentsForm()

    return render(
        request,
        "core/task_detail.html",
        {
            "task": task,
            "subtasks": subtasks,
            "sub_form": sub_form,
            "files_form": files_form,
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
        return JsonResponse({"ok": False, "error": "No tienes permiso para mover esta tarea"}, status=403)

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

    if not admin_user:
        allowed_forward = {Task.Status.NEW: Task.Status.IN_PROGRESS, Task.Status.IN_PROGRESS: Task.Status.COMPLETED}
        if old_status not in allowed_forward or allowed_forward[old_status] != new_status:
            return JsonResponse({"ok": False, "error": "Solo puedes avanzar al siguiente estado"}, status=403)

    if admin_user:
        is_backward = (
            (old_status == Task.Status.COMPLETED and new_status in {Task.Status.IN_PROGRESS, Task.Status.NEW})
            or (old_status == Task.Status.IN_PROGRESS and new_status == Task.Status.NEW)
        )
        if is_backward and not comment:
            return JsonResponse({"ok": False, "error": "Debe indicar el motivo del retroceso"}, status=400)

    task.status = new_status
    task.save(update_fields=["status"])

    TaskStatusLog.objects.create(
        task=task,
        from_status=old_status,
        to_status=new_status,
        comment=comment if admin_user else "",
        created_by=user,
    )

    # Notificaciones (si existen)
    from core.notifications import notify_task_completed_to_admins, notify_task_returned_with_comment

    if new_status == Task.Status.COMPLETED and old_status != Task.Status.COMPLETED:
        notify_task_completed_to_admins(task, user)

    if admin_user and old_status == Task.Status.COMPLETED and new_status == Task.Status.IN_PROGRESS and comment:
        notify_task_returned_with_comment(task, user, comment)

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
    if new_status not in dict(Task.Status.choices):
        messages.error(request, "Estado inválido.")
        return redirect("task_detail", pk=pk)

    old_status = task.status
    if new_status == old_status:
        messages.info(request, "No hubo cambios de estado.")
        return redirect("task_detail", pk=pk)

    task.status = new_status  # type: ignore
    task.save(update_fields=["status"])

    TaskStatusLog.objects.create(
        task=task,
        from_status=old_status,
        to_status=new_status,
        comment="",
        created_by=request.user,
    )

    from core.notifications import notify_task_completed_to_admins
    if new_status == Task.Status.COMPLETED and old_status != Task.Status.COMPLETED:
        notify_task_completed_to_admins(task, request.user)

    messages.success(request, "Estado actualizado.")
    return redirect("task_detail", pk=pk)


# ---------- CRUD SubTask ----------
@login_required
def subtask_update(request: HttpRequest, pk: int) -> HttpResponse:
    sub = get_object_or_404(SubTask, pk=pk)
    task = sub.task

    can = is_admin(request.user) or sub.created_by_id == request.user.id or task.responsibles.filter(id=request.user.id).exists()
    if not can:
        raise PermissionDenied("No tienes permiso para editar esta subtarea.")

    if request.method == "POST":
        action = request.POST.get("action", "save")

        form = SubTaskForm(request.POST, instance=sub)
        files_form = SubTaskAttachmentsForm(request.POST, request.FILES)
        comment_form = SubTaskCommentForm(request.POST)

        try:
            if action == "save":
                if form.is_valid():
                    form.save()
                    messages.success(request, "Subtarea actualizada.")
                else:
                    messages.error(request, "Revisa los campos.")
                return redirect("subtask_update", pk=sub.pk)

            if action == "upload":
                if files_form.is_valid():
                    files = files_form.cleaned_data.get("attachments") or []
                    if files:
                        _check_files_limit_or_raise(extra_files=len(files))
                        SubTaskAttachment.objects.bulk_create(
                            [SubTaskAttachment(subtask=sub, uploaded_by=request.user, file=f) for f in files]
                        )
                        messages.success(request, "Archivos agregados.")
                    else:
                        messages.info(request, "No seleccionaste archivos.")
                else:
                    messages.error(request, "Archivos inválidos.")
                return redirect("subtask_update", pk=sub.pk)

            if action == "comment":
                if comment_form.is_valid():
                    SubTaskComment.objects.create(
                        subtask=sub,
                        author=request.user,
                        text=comment_form.cleaned_data["text"],
                    )
                    messages.success(request, "Comentario agregado.")
                else:
                    messages.error(request, "Comentario inválido.")
                return redirect("subtask_update", pk=sub.pk)

        except ValidationError as e:
            msg = e.message if hasattr(e, "message") else str(e)
            messages.error(request, msg)

    else:
        form = SubTaskForm(instance=sub)
        files_form = SubTaskAttachmentsForm()
        comment_form = SubTaskCommentForm()

    attachments = sub.attachments.all()
    comments = sub.comments.select_related("author").all()

    return render(
        request,
        "core/subtask_form.html",
        {
            "form": form,
            "edit": True,
            "subtask": sub,
            "task": task,
            "attachments": attachments,
            "comments": comments,
            "files_form": files_form,
            "comment_form": comment_form,
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

    return render(request, "core/confirm_delete.html", {"object": sub, "type": "Subtarea"})
@login_required
def subtask_attachment_delete(request: HttpRequest, pk: int) -> HttpResponse:
    attachment = get_object_or_404(SubTaskAttachment, pk=pk)
    sub = attachment.subtask
    task = sub.task

    # Permisos: admin o creador del attachment o creador de subtarea o responsable de la tarea
    can = (
        is_admin(request.user)
        or (attachment.uploaded_by_id == request.user.id)
        or (sub.created_by_id == request.user.id)
        or task.responsibles.filter(id=request.user.id).exists()
    )
    if not can:
        raise PermissionDenied("No tienes permiso para eliminar este archivo.")

    if request.method == "POST":
        # borra el archivo físico y el registro
        attachment.file.delete(save=False)
        attachment.delete()
        messages.success(request, "Archivo eliminado.")
        return redirect("subtask_update", pk=sub.pk)

    # Confirmación simple reutilizando tu confirm_delete.html
    return render(
        request,
        "core/confirm_delete.html",
        {"object": attachment, "type": "Archivo"},
    )
