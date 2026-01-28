"""
Custom template filters for working with user roles and groups.

The ``has_group`` filter returns a boolean indicating whether a user
belongs to the specified group.  Usage in templates:

    {% if user|has_group:'admin' %}
        <!-- content for admins -->
    {% endif %}

Note that superusers implicitly have all groups.
"""
from __future__ import annotations

from django import template  # type: ignore

register = template.Library()


@register.filter(name='has_group')
def has_group(user, group_name: str) -> bool:
    """Return True if the given user belongs to the specified group."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=group_name).exists()