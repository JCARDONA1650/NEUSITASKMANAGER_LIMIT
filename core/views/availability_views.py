from __future__ import annotations

import calendar
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.contrib import messages  # type: ignore
from django.contrib.auth import get_user_model  # type: ignore
from django.contrib.auth.decorators import login_required  # type: ignore
from django.core.exceptions import PermissionDenied  # type: ignore
from django.db.models import Q  # type: ignore
from django.http import HttpRequest, HttpResponse  # type: ignore
from django.shortcuts import get_object_or_404, redirect, render  # type: ignore
from django.utils import timezone  # type: ignore

from core.forms import AvailabilityForm
from core.models import Availability
from core.views.permissions import is_admin

User = get_user_model()

MONTHS_ES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]
WEEKDAYS_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


@dataclass
class DayCell:
    day: date
    in_month: bool
    is_today: bool
    events_count: int


def _safe_int(v: str | None, default: int) -> int:
    try:
        return int(v or "")
    except Exception:
        return default


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    """
    Retorna [inicio, fin] del mes en datetime naive (local).
    Luego lo convertimos a aware si USE_TZ=True.
    """
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    start_dt = datetime.combine(first_day, time.min)
    end_dt = datetime.combine(last_day, time.max)
    return start_dt, end_dt


def _month_nav(year: int, month: int) -> tuple[tuple[int, int], tuple[int, int]]:
    """(prev_year, prev_month), (next_year, next_month)"""
    prev_month = month - 1
    prev_year = year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1

    next_month = month + 1
    next_year = year
    if next_month == 13:
        next_month = 1
        next_year += 1

    return (prev_year, prev_month), (next_year, next_month)


def _build_calendar_grid(year: int, month: int, events_by_day: dict[str, int]) -> list[list[DayCell]]:
    """
    Matriz semanas (lun-dom). Incluye días fuera del mes para llenar la cuadrícula.
    Resalta días con eventos.
    """
    cal = calendar.Calendar(firstweekday=0)  # 0 = Monday
    weeks: list[list[DayCell]] = []
    today = timezone.localdate()

    for week in cal.monthdatescalendar(year, month):
        row: list[DayCell] = []
        for d in week:
            key = d.isoformat()
            row.append(
                DayCell(
                    day=d,
                    in_month=(d.month == month),
                    is_today=(d == today),
                    events_count=int(events_by_day.get(key, 0)),
                )
            )
        weeks.append(row)

    # Asegura 6 semanas (UI estable)
    while len(weeks) < 6:
        last_day = weeks[-1][-1].day
        new_week: list[DayCell] = []
        for i in range(1, 8):
            nd = last_day + timedelta(days=i)
            key = nd.isoformat()
            new_week.append(
                DayCell(
                    day=nd,
                    in_month=(nd.month == month),
                    is_today=(nd == today),
                    events_count=int(events_by_day.get(key, 0)),
                )
            )
        weeks.append(new_week)

    return weeks[:6]


@login_required
def availability_list(request: HttpRequest) -> HttpResponse:
    user = request.user

    # Mes visible (si no viene, mes actual)
    today = timezone.localdate()
    year = _safe_int(request.GET.get("y"), today.year)
    month = _safe_int(request.GET.get("m"), today.month)
    if month < 1 or month > 12:
        month = today.month

    user_filter = request.GET.get("user") or ""
    
    # Nuevo: Vista grupal para usuarios no-admin
    group_view = request.GET.get("group_view") == "true"

    # Query base
    events = Availability.objects.select_related("user").all()

    # Permisos: no-admin solo ve los suyos (EXCEPTO en vista grupal)
    if not is_admin(user):
        if not group_view:
            events = events.filter(user=user)
        # Si group_view=true, muestra todos los eventos pero no permite editar
    else:
        if user_filter:
            events = events.filter(user__id=user_filter)

    # Boundaries del mes (incluye eventos que INTERSECTAN el mes)
    start_dt, end_dt = _month_bounds(year, month)

    tz = timezone.get_current_timezone()
    if timezone.is_naive(start_dt):
        start_dt = timezone.make_aware(start_dt, tz)
    if timezone.is_naive(end_dt):
        end_dt = timezone.make_aware(end_dt, tz)

    # Intersección: (start <= end_dt) AND (end >= start_dt)
    events_month = events.filter(
        Q(start_datetime__lte=end_dt) & Q(end_datetime__gte=start_dt)
    ).order_by("start_datetime")

    # Lista usuarios para filtro
    users = User.objects.all().order_by("username") if is_admin(user) else User.objects.filter(id=user.id)

    # Conteo por día (para resaltar) + detalles por día
    events_by_day: dict[str, int] = {}
    day_details: dict[str, list[dict]] = {}

    for ev in events_month:
        start_date = timezone.localtime(ev.start_datetime).date()
        end_date = timezone.localtime(ev.end_datetime).date()

        cur = start_date
        while cur <= end_date:
            key = cur.isoformat()
            events_by_day[key] = events_by_day.get(key, 0) + 1

            day_details.setdefault(key, []).append(
                {
                    "user": getattr(ev.user, "username", str(ev.user_id)),
                    "user_id": ev.user_id,  # Agregar user_id
                    "title": ev.title,
                    "start": timezone.localtime(ev.start_datetime).strftime("%Y-%m-%d %H:%M"),
                    "end": timezone.localtime(ev.end_datetime).strftime("%Y-%m-%d %H:%M"),
                    "description": ev.description or "",
                    "link": ev.link or "",
                    "id": ev.id,
                }
            )
            cur += timedelta(days=1)

    # Calendario 6x7
    weeks = _build_calendar_grid(year, month, events_by_day)

    # Navegación del mes
    (py, pm), (ny, nm) = _month_nav(year, month)

    # Label del mes para el template
    month_label = f"{MONTHS_ES[month]} {year}"

    # Querystrings para prev/next preservando filtro user y group_view
    def _qs(y: int, m: int) -> str:
        parts = [f"y={y}", f"m={m}"]
        if user_filter:
            parts.append(f"user={user_filter}")
        if group_view:
            parts.append("group_view=true")
        return "&".join(parts)

    context = {
        "users": users,
        "events": events_month,
        "selected_user": user_filter,
        "user_filter": user_filter,
        "year": year,
        "month": month,
        "month_name": MONTHS_ES[month],
        "month_label": month_label,
        "weekdays": WEEKDAYS_ES,
        "weeks": weeks,
        "prev_y": py,
        "prev_m": pm,
        "next_y": ny,
        "next_m": nm,
        "prev_qs": _qs(py, pm),
        "next_qs": _qs(ny, nm),
        # IMPORTANTE: Serializar a JSON aquí para pasarlo al template
        "day_details_json": json.dumps(day_details),
        "total_events": events_month.count(),
        "is_admin": is_admin(user),
        "group_view": group_view,  # Nuevo
    }
    return render(request, "core/availability_list.html", context)


@login_required
def availability_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = AvailabilityForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.save()
            messages.success(request, "Evento registrado.")
            return redirect("availability_list")
    else:
        form = AvailabilityForm()
    return render(request, "core/availability_form.html", {"form": form, "edit": False})


@login_required
def availability_update(request: HttpRequest, pk: int) -> HttpResponse:
    event = get_object_or_404(Availability, pk=pk)

    if not is_admin(request.user) and event.user_id != request.user.id:
        raise PermissionDenied("No puedes editar este evento.")

    if request.method == "POST":
        form = AvailabilityForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, "Evento actualizado.")
            return redirect("availability_list")
    else:
        form = AvailabilityForm(instance=event)

    return render(request, "core/availability_form.html", {"form": form, "edit": True, "event": event})


@login_required
def availability_delete(request: HttpRequest, pk: int) -> HttpResponse:
    event = get_object_or_404(Availability, pk=pk)

    if not is_admin(request.user) and event.user_id != request.user.id:
        raise PermissionDenied("No puedes borrar este evento.")

    if request.method == "POST":
        event.delete()
        messages.success(request, "Evento eliminado.")
        return redirect("availability_list")

    return render(request, "core/confirm_delete.html", {"object": event, "type": "Disponibilidad"})