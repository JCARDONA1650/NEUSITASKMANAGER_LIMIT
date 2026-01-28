from __future__ import annotations

from django.contrib.auth.decorators import user_passes_test  # type: ignore


def group_required(*group_names: str):
    """
    Restringe el acceso a usuarios en ciertos grupos.
    Superuser siempre pasa.
    """

    def in_groups(u):
        if not u.is_authenticated:
            return False
        if u.is_superuser:
            return True
        user_groups = u.groups.values_list("name", flat=True)
        return any(g in user_groups for g in group_names)

    return user_passes_test(in_groups)


def is_admin(user) -> bool:
    """
    Admin = pertenece a admin/leader/scrum o es superuser.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=["admin", "leader", "scrum"]).exists()
