from __future__ import annotations

from django.contrib import messages  # type: ignore
from django.contrib.auth import get_user_model  # type: ignore
from django.contrib.auth.decorators import login_required  # type: ignore
from django.core.exceptions import PermissionDenied  # type: ignore
from django.http import HttpRequest, HttpResponse  # type: ignore
from django.shortcuts import get_object_or_404, redirect, render  # type: ignore
from django.utils import timezone  # type: ignore
from core.models import Daily
from core.forms import DailyForm
from core.models import Daily

from core.utils import is_admin as is_admin_user 

from django.utils.dateparse import parse_date
User = get_user_model()


@login_required
def daily_list(request: HttpRequest) -> HttpResponse:
    user = request.user
    selected_user = request.GET.get("user", "")  # para mantener seleccionado

    if is_admin_user(user):
        dailies = Daily.objects.select_related("user").all()
        if selected_user:
            dailies = dailies.filter(user__id=selected_user)
        users = User.objects.all().order_by("username")
        is_admin_flag = True
    else:
        dailies = Daily.objects.select_related("user").filter(user=user)
        users = User.objects.filter(id=user.id)
        is_admin_flag = False

    dailies = dailies.order_by("-date", "-created_at")

    return render(
        request,
        "core/daily_list.html",
        {
            "dailies": dailies,
            "users": users,
            "is_admin": is_admin_flag,
            "selected_user": selected_user,
        },
    )

@login_required
def daily_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = DailyForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.date = timezone.localdate()
            obj.save()
            messages.success(request, "Daily registrado.")
            return redirect("daily_list")
    else:
        form = DailyForm()
    return render(request, "core/daily_form.html", {"form": form})


def _is_admin_like(user) -> bool:
    # mismo criterio que usas en templates
    if user.is_superuser:
        return True
    # si tienes role_tags, aquí NO aplica; esto es Python.
    # Usa groups:
    return user.groups.filter(name__in=["admin", "leader", "scrum"]).exists()


@login_required
def daily_bulk_delete(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("daily_list")

    if not _is_admin_like(request.user):
        raise PermissionDenied("No tienes permiso para eliminar dailies.")

    mode = request.POST.get("mode", "selected")  # selected | range

    qs = Daily.objects.all()

    deleted = 0

    if mode == "selected":
        ids = request.POST.getlist("daily_ids")
        if not ids:
            messages.warning(request, "No seleccionaste dailies.")
            return redirect("daily_list")

        deleted = qs.filter(id__in=ids).delete()[0]
        messages.success(request, f"Se eliminaron {deleted} daily(s).")
        return redirect("daily_list")

    # mode == "range"
    date_from = parse_date(request.POST.get("date_from") or "")
    date_to = parse_date(request.POST.get("date_to") or "")

    if not date_from or not date_to:
        messages.error(request, "Debes indicar fecha desde y hasta.")
        return redirect("daily_list")

    if date_from > date_to:
        messages.error(request, "La fecha 'desde' no puede ser mayor que 'hasta'.")
        return redirect("daily_list")

    user_id = request.POST.get("user_id")  # opcional, para borrar de un usuario

    qs2 = qs.filter(date__gte=date_from, date__lte=date_to)
    if user_id:
        qs2 = qs2.filter(user_id=user_id)

    deleted = qs2.delete()[0]
    messages.success(request, f"Se eliminaron {deleted} daily(s) entre {date_from} y {date_to}.")
    return redirect("daily_list")
