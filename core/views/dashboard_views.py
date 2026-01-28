from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import json

from django.contrib.auth import get_user_model  # type: ignore
from django.contrib.auth.decorators import login_required  # type: ignore
from django.db.models import Count, Q, Sum  # type: ignore
from django.db.models.functions import Coalesce  # type: ignore
from django.http import HttpRequest, HttpResponse  # type: ignore
from django.shortcuts import render  # type: ignore
from django.utils import timezone  # type: ignore
from django.utils.dateparse import parse_date  # type: ignore

from core.models import Daily, Project, Sprint, SubTask, Task, TaskStatusLog
from core.views.permissions import is_admin

User = get_user_model()


def _business_days(dfrom: date, dto: date) -> int:
    """Cuenta días hábiles (L-V) en rango inclusivo."""
    if dfrom > dto:
        return 0
    n = 0
    cur = dfrom
    while cur <= dto:
        if cur.weekday() < 5:
            n += 1
        cur += timedelta(days=1)
    return n


def _daterange(dfrom: date, dto: date) -> list[date]:
    out: list[date] = []
    cur = dfrom
    while cur <= dto:
        out.append(cur)
        cur += timedelta(days=1)
    return out


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    # -----------------------------
    # Filtros
    # -----------------------------
    project_id = request.GET.get("project") or ""
    responsible_id = request.GET.get("responsible") or ""
    sprint_id = request.GET.get("sprint") or ""

    today = timezone.localdate()
    date_from_str = request.GET.get("from") or ""
    date_to_str = request.GET.get("to") or ""

    date_from = parse_date(date_from_str) if date_from_str else None
    date_to = parse_date(date_to_str) if date_to_str else None

    if not date_to:
        date_to = today
    if not date_from:
        date_from = date_to - timedelta(days=6)

    if date_from > date_to:
        date_from, date_to = date_to, date_from

    # -----------------------------
    # Base queryset tareas
    # -----------------------------
    tasks = (
        Task.objects.select_related("project", "sprint")
        .prefetch_related("responsibles")
        .all()
    )

    if not is_admin(request.user):
        tasks = tasks.filter(responsibles=request.user)

    if project_id:
        tasks = tasks.filter(project__id=project_id)
    if sprint_id:
        tasks = tasks.filter(sprint__id=sprint_id)
    if responsible_id:
        tasks = tasks.filter(responsibles__id=responsible_id)

    tasks = tasks.distinct()

    # -----------------------------
    # Métricas tareas
    # -----------------------------
    total_tasks = tasks.count()
    status_counts = tasks.values("status").annotate(c=Count("id")).order_by()

    status_map = {s["status"]: s["c"] for s in status_counts}
    new_tasks = int(status_map.get(Task.Status.NEW, 0))
    in_progress_tasks = int(status_map.get(Task.Status.IN_PROGRESS, 0))
    completed_tasks = int(status_map.get(Task.Status.COMPLETED, 0))

    progress = (completed_tasks / total_tasks * 100.0) if total_tasks else 0.0

    # -----------------------------
    # Subtareas (del set filtrado)
    # -----------------------------
    subtasks_qs = SubTask.objects.filter(task__in=tasks)
    total_subtasks = subtasks_qs.count()
    completed_subtasks = subtasks_qs.filter(status=SubTask.Status.COMPLETED).count()
    sub_progress = (completed_subtasks / total_subtasks * 100.0) if total_subtasks else 0.0

    # -----------------------------
    # Presupuesto (Task.spent_budget es campo real)
    # -----------------------------
    total_budget = tasks.aggregate(v=Coalesce(Sum("budget"), Decimal("0.00")))["v"] or Decimal("0.00")
    spent_budget = tasks.aggregate(v=Coalesce(Sum("spent_budget"), Decimal("0.00")))["v"] or Decimal("0.00")

    if total_budget > 0:
        budget_used_percent = float((spent_budget / total_budget) * Decimal("100"))
    else:
        budget_used_percent = 0.0

    # -----------------------------
    # Usuarios para métricas dailies
    # -----------------------------
    if is_admin(request.user):
        if responsible_id:
            users_qs = User.objects.filter(id=responsible_id)
        else:
            users_qs = User.objects.filter(tasks__in=tasks).distinct()
    else:
        users_qs = User.objects.filter(id=request.user.id)

    users = list(users_qs.order_by("username"))

    # -----------------------------
    # Dailies en rango + métricas por usuario
    # (within_time_range es property => NO se puede filtrar en SQL)
    # -----------------------------
    bd = _business_days(date_from, date_to)

    dailies_range = Daily.objects.select_related("user").filter(date__range=[date_from, date_to])

    if is_admin(request.user):
        if responsible_id:
            dailies_range = dailies_range.filter(user__id=responsible_id)
    else:
        dailies_range = dailies_range.filter(user=request.user)

    daily_stats = []
    for u in users:
        qs_u = list(dailies_range.filter(user=u).order_by("-created_at"))

        total_reg = len(qs_u)
        within_reg = sum(1 for d in qs_u if d.within_time_range)

        participation = (total_reg / bd * 100.0) if bd else 0.0
        compliance = (within_reg / bd * 100.0) if bd else 0.0
        not_completed = max(0.0, 100.0 - participation)
        late = max(0.0, participation - compliance)

        daily_stats.append(
            {
                "user": u,
                "participation": participation,
                "compliance": compliance,
                "late": late,
                "not_completed": not_completed,
                "total_reg": total_reg,
                "within_reg": within_reg,
            }
        )

    within_total = sum(x["within_reg"] for x in daily_stats)
    daily_efficiency = (within_total / (bd * len(users)) * 100.0) if (bd and users) else 0.0

    # -----------------------------
    # Presupuesto por proyecto (tabla + gráfica)
    # -----------------------------
    budget_by_project = (
        tasks.values("project__name")
        .annotate(
            total=Coalesce(Sum("budget"), Decimal("0.00")),
            spent=Coalesce(Sum("spent_budget"), Decimal("0.00")),
            tasks=Count("id"),
        )
        .order_by("project__name")
    )

    budget_rows = []
    for row in budget_by_project:
        tb = row["total"] or Decimal("0.00")
        sb = row["spent"] or Decimal("0.00")
        pct = float((sb / tb * Decimal("100"))) if tb > 0 else 0.0
        budget_rows.append(
            {"project": row["project__name"] or "—", "total": tb, "spent": sb, "pct": pct, "tasks": row["tasks"]}
        )

    # -----------------------------
    # Detalle HU (últimas 25)
    # -----------------------------
    recent_tasks = tasks.order_by("-id")[:25]

    sub_counts = (
        SubTask.objects.filter(task__in=recent_tasks)
        .values("task_id")
        .annotate(
            total=Count("id"),
            done=Count("id", filter=Q(status=SubTask.Status.COMPLETED)),
        )
    )
    sub_map = {x["task_id"]: {"total": x["total"], "done": x["done"]} for x in sub_counts}

    task_rows = []
    for t in recent_tasks:
        sc = sub_map.get(t.id, {"total": 0, "done": 0})
        task_rows.append({"task": t, "sub_done": sc["done"], "sub_total": sc["total"]})

    # ============================================================
    # ✅ NUEVO 1: Gráfica tipo línea (avance en el tiempo)
    # ------------------------------------------------------------
    # Calcula % de tareas completadas de forma acumulada por día.
    # Usa TaskStatusLog (to_status=completed) como fuente de "fecha de cierre".
    # Si una tarea está completed pero no hay log, usa created_at como fallback.
    # ============================================================
    day_list = _daterange(date_from, date_to)

    # logs de cierre dentro de TODA la vida, pero filtrados por tasks
    completed_logs = (
        TaskStatusLog.objects.filter(task__in=tasks, to_status=Task.Status.COMPLETED)
        .select_related("task")
        .order_by("created_at")
    )

    # mapa task_id -> completion_date
    completion_date_by_task: dict[int, date] = {}
    for lg in completed_logs:
        completion_date_by_task[lg.task_id] = timezone.localdate(lg.created_at)

    # fallback: tasks completed sin log
    # (NO usar .only() porque tasks tiene select_related y Django no permite defer + select_related)
    for t in tasks.filter(status=Task.Status.COMPLETED).values("id", "created_at"):
        tid = t["id"]
        if tid not in completion_date_by_task:
            completion_date_by_task[tid] = timezone.localdate(t["created_at"])

    # serie acumulada
    total_for_trend = total_tasks if total_tasks else 0
    completed_count_by_day: list[int] = []
    pct_by_day: list[float] = []

    for d in day_list:
        done_up_to = sum(1 for _, cd in completion_date_by_task.items() if cd <= d)
        completed_count_by_day.append(done_up_to)
        pct = (done_up_to / total_for_trend * 100.0) if total_for_trend else 0.0
        pct_by_day.append(round(pct, 2))

    chart_work_trend = {
        "labels": [x.strftime("%Y-%m-%d") for x in day_list],
        "completed": completed_count_by_day,
        "percent": pct_by_day,  # si prefieres % en la línea
    }

    # ============================================================
    # ✅ NUEVO 2: Tabla por responsable: subtareas NEW/IN_PROGRESS/COMPLETED
    # ------------------------------------------------------------
    # OJO: SubTask no tiene responsible directo.
    # Se cuenta por los responsables de la tarea padre (M2M).
    # Si una tarea tiene 2 responsables, esa subtarea contará para ambos (normal en tableros).
    # ============================================================
    # users a mostrar: los mismos del dashboard (users)
    user_ids = [u.id for u in users]

    # conteo por usuario con annotations sobre la relación tasks__subtasks
    users_with_sub_counts = (
        User.objects.filter(id__in=user_ids)
        .annotate(
            st_new=Count(
                "tasks__subtasks",
                filter=Q(tasks__in=tasks, tasks__subtasks__status=SubTask.Status.NEW),
                distinct=True,
            ),
            st_in_progress=Count(
                "tasks__subtasks",
                filter=Q(tasks__in=tasks, tasks__subtasks__status=SubTask.Status.IN_PROGRESS),
                distinct=True,
            ),
            st_completed=Count(
                "tasks__subtasks",
                filter=Q(tasks__in=tasks, tasks__subtasks__status=SubTask.Status.COMPLETED),
                distinct=True,
            ),
        )
        .order_by("username")
    )

    responsible_subtask_rows = []
    for u in users_with_sub_counts:
        responsible_subtask_rows.append(
            {
                "user": u,
                "new": int(getattr(u, "st_new", 0) or 0),
                "in_progress": int(getattr(u, "st_in_progress", 0) or 0),
                "completed": int(getattr(u, "st_completed", 0) or 0),
            }
        )

    # -----------------------------
    # Catálogos filtros
    # -----------------------------
    projects = Project.objects.all().order_by("name")
    sprints = Sprint.objects.all().order_by("-id")
    responsibles = (
        User.objects.all().order_by("username")
        if is_admin(request.user)
        else User.objects.filter(id=request.user.id)
    )

    # -----------------------------
    # Datos para Chart.js (serializables)
    # -----------------------------
    chart_tasks_status = {
        "labels": ["Nuevas", "En progreso", "Completadas"],
        "data": [new_tasks, in_progress_tasks, completed_tasks],
    }
    chart_budget_projects = {
        "labels": [x["project"] for x in budget_rows],
        "total": [float(x["total"]) for x in budget_rows],
        "spent": [float(x["spent"]) for x in budget_rows],
    }
    chart_daily_users = {
        "labels": [
            (u.get_full_name() if hasattr(u, "get_full_name") and u.get_full_name() else u.username)
            for u in users
        ],
        "compliance": [round(x["compliance"], 2) for x in daily_stats],
        "participation": [round(x["participation"], 2) for x in daily_stats],
    }

    return render(
        request,
        "core/dashboard.html",
        {
            "selected_project": project_id,
            "selected_sprint": sprint_id,
            "selected_responsible": responsible_id,
            "date_from": date_from,
            "date_to": date_to,
            "is_admin": is_admin(request.user),

            "total_tasks": total_tasks,
            "new_tasks": new_tasks,
            "in_progress_tasks": in_progress_tasks,
            "completed_tasks": completed_tasks,
            "progress": progress,

            "total_subtasks": total_subtasks,
            "completed_subtasks": completed_subtasks,
            "sub_progress": sub_progress,

            "total_budget": total_budget,
            "spent_budget": spent_budget,
            "budget_used_percent": budget_used_percent,

            "daily_efficiency": daily_efficiency,
            "business_days": bd,

            "daily_stats": daily_stats,
            "budget_rows": budget_rows,
            "task_rows": task_rows,

            # ✅ NUEVO
            "chart_work_trend": chart_work_trend,
            "responsible_subtask_rows": responsible_subtask_rows,

            "projects": projects,
            "sprints": sprints,
            "responsibles": responsibles,

            "chart_tasks_status": chart_tasks_status,
            "chart_budget_projects": chart_budget_projects,
            "chart_daily_users": chart_daily_users,
        },
    )
