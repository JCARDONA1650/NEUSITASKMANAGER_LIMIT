from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

from django.conf import settings  # type: ignore
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model  # type: ignore
from django.db import models  # type: ignore
from django.db.models import Sum  # type: ignore
from django.db.models.functions import Coalesce  # type: ignore
from django.utils import timezone  # type: ignore

User = get_user_model()

class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications_sent")

    verb = models.CharField(max_length=50)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    url = models.CharField(max_length=300, blank=True)

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.recipient} - {self.verb} - {self.title}"
class PlanLimits(models.Model):
    """
    Plan FREE: límites globales de la app.
    Se maneja como singleton (1 fila).
    """
    # usuarios
    max_admin_users = models.PositiveIntegerField(default=5)
    max_normal_users = models.PositiveIntegerField(default=10)

    # nuevos límites
    max_projects = models.PositiveIntegerField(default=5)
    max_tasks = models.PositiveIntegerField(default=50)
    max_files = models.PositiveIntegerField(default=1000)

    class Meta:
        verbose_name = "Plan (Límites)"
        verbose_name_plural = "Plan (Límites)"

    def __str__(self):
        return (
            f"FREE: admin={self.max_admin_users}, normal={self.max_normal_users}, "
            f"projects={self.max_projects}, tasks={self.max_tasks}, files={self.max_files}"
        )

    @classmethod
    def get_solo(cls) -> "PlanLimits":
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create(
                max_admin_users=5,
                max_normal_users=10,
                max_projects=5,
                max_tasks=50,
                max_files=1000,
            )
        return obj


# -----------------------
# Validadores centralizados
# -----------------------

def check_user_limits_or_raise(new_role: str):
    """
    new_role: 'admin' o 'normal'
    Admin = is_staff=True (o superuser).
    """
    limits = PlanLimits.get_solo()

    admin_count = User.objects.filter(is_staff=True, is_superuser=False).count()
    normal_count = User.objects.filter(is_staff=False, is_superuser=False).count()

    if new_role == "admin":
        if admin_count >= limits.max_admin_users:
            raise ValidationError(
                "Su sesión free no alcanza para seguir creando usuarios ADMIN. "
                "Contacte con su proveedor de software para cambiar el plan."
            )
    else:
        if normal_count >= limits.max_normal_users:
            raise ValidationError(
                "Su sesión free no alcanza para seguir creando usuarios. "
                "Contacte con su proveedor de software para cambiar el plan."
            )


def check_projects_limit_or_raise(projects_model):
    limits = PlanLimits.get_solo()
    total = projects_model.objects.count()
    if total >= limits.max_projects:
        raise ValidationError(
            "Su sesión free no alcanza para seguir creando proyectos. "
            "Contacte con su proveedor de software para cambiar el plan."
        )


def check_tasks_limit_or_raise(tasks_model):
    limits = PlanLimits.get_solo()
    total = tasks_model.objects.count()
    if total >= limits.max_tasks:
        raise ValidationError(
            "Su sesión free no alcanza para seguir creando tareas. "
            "Contacte con su proveedor de software para cambiar el plan."
        )


def check_files_limit_or_raise(files_model):
    limits = PlanLimits.get_solo()
    total = files_model.objects.count()
    if total >= limits.max_files:
        raise ValidationError(
            "Su sesión free no alcanza para seguir cargando archivos. "
            "Contacte con su proveedor de software para cambiar el plan."
        )


class Project(models.Model):
    """Represents a project containing sprints, epics and tasks."""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="projects_created")
    members = models.ManyToManyField(User, related_name="projects", blank=True)

    def __str__(self) -> str:
        return self.name

    @property
    def remaining_budget(self) -> Decimal:
        """
        Presupuesto restante del proyecto = presupuesto - sum(spent_budget de sus tareas)
        spent_budget es CAMPO real en Task (actualizado por signals).
        """
        spent = self.tasks.aggregate(v=Coalesce(Sum("spent_budget"), Decimal("0.00")))["v"]
        return (self.budget or Decimal("0.00")) - (spent or Decimal("0.00"))

    @property
    def progress_percent(self) -> float:
        tasks = self.tasks.all()
        total = tasks.count()
        if total == 0:
            return 0.0
        completed = tasks.filter(status=Task.Status.COMPLETED).count()
        return (completed / total) * 100.0


class Sprint(models.Model):
    """Represents a sprint within a project."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="sprints")
    name = models.CharField(max_length=100)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="sprints_created")

    def __str__(self) -> str:
        return f"{self.project.name} – {self.name}"


class Epic(models.Model):
    """Represents an epic grouping multiple tasks within a project."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="epics")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="epics_created")

    def __str__(self) -> str:
        return self.name


class Task(models.Model):
    """Represents a principal task within an epic and/or sprint."""

    class Status(models.TextChoices):
        NEW = "new", "Nueva"
        IN_PROGRESS = "in_progress", "En progreso"
        COMPLETED = "completed", "Completada"

    class Priority(models.TextChoices):
        DO = "do", "Urgente e Importante "
        PLAN = "plan", "Importante no Urgente "
        DELEGATE = "delegate", "Urgente no Importante "
        ELIMINATE = "eliminate", "Ni Urgente ni Importante"

    class StoryPoints(models.IntegerChoices):
        SP_1 = 1, "1"
        SP_2 = 2, "2"
        SP_3 = 3, "3"
        SP_5 = 5, "5"
        SP_8 = 8, "8"
        SP_13 = 13, "13"
        SP_21 = 21, "21"

    project = models.ForeignKey("Project", on_delete=models.CASCADE, related_name="tasks")
    epic = models.ForeignKey("Epic", on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    sprint = models.ForeignKey("Sprint", on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # ✅ NUEVO: KPIs (solo texto)
    kpis = models.TextField(blank=True, verbose_name="KPIs")

    story_points = models.IntegerField(choices=StoryPoints.choices, default=StoryPoints.SP_3)

    budget = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    # ✅ CAMPO REAL (se alimenta automáticamente con signals desde SubTask.budget)
    spent_budget = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    status = models.CharField(max_length=15, choices=Status.choices, default=Status.NEW)
    priority = models.CharField(max_length=15, choices=Priority.choices, default=Priority.PLAN)

    responsibles = models.ManyToManyField(User, related_name="tasks", blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="tasks_created")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.title

    @property
    def remaining_budget(self) -> Decimal:
        b = self.budget or Decimal("0.00")
        s = self.spent_budget or Decimal("0.00")
        return b - s

    @property
    def progress_percent(self) -> float:
        total = self.subtasks.count()
        if total == 0:
            return 0.0
        completed = self.subtasks.filter(status=SubTask.Status.COMPLETED).count()
        return (completed / total) * 100.0


class SubTask(models.Model):
    """Represents a subtask within a principal task."""

    class Status(models.TextChoices):
        NEW = "new", "Nueva"
        IN_PROGRESS = "in_progress", "En progreso"
        COMPLETED = "completed", "Completada"

    class StoryPoints(models.IntegerChoices):
        SP_1 = 1, "1"
        SP_2 = 2, "2"
        SP_3 = 3, "3"
        SP_5 = 5, "5"
        SP_7 = 7, "7"

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="subtasks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    story_points = models.IntegerField(choices=StoryPoints.choices, default=StoryPoints.SP_1)

    budget = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.NEW)
    attachment = models.FileField(upload_to="attachments/", null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="subtasks_created")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.task.title} > {self.title}"

class SubTaskComment(models.Model):
    """
    Comentarios de avance por subtarea.
    Guarda historial: quién, cuándo, qué comentó.
    """
    subtask = models.ForeignKey(
        "SubTask",
        on_delete=models.CASCADE,
        related_name="comments",
    )
    body = models.TextField()
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subtask_comments_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        who = getattr(self.created_by, "username", None) or "Sistema"
        return f"Comment by {who} on SubTask #{self.subtask_id}"


class Daily(models.Model):
    """Represents a daily stand-up record for a user."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="dailies")
    date = models.DateField(default=timezone.localdate)
    yesterday = models.TextField(verbose_name="¿Qué hice ayer?")
    today = models.TextField(verbose_name="¿Qué haré hoy?")
    impediment = models.TextField(verbose_name="Impedimentos / Observaciones", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Daily {self.user.username} {self.date}"

    @property
    def within_time_range(self) -> bool:
        try:
            settings_obj = DailySettings.objects.first()
            if not settings_obj:
                return True  # si no hay config, no bloquea
        except Exception:
            return True

        created_local = timezone.localtime(self.created_at)
        tz = timezone.get_current_timezone()

        start_dt = timezone.make_aware(
            datetime.combine(self.date, time(settings_obj.start_hour, 0)),
            tz,
        )
        end_dt = timezone.make_aware(
            datetime.combine(self.date, time(settings_obj.end_hour, 0)),
            tz,
        )

        return start_dt <= created_local <= end_dt
from django.db import models

class DailySettings(models.Model):
    start_hour = models.PositiveSmallIntegerField(default=5)
    end_hour = models.PositiveSmallIntegerField(default=9)

    def __str__(self):
        return f"Horario Daily: {self.start_hour}:00 - {self.end_hour}:00"

    class Meta:
        verbose_name = "Configuración Daily"
        verbose_name_plural = "Configuración Daily"

class Availability(models.Model):
    """Represents an availability or meeting event for a user."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="availabilities")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    link = models.URLField(blank=True)

    def __str__(self) -> str:
        return f"{self.user.username}: {self.title}"


class TaskStatusLog(models.Model):
    task = models.ForeignKey("Task", related_name="status_logs", on_delete=models.CASCADE)
    from_status = models.CharField(max_length=32)
    to_status = models.CharField(max_length=32)

    comment = models.TextField(blank=True, default="")

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
