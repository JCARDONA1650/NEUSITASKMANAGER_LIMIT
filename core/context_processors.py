# core/context_processors.py
from core.models import Notification

def notifications_badge(request):
    if not request.user.is_authenticated:
        return {"notif_unread": 0}

    unread = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return {"notif_unread": unread}

# core/context_processors.py
from core.models import Notification

def notifications_context(request):
    if not request.user.is_authenticated:
        return {"notif_unread": 0}

    unread = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return {"notif_unread": unread}

