from __future__ import annotations

from django.contrib import messages  # type: ignore
from django.contrib.auth import authenticate, login, logout, get_user_model  # type: ignore
from django.contrib.auth.decorators import login_required  # type: ignore
from django.contrib.auth.models import Group  # type: ignore
from django.http import HttpRequest, HttpResponse  # type: ignore
from django.shortcuts import redirect, render  # type: ignore

from core.views.permissions import is_admin

User = get_user_model()

# PlanLimits (si existe)
try:
    from core.models import PlanLimits, check_user_limits_or_raise
except Exception:  # pragma: no cover
    PlanLimits = None  # type: ignore
    check_user_limits_or_raise = None  # type: ignore


def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""

        user = authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, "Usuario o contraseña incorrectos.")
            return render(request, "login.html")

        login(request, user)
        return redirect("/")

    return render(request, "login.html")


@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("/login/")


@login_required
def user_register_admin(request: HttpRequest) -> HttpResponse:
    """
    Pantalla para que un ADMIN cree usuarios.
    Esta es tu "Registrarse", pero controlada (no self-signup).
    """
    if not is_admin(request.user):
        messages.error(request, "No tienes permisos para crear usuarios.")
        return redirect("/")

    # Roles permitidos (por grupos)
    role_choices = [
        ("user", "Usuario normal"),
        ("scrum", "Scrum"),
        ("leader", "Leader"),
        ("admin", "Admin"),
    ]

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password1 = request.POST.get("password1") or ""
        password2 = request.POST.get("password2") or ""
        role = request.POST.get("role") or "user"

        if not username:
            messages.error(request, "El usuario es requerido.")
            return render(request, "core/register.html", {"role_choices": role_choices})

        if password1 != password2:
            messages.error(request, "Las contraseñas no coinciden.")
            return render(request, "core/register.html", {"role_choices": role_choices})

        if User.objects.filter(username=username).exists():
            messages.error(request, "Ese usuario ya existe.")
            return render(request, "core/register.html", {"role_choices": role_choices})

        # Validar límites (FREE)
        # admin/leader/scrum cuentan como admin-tier
        is_admin_tier = role in {"admin", "leader", "scrum"}
        if check_user_limits_or_raise is not None:
            try:
                check_user_limits_or_raise("admin" if is_admin_tier else "normal")
            except Exception as e:
                messages.error(request, str(e))
                return render(request, "core/register.html", {"role_choices": role_choices})

        # Crear usuario
        new_user = User.objects.create_user(username=username, password=password1)

        # Asegurar grupos existen
        for gname in ["admin", "leader", "scrum", "user"]:
            Group.objects.get_or_create(name=gname)

        # asignar grupo
        new_user.groups.clear()
        new_user.groups.add(Group.objects.get(name=role if role in {"admin", "leader", "scrum"} else "user"))

        # is_staff solo para admin-tier (si quieres que entren /admin)
        new_user.is_staff = bool(is_admin_tier)
        new_user.save(update_fields=["is_staff"])

        messages.success(request, f"Usuario '{username}' creado como {role}.")
        return redirect("/")

    return render(request, "core/register.html", {"role_choices": role_choices})
