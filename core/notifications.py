# core/notifications.py
from __future__ import annotations

from typing import Iterable, Optional

from django.contrib.auth.models import AbstractUser
from django.contrib.auth import get_user_model
from django.db.models import Q

from core.models import Task, Notification  # ✅ IMPORTA EL MODELO DESDE models (NO desde core.notifications)

User = get_user_model()

ADMIN_ROLES = {"admin", "leader", "scrum"}


def is_admin_like(u: AbstractUser) -> bool:
    return bool(getattr(u, "is_superuser", False) or getattr(u, "is_staff", False))


def admin_like_users_qs():
    return User.objects.filter(
        Q(is_superuser=True)
        | Q(is_staff=True, is_superuser=False)
        | Q(groups__name__in=list(ADMIN_ROLES))
    ).distinct()


def notify_many(
    *,
    recipients: Iterable[AbstractUser],
    actor: Optional[AbstractUser],
    verb: str,
    title: str,
    message: str = "",
    url: str = "",
) -> None:
    rows = []
    actor_id = actor.id if actor else None

    for r in recipients:
        rows.append(
            Notification(
                recipient_id=r.id,
                actor_id=actor_id,
                verb=verb,
                title=title,
                message=message,
                url=url,
            )
        )

    if rows:
        Notification.objects.bulk_create(rows)


def notify_task_assigned_new(task: Task, actor: Optional[AbstractUser]) -> None:
    recipients = list(task.responsibles.all())
    if actor:
        recipients = [r for r in recipients if r.id != actor.id]
    if not recipients:
        return

    notify_many(
        recipients=recipients,
        actor=actor,
        verb="task_new_assigned",
        title="Tienes una tarea nueva",
        message=f"Tarea: {task.title}\nProyecto: {task.project.name}",
        url=f"/tasks/{task.pk}/",
    )


def notify_task_completed_to_admins(task: Task, actor: Optional[AbstractUser]) -> None:
    recipients = list(admin_like_users_qs())
    if actor:
        recipients = [r for r in recipients if r.id != actor.id]
    if not recipients:
        return

    who = (actor.get_full_name() or actor.username) if actor else "Sistema"

    notify_many(
        recipients=recipients,
        actor=actor,
        verb="task_completed",
        title="Tarea completada para revisión",
        message=f"{who} marcó como COMPLETADA la tarea: {task.title}\nProyecto: {task.project.name}",
        url=f"/tasks/{task.pk}/",
    )


def notify_task_returned_with_comment(task: Task, actor: Optional[AbstractUser], comment: str) -> None:
    recipients = list(task.responsibles.all())
    if actor:
        recipients = [r for r in recipients if r.id != actor.id]
    if not recipients:
        return

    who = (actor.get_full_name() or actor.username) if actor else "Admin"

    notify_many(
        recipients=recipients,
        actor=actor,
        verb="task_returned",
        title="Corrección: tu tarea volvió a EN PROGRESO",
        message=f"{who} cambió el estado a EN PROGRESO.\nComentario:\n{comment}",
        url=f"/tasks/{task.pk}/",
    )
