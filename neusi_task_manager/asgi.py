"""
ASGI config for NeusiTaskManager project.

It exposes the ASGI callable as a module-level variable named
``application``.  Django uses this module to instantiate the
application when running under ASGI servers such as Daphne or Uvicorn.
"""
import os

from django.core.asgi import get_asgi_application  # type: ignore


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'neusi_task_manager.settings')

# Obtain the ASGI application.  This will raise an exception if Django
# cannot be configured.  It is executed once at module import time.
application = get_asgi_application()