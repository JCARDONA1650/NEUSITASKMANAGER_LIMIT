# core/context_processors.py
from __future__ import annotations

from django.http import HttpRequest

def notifications_context(request: HttpRequest) -> dict:
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"notif_unread": 0}

    # import local para evitar circular
    from core.models import Notification

    unread = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return {"notif_unread": unread}
