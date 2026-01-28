
from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from django.conf import settings  # type: ignore
from django.contrib import messages  # type: ignore
from django.contrib.auth.decorators import login_required, user_passes_test  # type: ignore
from django.contrib.auth import get_user_model

from django.contrib.auth.mixins import LoginRequiredMixin  # type: ignore
from django.contrib.auth.models import Group  # type: ignore
from django.core.exceptions import PermissionDenied  # type: ignore
from django.http import FileResponse, HttpRequest, HttpResponse, HttpResponseRedirect  # type: ignore
from django.shortcuts import get_object_or_404, redirect, render  # type: ignore
from django.urls import reverse, reverse_lazy  # type: ignore
from django.utils import timezone  # type: ignore
from django.views import View  # type: ignore
from django.views.generic import ListView, CreateView, DetailView  # type: ignore

from reportlab.pdfgen import canvas  # type: ignore

from .forms import (
    AvailabilityForm,
    DailyForm,
    EpicForm,
    ProjectForm,
    SprintForm,
    SubTaskForm,
    TaskForm,
)
from .models import Availability, Daily, Epic, Project, Sprint, SubTask, Task
from django.contrib.auth import get_user_model
User = get_user_model()

def group_required(*group_names: str):
    """Decorator to restrict a view to users belonging to specific groups.

    Users who are superusers bypass the group check.  If the user is
    not authenticated or not a member of one of the allowed groups
    ``PermissionDenied`` is raised.
    """

    def in_groups(u):
        if not u.is_authenticated:
            return False
        if u.is_superuser:
            return True
        user_groups = u.groups.values_list('name', flat=True)
        return any(group in user_groups for group in group_names)

    return user_passes_test(in_groups)


def is_admin(user) -> bool:
    """Return True if the user is an admin/leader (has elevated privileges)."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=['admin', 'leader', 'scrum']).exists()


@login_required
def home(request: HttpRequest) -> HttpResponse:
    """Redirects to the backlog list.

    This simple view acts as the landing page for authenticated users.
    """
    return redirect('task_list')


@login_required
@group_required('admin', 'leader', 'scrum')
def project_list(request: HttpRequest) -> HttpResponse:
    projects = Project.objects.all()
    return render(request, 'core/project_list.html', {'projects': projects})


@login_required
@group_required('admin', 'leader', 'scrum')
def project_create(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()
            form.save_m2m()
            messages.success(request, 'Proyecto creado correctamente.')
            return redirect('project_list')
    else:
        form = ProjectForm()
    return render(request, 'core/project_form.html', {'form': form})


@login_required
@group_required('admin', 'leader', 'scrum')
def sprint_create(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = SprintForm(request.POST)
        if form.is_valid():
            sprint = form.save(commit=False)
            sprint.created_by = request.user
            sprint.save()
            messages.success(request, 'Sprint creado correctamente.')
            return redirect('project_list')
    else:
        form = SprintForm()
    return render(request, 'core/sprint_form.html', {'form': form})


@login_required
@group_required('admin', 'leader', 'scrum')
def epic_create(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = EpicForm(request.POST)
        if form.is_valid():
            epic = form.save(commit=False)
            epic.created_by = request.user
            epic.save()
            messages.success(request, 'Épica creada correctamente.')
            return redirect('project_list')
    else:
        form = EpicForm()
    return render(request, 'core/epic_form.html', {'form': form})


@login_required
def task_list(request: HttpRequest) -> HttpResponse:
    """Display a backlog of tasks filtered by query parameters.

    Non‑admin users only see tasks where they are responsible.  Admin
    users see all tasks.  Filters include project, sprint and
    responsible user.  Results are ordered by priority and status.
    """
    tasks = Task.objects.all()
    user = request.user
    if not is_admin(user):
        tasks = tasks.filter(responsibles=user)
    # Filtering by query parameters
    project_id = request.GET.get('project')
    sprint_id = request.GET.get('sprint')
    responsible_id = request.GET.get('responsible')
    if project_id:
        tasks = tasks.filter(project__id=project_id)
    if sprint_id:
        tasks = tasks.filter(sprint__id=sprint_id)
    if responsible_id:
        tasks = tasks.filter(responsibles__id=responsible_id)
    tasks = tasks.order_by('priority', 'status')
    projects = Project.objects.all()
    sprints = Sprint.objects.all()
    responsibles = User.objects.all() if is_admin(user) else User.objects.filter(id=user.id)
    return render(request, 'core/task_list.html', {
        'tasks': tasks,
        'projects': projects,
        'sprints': sprints,
        'responsibles': responsibles,
        'selected_project': project_id,
        'selected_sprint': sprint_id,
        'selected_responsible': responsible_id,
    })


@login_required
@group_required('admin', 'leader', 'scrum')
def task_create(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.save()
            form.save_m2m()
            messages.success(request, 'Tarea principal creada correctamente.')
            return redirect('task_list')
    else:
        form = TaskForm()
    return render(request, 'core/task_form.html', {'form': form})


@login_required
def task_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Show details of a task and handle creation of subtasks."""
    task = get_object_or_404(Task, pk=pk)
    # Permissions: only responsibles or admins can view
    if not is_admin(request.user) and not task.responsibles.filter(id=request.user.id).exists():
        raise PermissionDenied("No tienes permiso para ver esta tarea.")
    subtasks = task.subtasks.all()
    if request.method == 'POST':
        sub_form = SubTaskForm(request.POST, request.FILES)
        if sub_form.is_valid():
            subtask = sub_form.save(commit=False)
            subtask.created_by = request.user
            subtask.save()
            messages.success(request, 'Subtarea creada correctamente.')
            return redirect('task_detail', pk=task.pk)
    else:
        sub_form = SubTaskForm(initial={'task': task})
    return render(request, 'core/task_detail.html', {
        'task': task,
        'subtasks': subtasks,
        'sub_form': sub_form,
    })


@login_required
def task_update_status(request: HttpRequest, pk: int) -> HttpResponse:
    """Update the status of a task.

    Admins can update any task.  Regular users can only update tasks they
    are responsible for.  The new status is provided via POST.
    """
    task = get_object_or_404(Task, pk=pk)
    if not is_admin(request.user) and not task.responsibles.filter(id=request.user.id).exists():
        raise PermissionDenied("No tienes permiso para actualizar esta tarea.")
    new_status = request.POST.get('status')
    if new_status in dict(Task.Status.choices):
        task.status = new_status
        task.save(update_fields=['status'])
        messages.success(request, 'Estado de la tarea actualizado.')
    return redirect('task_detail', pk=pk)


@login_required
def daily_list(request: HttpRequest) -> HttpResponse:
    """List daily stand‑up entries.

    Admin users can see all dailies or filter by user via query
    parameter ``user``; regular users only see their own dailies.
    """
    user = request.user
    if is_admin(user):
        dailies = Daily.objects.all()
        user_filter = request.GET.get('user')
        if user_filter:
            dailies = dailies.filter(user__id=user_filter)
        users = User.objects.all()
    else:
        dailies = Daily.objects.filter(user=user)
        users = User.objects.filter(id=user.id)
    dailies = dailies.order_by('-date', '-created_at')
    return render(request, 'core/daily_list.html', {
        'dailies': dailies,
        'users': users,
    })


@login_required
def daily_create(request: HttpRequest) -> HttpResponse:
    """Create a daily stand‑up entry for the current user."""
    if request.method == 'POST':
        form = DailyForm(request.POST)
        if form.is_valid():
            daily = form.save(commit=False)
            daily.user = request.user
            daily.date = timezone.localdate()
            daily.save()
            messages.success(request, 'Registro de daily guardado.')
            return redirect('daily_list')
    else:
        form = DailyForm()
    return render(request, 'core/daily_form.html', {'form': form})


@login_required
def availability_list(request: HttpRequest) -> HttpResponse:
    """Display availability calendar entries.

    Admin users see all entries; others only see their own or optionally
    filter by user when provided via query parameter.
    """
    user = request.user
    events = Availability.objects.all() if is_admin(user) else Availability.objects.filter(user=user)
    user_filter = request.GET.get('user')
    if is_admin(user) and user_filter:
        events = events.filter(user__id=user_filter)
    users = User.objects.all() if is_admin(user) else User.objects.filter(id=user.id)
    events = events.order_by('start_datetime')
    return render(request, 'core/availability_list.html', {
        'events': events,
        'users': users,
    })


@login_required
def availability_create(request: HttpRequest) -> HttpResponse:
    """Create an availability or meeting entry."""
    if request.method == 'POST':
        form = AvailabilityForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.user = request.user
            event.save()
            messages.success(request, 'Disponibilidad/Evento registrado.')
            return redirect('availability_list')
    else:
        form = AvailabilityForm()
    return render(request, 'core/availability_form.html', {'form': form})


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Render a dashboard summarising metrics across projects, tasks and dailies."""
    # Filter parameters
    project_id = request.GET.get('project')
    responsible_id = request.GET.get('responsible')
    sprint_id = request.GET.get('sprint')
    tasks = Task.objects.all()
    if not is_admin(request.user):
        tasks = tasks.filter(responsibles=request.user)
    if project_id:
        tasks = tasks.filter(project__id=project_id)
    if sprint_id:
        tasks = tasks.filter(sprint__id=sprint_id)
    if responsible_id:
        tasks = tasks.filter(responsibles__id=responsible_id)
    total_tasks = tasks.count()
    completed_tasks = tasks.filter(status=Task.Status.COMPLETED).count()
    progress = (completed_tasks / total_tasks * 100.0) if total_tasks else 0.0
    total_subtasks = SubTask.objects.filter(task__in=tasks).count()
    completed_subtasks = SubTask.objects.filter(task__in=tasks, status=SubTask.Status.COMPLETED).count()
    sub_progress = (completed_subtasks / total_subtasks * 100.0) if total_subtasks else 0.0
    total_budget = Decimal('0.00')
    spent_budget = Decimal('0.00')
    for task in tasks:
        total_budget += task.budget
        spent_budget += task.spent_budget
    budget_used_percent = (spent_budget / total_budget * 100.0) if total_budget > 0 else 0.0
    # Daily efficiency: proportion of users who registered dailies within time range today
    today = timezone.localdate()
    users = User.objects.all() if is_admin(request.user) else [request.user]
    within_count = 0
    total_users = len(users)
    for u in users:
        daily = Daily.objects.filter(user=u, date=today).order_by('-created_at').first()
        if daily and daily.within_time_range:
            within_count += 1
    daily_efficiency = (within_count / total_users * 100.0) if total_users else 0.0
    projects = Project.objects.all()
    sprints = Sprint.objects.all()
    responsibles = User.objects.all() if is_admin(request.user) else User.objects.filter(id=request.user.id)
    return render(request, 'core/dashboard.html', {
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'progress': progress,
        'total_subtasks': total_subtasks,
        'completed_subtasks': completed_subtasks,
        'sub_progress': sub_progress,
        'total_budget': total_budget,
        'spent_budget': spent_budget,
        'budget_used_percent': budget_used_percent,
        'daily_efficiency': daily_efficiency,
        'projects': projects,
        'sprints': sprints,
        'responsibles': responsibles,
        'selected_project': project_id,
        'selected_sprint': sprint_id,
        'selected_responsible': responsible_id,
    })


@login_required
def matrix_priority(request: HttpRequest) -> HttpResponse:
    """Render the Aizenjaguer priority matrix.

    Tasks are grouped into categories defined by their priority.  Users
    can optionally filter by project, sprint or responsible via query
    parameters.  Non‑admins only see their own tasks.
    """
    tasks = Task.objects.all()
    if not is_admin(request.user):
        tasks = tasks.filter(responsibles=request.user)
    project_id = request.GET.get('project')
    sprint_id = request.GET.get('sprint')
    responsible_id = request.GET.get('responsible')
    if project_id:
        tasks = tasks.filter(project__id=project_id)
    if sprint_id:
        tasks = tasks.filter(sprint__id=sprint_id)
    if responsible_id:
        tasks = tasks.filter(responsibles__id=responsible_id)
    matrix = {
        'urgent': tasks.filter(priority=Task.Priority.URGENT),
        'important': tasks.filter(priority=Task.Priority.IMPORTANT),
        'not_urgent': tasks.filter(priority=Task.Priority.NOT_URGENT),
        'other': tasks.filter(priority=Task.Priority.OTHER),
    }
    projects = Project.objects.all()
    sprints = Sprint.objects.all()
    responsibles = User.objects.all() if is_admin(request.user) else User.objects.filter(id=request.user.id)
    return render(request, 'core/matrix_priority.html', {
        'matrix': matrix,
        'projects': projects,
        'sprints': sprints,
        'responsibles': responsibles,
        'selected_project': project_id,
        'selected_sprint': sprint_id,
        'selected_responsible': responsible_id,
    })


@login_required
def matrix_status(request: HttpRequest) -> HttpResponse:
    """Render the status matrix grouping tasks by status.

    Non‑admin users only see tasks they are responsible for.  Admin
    users can update status via a POST to the task_update_status view.
    """
    tasks = Task.objects.all()
    if not is_admin(request.user):
        tasks = tasks.filter(responsibles=request.user)
    matrix = {
        'new': tasks.filter(status=Task.Status.NEW),
        'in_progress': tasks.filter(status=Task.Status.IN_PROGRESS),
        'completed': tasks.filter(status=Task.Status.COMPLETED),
    }
    return render(request, 'core/matrix_status.html', {
        'matrix': matrix,
    })


@login_required
def export_matrix_pdf(request: HttpRequest) -> HttpResponse:
    """Export the priority matrix to a PDF file using ReportLab.

    The PDF lists tasks grouped by priority.  Admin users see all
    tasks; others only their own tasks.
    """
    tasks = Task.objects.all()
    if not is_admin(request.user):
        tasks = tasks.filter(responsibles=request.user)
    matrix = {
        'Urgente': tasks.filter(priority=Task.Priority.URGENT),
        'Importante': tasks.filter(priority=Task.Priority.IMPORTANT),
        'No urgente': tasks.filter(priority=Task.Priority.NOT_URGENT),
        'Otro': tasks.filter(priority=Task.Priority.OTHER),
    }
    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    y = 800
    p.setFont("Helvetica-Bold", 16)
    p.drawString(200, y, "Matriz de prioridad")
    p.setFont("Helvetica", 12)
    y -= 40
    for category, qs in matrix.items():
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, category)
        y -= 20
        p.setFont("Helvetica", 12)
        if not qs:
            p.drawString(70, y, "Sin tareas")
            y -= 20
        for task in qs:
            p.drawString(70, y, f"{task.title} – {task.get_status_display()} – {task.progress_percent:.0f}%")
            y -= 15
            if y < 50:
                p.showPage()
                y = 800
    p.showPage()
    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename='matriz_prioridad.pdf')