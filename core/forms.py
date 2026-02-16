"""
Forms for the NeusiTaskManager core application.
"""
from __future__ import annotations

import os
from typing import Any

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from .models import (
    Availability,
    Daily,
    Epic,
    PlanLimits,
    Project,
    Sprint,
    SubTask,
    SubTaskAttachment,
    SubTaskComment,
    Task,
)


def _limits() -> dict[str, int]:
    pl = PlanLimits.get_solo()
    return {
        "max_projects": int(pl.max_projects),
        "max_tasks": int(pl.max_tasks),
        "max_files": int(pl.max_files),
    }


# ---------------------------------------------------------------------
# PROJECT
# ---------------------------------------------------------------------
class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description", "budget", "start_date", "end_date", "members"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "members": forms.SelectMultiple(attrs={"class": "form-select"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        lim = _limits()
        if not self.instance.pk and Project.objects.count() >= lim["max_projects"]:
            raise ValidationError(
                f"Se alcanzó el máximo de proyectos ({lim['max_projects']}) en la versión gratuita."
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
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


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
            "story_points",
            "budget",
            "status",
            "priority",
            "responsibles",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "kpis": forms.Textarea(attrs={"rows": 3, "placeholder": "Ej: Tiempo, % avance, entregables..."}),
            "responsibles": forms.SelectMultiple(attrs={"class": "form-select"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        lim = _limits()
        if not self.instance.pk and Task.objects.count() >= lim["max_tasks"]:
            raise ValidationError(
                f"Se alcanzó el máximo de tareas principales ({lim['max_tasks']}) en la versión gratuita."
            )
        return cleaned_data


# ---------------------------------------------------------------------
# SUBTASK
# ---------------------------------------------------------------------
class SubTaskForm(forms.ModelForm):
    class Meta:
        model = SubTask
        fields = ["title", "description", "story_points", "budget", "status"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "story_points": forms.Select(attrs={"class": "form-select"}),
            "budget": forms.NumberInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_budget(self):
        budget = self.cleaned_data.get("budget") or 0
        task: Task | None = getattr(self.instance, "task", None)
        if task and budget > task.remaining_budget:
            raise ValidationError(
                f"El presupuesto de la subtarea ({budget}) excede el presupuesto restante de la tarea ({task.remaining_budget})."
            )
        return budget


# ---------------------------------------------------------------------
# MULTI FILE UPLOAD (CORRECTO: acepta lista de archivos)
# ---------------------------------------------------------------------
class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultiFileInput

    def clean(self, data, initial=None):
        # data puede ser UploadedFile o lista[UploadedFile]
        if data in (None, "", []):
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        cleaned_files = []
        for f in data:
            cleaned_files.append(super().clean(f, initial))
        return cleaned_files


class SubTaskAttachmentsForm(forms.Form):
    attachments = MultipleFileField(required=False)

    def clean(self):
        cleaned = super().clean()
        files = cleaned.get("attachments") or []
        if not files:
            return cleaned

        allowed_exts = getattr(
            settings,
            "ALLOWED_UPLOAD_EXTS",
            {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx", ".xlsx"},
        )

        max_mb = int(getattr(settings, "FREE_MAX_FILE_SIZE_MB", 8))
        max_bytes = max_mb * 1024 * 1024

        lim = _limits()
        max_files = int(lim["max_files"])

        total_files = SubTaskAttachment.objects.count()
        if total_files + len(files) > max_files:
            raise ValidationError(
                "Su sesión free no alcanza para seguir cargando archivos. Contacte con su proveedor."
            )

        for f in files:
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in allowed_exts:
                raise ValidationError(
                    f"Extensión no permitida ({ext}). Permitidas: {', '.join(sorted(allowed_exts))}"
                )
            if f.size > max_bytes:
                raise ValidationError(
                    f"El archivo '{f.name}' supera el límite de {max_mb}MB permitido en la versión gratuita."
                )

        return cleaned


# ---------------------------------------------------------------------
# COMMENTS
# ---------------------------------------------------------------------
class SubTaskCommentForm(forms.ModelForm):
    class Meta:
        model = SubTaskComment
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(
                attrs={"rows": 3, "class": "form-control", "placeholder": "Escribe un comentario..."}
            ),
        }


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
        fields = ["title", "description", "start_datetime", "end_datetime", "link"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "start_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "end_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.fields["start_datetime"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["end_datetime"].input_formats = ["%Y-%m-%dT%H:%M"]

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
            raise ValidationError("La fecha/hora de inicio debe ser anterior a la fecha/hora de finalización.")
        return cleaned_data
