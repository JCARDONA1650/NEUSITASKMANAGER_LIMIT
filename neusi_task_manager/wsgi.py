"""
WSGI config for NeusiTaskManager project.

This module exposes the WSGI callable ``application`` for use by
WSGI servers such as Gunicorn or uWSGI.  See
https://docs.djangoproject.com/en/stable/howto/deployment/wsgi/ for
details.
"""
import os

from django.core.wsgi import get_wsgi_application  # type: ignore


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'neusi_task_manager.settings')

application = get_wsgi_application()