from __future__ import annotations

from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import (
    Availability,
    Daily,
    Epic,
    PlanLimits,
    Project,
    Sprint,
    SubTask,
    Task,
    check_projects_limit_or_raise,
    check_tasks_limit_or_raise,
)

User = get_user_model()


# =========================================================
# Helpers: límites de archivos (usando SubTask.attachment)
# =========================================================
def _check_files_limit_or_raise():
    """
    Tu app no tiene modelo UploadedFile. Los archivos están en SubTask.attachment.
    Así que el límite se calcula por cantidad de SubTask con attachment cargado.
    """
    limits = PlanLimits.get_solo()
    total_files = SubTask.objects.exclude(Q(attachment="") | Q(attachment__isnull=True)).count()
    if total_files >= limits.max_files:
        raise ValidationError(
            "Su sesión free no alcanza para seguir cargando archivos. "
            "Contacte con su proveedor de software para cambiar el plan."
        )


# =========================================================
# PlanLimits en Admin (singleton)
# =========================================================
@admin.register(PlanLimits)
class PlanLimitsAdmin(admin.ModelAdmin):
    list_display = (
        "max_admin_users",
        "max_normal_users",
        "max_projects",
        "max_tasks",
        "max_files",
    )

    def has_add_permission(self, request):
        # singleton: solo una fila
        return not PlanLimits.objects.exists()


# =========================================================
# Bloqueo de creación de usuarios desde /admin
# =========================================================
class UserCreationAdminForm(forms.ModelForm):
    class Meta:
        model = User
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()

        # Solo validar al crear (no al editar)
        if self.instance and self.instance.pk:
            return cleaned

        limits = PlanLimits.get_solo()

        is_staff = bool(cleaned.get("is_staff", False))
        is_superuser = bool(cleaned.get("is_superuser", False))

        # (Opcional) dejar superusers fuera del conteo (o cámbialo si quieres)
        if is_superuser:
            return cleaned

        admin_count = User.objects.filter(is_staff=True, is_superuser=False).count()
        normal_count = User.objects.filter(is_staff=False, is_superuser=False).count()

        if is_staff:
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

        return cleaned


# Si ya tienes User registrado en otro admin, elimina ese registro antes.
# Si te da error "AlreadyRegistered", quita esta parte o desregistra.
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = UserCreationAdminForm


# =========================================================
# PROJECT Admin (bloqueo por límite max_projects)
# =========================================================
class ProjectAdminForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()

        # Solo validar al crear
        if not self.instance.pk:
            check_projects_limit_or_raise(Project)

        return cleaned


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    form = ProjectAdminForm
    list_display = (
        "name",
        "budget",
        "start_date",
        "end_date",
        "remaining_budget",
        "progress_percent",
    )
    search_fields = ("name",)
    filter_horizontal = ("members",)


# =========================================================
# SPRINT
# =========================================================
@admin.register(Sprint)
class SprintAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "start_date", "end_date")
    search_fields = ("name",)
    list_filter = ("project",)


# =========================================================
# EPIC
# =========================================================
@admin.register(Epic)
class EpicAdmin(admin.ModelAdmin):
    list_display = ("name", "project")
    search_fields = ("name",)
    list_filter = ("project",)


# =========================================================
# SUBTASK INLINE (inside Task admin)
#   + bloqueo por límite de archivos si suben attachment
# =========================================================
class SubTaskInlineForm(forms.ModelForm):
    class Meta:
        model = SubTask
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()

        # Si están intentando subir un attachment en esta SubTask NUEVA,
        # revisa límite global de archivos
        attachment = cleaned.get("attachment")

        # Si es creación y trae archivo => validar cupo
        if not self.instance.pk and attachment:
            _check_files_limit_or_raise()

        return cleaned


class SubTaskInline(admin.TabularInline):
    model = SubTask
    form = SubTaskInlineForm
    extra = 0
    fields = (
        "title",
        "story_points",
        "budget",
        "status",
        "attachment",
        "created_at",
    )
    readonly_fields = ("created_at",)


# =========================================================
# TASK Admin (bloqueo por límite max_tasks)
# =========================================================
class TaskAdminForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()

        # Solo validar al crear
        if not self.instance.pk:
            check_tasks_limit_or_raise(Task)

        return cleaned


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    form = TaskAdminForm
    list_display = (
        "title",
        "project",
        "epic",
        "sprint",
        "status",
        "priority",
        "story_points",
        "budget",
        "remaining_budget",
        "progress_percent",
    )
    search_fields = ("title",)
    list_filter = ("project", "sprint", "priority", "status")
    filter_horizontal = ("responsibles",)
    inlines = [SubTaskInline]


# =========================================================
# SUBTASK Admin (bloqueo por límite de archivos al crear con attachment)
# =========================================================
class SubTaskAdminForm(forms.ModelForm):
    class Meta:
        model = SubTask
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()

        # Solo validar al crear
        if not self.instance.pk:
            attachment = cleaned.get("attachment")
            if attachment:
                _check_files_limit_or_raise()

        return cleaned


@admin.register(SubTask)
class SubTaskAdmin(admin.ModelAdmin):
    form = SubTaskAdminForm
    list_display = (
        "title",
        "task",
        "status",
        "story_points",
        "budget",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("title", "task__title")
    readonly_fields = ("created_at",)


# =========================================================
# DAILY
# =========================================================
@admin.register(Daily)
class DailyAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "within_time_range", "created_at")
    list_filter = ("date", "user")
    search_fields = ("user__username",)
    readonly_fields = ("created_at",)


# =========================================================
# AVAILABILITY
# =========================================================
@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "start_datetime", "end_datetime")
    list_filter = ("user",)
    search_fields = ("title", "user__username")
