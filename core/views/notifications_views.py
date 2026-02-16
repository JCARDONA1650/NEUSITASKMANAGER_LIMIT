# core/views/notifications_views.py
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Notification


@login_required
def notifications_list(request: HttpRequest) -> HttpResponse:
    qs = Notification.objects.filter(recipient=request.user).order_by("-created_at")
    unread = qs.filter(is_read=False).count()

    return render(
        request,
        "core/notifications_list.html",
        {
            "items": qs[:200],  # simple límite visual
            "unread": unread,
        },
    )


@login_required
def notification_read(request: HttpRequest, pk: int) -> HttpResponse:
    n = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not n.is_read:
        n.is_read = True
        n.save(update_fields=["is_read"])

    if n.url:
        return redirect(n.url)
    return redirect("notifications_list")


@login_required
def notifications_read_all(request: HttpRequest) -> HttpResponse:
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return redirect("notifications_list")
