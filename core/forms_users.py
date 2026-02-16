from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser
from .models import PlanLimits

User = get_user_model()

ROLE_CHOICES = (
    ("normal", "Usuario (Normal)"),
    ("scrum", "Scrum"),
    ("leader", "Leader"),
    ("admin", "Admin"),
)

ROLE_GROUPS = {"admin", "leader", "scrum"}  # roles “elevados”


def _current_role(u: AbstractUser) -> str:
    """
    Rol actual según grupos.
    - normal = no pertenece a admin/leader/scrum
    - scrum/leader/admin = según grupo
    """
    if getattr(u, "is_superuser", False):
        return "admin"

    groups = set(u.groups.values_list("name", flat=True))
    for r in ("admin", "leader", "scrum"):
        if r in groups:
            return r
    return "normal"


def _counts(exclude_user_id: int | None = None) -> tuple[int, int]:
    """
    Cuenta usuarios para límites FREE.
    - admin_like: is_staff=True y no superuser
    - normal: is_staff=False y no superuser
    exclude_user_id: para edición (excluir el usuario editado del conteo)
    """
    qs_admin = User.objects.filter(is_staff=True, is_superuser=False)
    qs_norm = User.objects.filter(is_staff=False, is_superuser=False)

    if exclude_user_id:
        qs_admin = qs_admin.exclude(id=exclude_user_id)
        qs_norm = qs_norm.exclude(id=exclude_user_id)

    return qs_admin.count(), qs_norm.count()


def _apply_role_to_user(user: AbstractUser, role: str) -> None:
    """
    Aplica rol:
    - normal => is_staff False, sin grupos elevados
    - admin/leader/scrum => is_staff True, asigna grupo correspondiente
    """
    user.is_staff = role in ROLE_GROUPS
    user.is_superuser = False  # por seguridad: esto no se maneja aquí

    # limpiar grupos elevados previos
    user.groups.remove(*user.groups.filter(name__in=["admin", "leader", "scrum"]))

    # asignar grupo nuevo si aplica
    if role in ROLE_GROUPS:
        grp, _ = Group.objects.get_or_create(name=role)
        user.groups.add(grp)


class UserCreateForm(forms.ModelForm):
    """
    Crea usuario y define rol.
    """
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True, label="Rol")
    password1 = forms.CharField(widget=forms.PasswordInput, label="Contraseña")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirmar contraseña")

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise ValidationError("El usuario es obligatorio.")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Ese username ya existe.")
        return username

    def clean(self):
        cleaned = super().clean()

        p1 = cleaned.get("password1") or ""
        p2 = cleaned.get("password2") or ""
        if p1 != p2:
            raise ValidationError("Las contraseñas no coinciden.")

        role = cleaned.get("role") or "normal"
        wants_admin_like = role in ROLE_GROUPS

        limits = PlanLimits.get_solo()
        admin_count, normal_count = _counts()

        if wants_admin_like:
            if admin_count >= limits.max_admin_users:
                raise ValidationError(
                    "No se puede crear el usuario con ese rol porque el plan FREE ya alcanzó "
                    "el límite de usuarios ADMIN/LEADER/SCRUM. Contacte con su proveedor para cambiar el plan."
                )
        else:
            if normal_count >= limits.max_normal_users:
                raise ValidationError(
                    "No se puede crear el usuario porque el plan FREE ya alcanzó el límite de usuarios normales. "
                    "Contacte con su proveedor para cambiar el plan."
                )

        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])

        role = self.cleaned_data["role"]

        if commit:
            user.save()  # 👈 PRIMERO GUARDAR
            _apply_role_to_user(user, role)  # 👈 DESPUÉS tocar groups

        return user



class UserUpdateForm(forms.ModelForm):
    """
    Edita datos básicos + permite cambiar rol con validación de cupos.
    Superuser protegido.
    """
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True, label="Rol")

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.fields["role"].initial = _current_role(self.instance)

        # Superuser: bloquear UI
        if self.instance and self.instance.pk and self.instance.is_superuser:
            for f in self.fields.values():
                f.disabled = True

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise ValidationError("El usuario es obligatorio.")
        qs = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Ese username ya existe.")
        return username

    def clean(self):
        cleaned = super().clean()

        if not self.instance or not self.instance.pk:
            return cleaned

        if self.instance.is_superuser:
            raise ValidationError("Este usuario está protegido. No se permite editar un SUPERUSER desde esta pantalla.")

        new_role = cleaned.get("role") or "normal"
        old_role = _current_role(self.instance)

        # si no cambió rol, no valida cupos
        if new_role == old_role:
            return cleaned

        limits = PlanLimits.get_solo()
        admin_count, normal_count = _counts(exclude_user_id=self.instance.id)

        new_admin_like = new_role in ROLE_GROUPS
        old_admin_like = old_role in ROLE_GROUPS

        # normal -> admin/leader/scrum
        if new_admin_like and not old_admin_like:
            if admin_count >= limits.max_admin_users:
                raise ValidationError(
                    "No se puede cambiar el rol porque el plan FREE ya alcanzó el límite de usuarios ADMIN. "
                    "Contacte con su proveedor de software para cambiar el plan."
                )

        # admin/leader/scrum -> normal (por consistencia)
        if (not new_admin_like) and old_admin_like:
            if normal_count >= limits.max_normal_users:
                raise ValidationError(
                    "No se puede cambiar el rol a NORMAL porque el plan FREE ya alcanzó el límite de usuarios normales. "
                    "Contacte con su proveedor de software para cambiar el plan."
                )

        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        role = self.cleaned_data.get("role") or "normal"

        if commit:
            user.save()                 # 👈 ya tiene ID
            _apply_role_to_user(user, role)  # 👈 ahora sí puede tocar groups

        return user


class UserSetPasswordForm(SetPasswordForm):
    """
    Reseteo de contraseña (asignar nueva).
    Usa validaciones de Django.
    """
    pass
