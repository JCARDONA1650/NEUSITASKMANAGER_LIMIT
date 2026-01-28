from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.views.permissions import group_required
from core.forms_users import UserCreateForm, UserUpdateForm, UserSetPasswordForm
from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser

User = get_user_model()


def _is_protected_user(u: AbstractBaseUser) -> bool:
    return bool(u.is_superuser)

@login_required
@group_required("admin", "leader", "scrum")
def user_list(request: HttpRequest) -> HttpResponse:
    users = User.objects.all().order_by("username")
    return render(request, "core/users/user_list.html", {"users": users})


@login_required
@group_required("admin", "leader", "scrum")
def user_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = UserCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuario creado correctamente.")
            return redirect("user_list")
    else:
        form = UserCreateForm()

    return render(request, "core/users/user_form.html", {"form": form, "edit": False})


@login_required
@group_required("admin", "leader", "scrum")
def user_update(request: HttpRequest, pk: int) -> HttpResponse:
    u = get_object_or_404(User, pk=pk)

    if u.is_superuser:
        messages.error(request, "Este usuario está protegido.")
        return redirect("user_list")

    if request.method == "POST":
        form = UserUpdateForm(request.POST, instance=u)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuario actualizado.")
            return redirect("user_list")
        else:
            # mensaje emergente claro (además del error en el form)
            messages.error(
                request,
                "No se pudo guardar. Si intentaste cambiar el rol, puede ser por cupo del plan FREE."
            )
    else:
        form = UserUpdateForm(instance=u)

    return render(request, "core/users/user_form.html", {"form": form, "edit": True, "obj": u})


@login_required
@group_required("admin", "leader", "scrum")
def user_set_password(request: HttpRequest, pk: int) -> HttpResponse:
    u = get_object_or_404(User, pk=pk)

    if u.is_superuser:
        messages.error(request, "Este usuario está protegido.")
        return redirect("user_list")

    if request.method == "POST":
        form = UserSetPasswordForm(u, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Contraseña actualizada.")
            return redirect("user_list")
    else:
        form = UserSetPasswordForm(u)

    return render(request, "core/users/user_password.html", {"form": form, "obj": u})


@login_required
@group_required("admin", "leader", "scrum")
def user_delete(request: HttpRequest, pk: int) -> HttpResponse:
    u = get_object_or_404(User, pk=pk)

    if u.pk == request.user.pk:
        messages.error(request, "No puedes eliminar tu propio usuario.")
        return redirect("user_list")

    if _is_protected_user(u):
        messages.error(request, "Este usuario está protegido.")
        return redirect("user_list")

    if request.method == "POST":
        username = u.username
        u.delete()
        messages.success(request, f"Usuario '{username}' eliminado.")
        return redirect("user_list")

    return render(request, "core/users/user_confirm_delete.html", {"obj": u})
