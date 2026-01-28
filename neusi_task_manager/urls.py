
from __future__ import annotations

from django.conf import settings  # type: ignore
from django.conf.urls.static import static  # type: ignore
from django.contrib import admin  # type: ignore
from django.urls import include, path  # type: ignore
from django.contrib.auth import views as auth_views  # type: ignore
from core.views.auth_views import login_view, logout_view


urlpatterns = [
    path('admin/', admin.site.urls),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path('', include('core.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)