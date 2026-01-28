from django.contrib.auth.models import AbstractUser

def is_admin(user: AbstractUser) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or user.groups.filter(name__in=["admin", "leader", "scrum"]).exists()
        )
    )
