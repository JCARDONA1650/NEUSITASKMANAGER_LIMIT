# core/notifications.py
from __future__ import annotations

from typing import Iterable, Optional

from django.contrib.auth import get_user_model
from django.db.models import Q

from core.models import Task, Notification

User = get_user_model()

ADMIN_ROLES = {"admin", "leader", "scrum"}


def is_admin_like(u) -> bool:
    return bool(getattr(u, "is_superuser", False) or getattr(u, "is_staff", False))


def admin_like_users_qs():
    """
    Admin-like = superuser OR staff OR (grupo admin/leader/scrum).
    """
    return (
        User.objects.filter(
            Q(is_superuser=True)
            | Q(is_staff=True)
            | Q(groups__name__in=list(ADMIN_ROLES))
        )
        .distinct()
    )


def notify_many(
    *,
    recipients: Iterable[User],
    actor: Optional[User],
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
                recipient=r,
                actor_id=actor_id,
                verb=verb,
                title=title,
                message=message,
                url=url,
            )
        )

    if rows:
        Notification.objects.bulk_create(rows)


def notify_task_assigned_new(task: Task, actor: Optional[User]) -> None:
    """
    Regla 1:
    Admin crea tarea, asigna responsables y la deja en NEW => notificar responsables.
    """
    recipients = list(task.responsibles.all())
    if actor:
        recipients = [r for r in recipients if r.id != actor.id]

    if not recipients:
        return

    title = "Tienes una tarea nueva"
    msg = f"Tarea: {task.title}\nProyecto: {task.project.name}"
    url = f"/tasks/{task.pk}/"

    notify_many(
        recipients=recipients,
        actor=actor,
        verb="task_new_assigned",
        title=title,
        message=msg,
        url=url,
    )


def notify_task_completed_to_admins(task: Task, actor: Optional[User]) -> None:
    """
    Regla 2:
    Cualquier usuario cambia a COMPLETED => notificar admins para revisión.
    """
    recipients = list(admin_like_users_qs())
    if actor:
        recipients = [r for r in recipients if r.id != actor.id]

    if not recipients:
        return

    who = (actor.get_full_name() or actor.username) if actor else "Sistema"
    title = "Tarea completada para revisión"
    msg = f"{who} marcó como COMPLETADA la tarea: {task.title}\nProyecto: {task.project.name}"
    url = f"/tasks/{task.pk}/"

    notify_many(
        recipients=recipients,
        actor=actor,
        verb="task_completed",
        title=title,
        message=msg,
        url=url,
    )


def notify_task_returned_with_comment(task: Task, actor: Optional[User], comment: str) -> None:
    """
    Regla 3:
    Admin devuelve de COMPLETED -> IN_PROGRESS con comentario => notificar responsables.
    """
    recipients = list(task.responsibles.all())
    if actor:
        recipients = [r for r in recipients if r.id != actor.id]

    if not recipients:
        return

    who = (actor.get_full_name() or actor.username) if actor else "Admin"
    title = "Corrección: tu tarea volvió a EN PROGRESO"
    msg = f"{who} cambió el estado a EN PROGRESO.\n\nComentario:\n{comment}"
    url = f"/tasks/{task.pk}/"

    notify_many(
        recipients=recipients,
        actor=actor,
        verb="task_returned",
        title=title,
        message=msg,
        url=url,
    )
