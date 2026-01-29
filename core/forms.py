"""
Forms for the NeusiTaskManager core application.

These forms derive from Django's ModelForm and encapsulate
validation logic for each model. Where appropriate, custom
clean methods are implemented to enforce business rules such as
the free tier limits (PlanLimits).
"""
from __future__ import annotations

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Availability, Daily, Epic, Project, Sprint, SubTask, Task

# Intentar usar PlanLimits (nuevo). Si no existe por migraciones, cae a settings.
try:
    from .models import PlanLimits
except Exception:  # pragma: no cover
    PlanLimits = None  # type: ignore


def _limits():
    """
    Devuelve un dict con los límites FREE.
    Prioridad:
      1) PlanLimits (admin editable)
      2) settings.* (fallback)
    """
    if PlanLimits is not None:
        try:
            pl = PlanLimits.get_solo()
            return {
                "max_projects": pl.max_projects,
                "max_tasks": pl.max_tasks,
            }
        except Exception:
            pass

    # fallback por si aún no aplicaste migraciones
    return {
        "max_projects": getattr(settings, "FREE_MAX_PROJECTS", 10),
        "max_tasks": getattr(settings, "FREE_MAX_TASKS", 50),  # si no existe, usar 50
    }


# ---------------------------------------------------------------------
# PROJECT
# ---------------------------------------------------------------------
class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            "name",
            "description",
            "budget",
            "start_date",
            "end_date",
            "members",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "members": forms.SelectMultiple(attrs={"class": "form-select"}),
        }

    def clean(self):
        cleaned_data = super().clean()

        lim = _limits()
        max_projects = int(lim["max_projects"])

        # SOLO aplicar el límite cuando se CREA (no al editar)
        if not self.instance or not self.instance.pk:
            if Project.objects.count() >= max_projects:
                raise ValidationError(
                    f"Se alcanzó el máximo de proyectos ({max_projects}) "
                    "permitido en la versión gratuita. Elimine un proyecto o contacte soporte."
                )
        return cleaned_data


# ---------------------------------------------------------------------
# SPRINT
# ---------------------------------------------------------------------
class SprintForm(forms.ModelForm):
    class Meta:
        model = Sprint
        fields = ["project", "name", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


# ---------------------------------------------------------------------
# EPIC
# ---------------------------------------------------------------------
class EpicForm(forms.ModelForm):
    class Meta:
        model = Epic
        fields = ["project", "name", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


# ---------------------------------------------------------------------
# TASK (Principal)
# ---------------------------------------------------------------------
class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            "project",
            "epic",
            "sprint",
            "title",
            "description",
            "kpis", 
            "story_points",   # ✅ ENUM (1,2,3,5,8,13,21)
            "budget",
            "status",
            "priority",       # ✅ Matriz Eisenhower real
            "responsibles",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "kpis": forms.Textarea(attrs={"rows": 3, "placeholder": "Ej: Tiempo, % avance, entregables, calidad, SLA..."}),
            "responsibles": forms.SelectMultiple(attrs={"class": "form-select"}),
        }

    def clean(self):
        cleaned_data = super().clean()

        lim = _limits()
        max_tasks = int(lim["max_tasks"])

        # SOLO aplicar límite al CREAR
        if not self.instance or not self.instance.pk:
            if Task.objects.count() >= max_tasks:
                raise ValidationError(
                    f"Se alcanzó el máximo de tareas principales ({max_tasks}) "
                    "permitido en la versión gratuita. Elimine tareas o contacte soporte."
                )

        return cleaned_data


# ---------------------------------------------------------------------
# SUBTASK
# ---------------------------------------------------------------------
class SubTaskForm(forms.ModelForm):
    class Meta:
        model = SubTask
        fields = [
            "title",
            "description",
            "story_points",   # ✅ Máx 7
            "budget",
            "status",
            "attachment",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_attachment(self):
        f = self.cleaned_data.get("attachment")
        if not f:
            return f

        # 1) Extensión permitida
        import os
        ext = os.path.splitext(f.name)[1].lower()
        allowed_exts = getattr(settings, "ALLOWED_UPLOAD_EXTS", {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx", ".xlsx"})
        if ext not in allowed_exts:
            raise ValidationError(
                f"Extensión no permitida ({ext}). Permitidas: {', '.join(sorted(allowed_exts))}"
            )

        # 2) Tamaño máximo por archivo (FREE)
        max_mb = int(getattr(settings, "FREE_MAX_FILE_SIZE_MB", 8))
        max_bytes = max_mb * 1024 * 1024
        if f.size > max_bytes:
            raise ValidationError(
                f"El archivo supera el límite de {max_mb}MB permitido en la versión gratuita."
            )

        # 3) Cupo total por cantidad (PlanLimits.max_files si existe)
        try:
            from .models import PlanLimits
            limits = PlanLimits.get_solo()
            max_files = int(limits.max_files)
        except Exception:
            max_files = int(getattr(settings, "FREE_MAX_FILES", 1000))

        from django.db.models import Q
        total_files = SubTask.objects.exclude(Q(attachment="") | Q(attachment__isnull=True)).count()

        # Si estamos editando y ya tenía archivo, no sumar doble
        if self.instance and self.instance.pk and getattr(self.instance, "attachment", None):
            had_file = bool(self.instance.attachment)
        else:
            had_file = False

        if not had_file and total_files >= max_files:
            raise ValidationError(
                "Su sesión free no alcanza para seguir cargando archivos. "
                "Contacte con su proveedor de software para cambiar el plan."
            )

        return f

    def clean_budget(self):
        budget = self.cleaned_data.get("budget") or 0
        task: Task | None = getattr(self.instance, "task", None)

        if task and budget > task.remaining_budget:
            raise ValidationError(
                f"El presupuesto de la subtarea ({budget}) excede el presupuesto restante "
                f"de la tarea ({task.remaining_budget})."
            )
        return budget

from .models import SubTaskComment


class SubTaskCommentForm(forms.ModelForm):
    class Meta:
        model = SubTaskComment
        fields = ("body",)
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Escribe un comentario de avance...",
                    "class": "form-control",
                }
            )
        }

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise ValidationError("El comentario no puede ir vacío.")
        return body
# ---------------------------------------------------------------------
# DAILY
# ---------------------------------------------------------------------
class DailyForm(forms.ModelForm):
    class Meta:
        model = Daily
        fields = ["yesterday", "today", "impediment"]
        widgets = {
            "yesterday": forms.Textarea(attrs={"rows": 2}),
            "today": forms.Textarea(attrs={"rows": 2}),
            "impediment": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        impediment = cleaned_data.get("impediment")
        if impediment and len(impediment.strip()) == 0:
            cleaned_data["impediment"] = ""
        return cleaned_data


# ---------------------------------------------------------------------
# AVAILABILITY
# ---------------------------------------------------------------------
class AvailabilityForm(forms.ModelForm):
    class Meta:
        model = Availability
        fields = [
            "title",
            "description",
            "start_datetime",
            "end_datetime",
            "link",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "start_datetime": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "end_datetime": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["start_datetime"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["end_datetime"].input_formats = ["%Y-%m-%dT%H:%M"]

        # Si estamos editando, formatear las fechas correctamente
        if self.instance and self.instance.pk:
            if self.instance.start_datetime:
                local_start = timezone.localtime(self.instance.start_datetime)
                self.fields["start_datetime"].initial = local_start.strftime("%Y-%m-%dT%H:%M")

            if self.instance.end_datetime:
                local_end = timezone.localtime(self.instance.end_datetime)
                self.fields["end_datetime"].initial = local_end.strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_datetime")
        end = cleaned_data.get("end_datetime")

        if start and end and start >= end:
            raise ValidationError(
                "La fecha/hora de inicio debe ser anterior a la fecha/hora de finalización."
            )
        return cleaned_data
