#!/usr/bin/env python3
"""
Django's command-line utility for administrative tasks.

This script is used to manage and operate the NeusiTaskManager project.  It
acts as a thin wrapper around the Django management API and should be
invoked using the Python interpreter.  Before executing management
commands (such as runserver, migrate, or createsuperuser) you must
install the project's dependencies and activate a virtual environment.
"""
import os
import sys


def main() -> None:
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'neusi_task_manager.settings')
    try:
        from django.core.management import execute_from_command_line  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()