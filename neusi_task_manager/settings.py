from __future__ import annotations

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY: str = "django-insecure-change-me-to-a-strong-secret-key"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG: bool = True

ALLOWED_HOSTS: list[str] = []

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core.apps.CoreConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "neusi_task_manager.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.notifications_context",

            ],
        },
    },
]

WSGI_APPLICATION = "neusi_task_manager.wsgi.application"

# Database
# https://docs.djangoproject.com/en/stable/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Password validation
# https://docs.djangoproject.com/en/stable/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# Internationalization
# https://docs.djangoproject.com/en/stable/topics/i18n/
LANGUAGE_CODE: str = "es"
TIME_ZONE: str = "America/Bogota"

USE_I18N: bool = True
USE_TZ: bool = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/stable/howto/static-files/
STATIC_URL: str = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Media files for uploaded attachments
MEDIA_URL: str = "/media/"
MEDIA_ROOT: Path = BASE_DIR / "media"

# Default primary key field type
# https://docs.djangoproject.com/en/stable/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Daily stand-up window (24-hour format). Entries outside this range are considered late.
DAILY_START_HOUR: int = 6  # 6 AM
DAILY_END_HOUR: int = 9    # 9 AM

# ============================
# Upload limits (FREE / safety)
# (valores típicos de app FREE para equipos pequeños)
# ============================

# 1) Límite por archivo (lo validarás en tu lógica de app/form)
FREE_MAX_FILE_SIZE_MB: int = 5  # 5MB por archivo (free típico)

# 2) Límite total de almacenamiento acumulado (app)
FREE_MAX_TOTAL_STORAGE_MB: int = 100  # 100MB total (free típico)

# 3) Límite del POST completo (protección a nivel Django)
# Recomendación: un poco mayor que el máximo archivo, por campos extra + overhead.
DATA_UPLOAD_MAX_MEMORY_SIZE: int = 12 * 1024 * 1024  # 12MB total por request

# 4) Umbral de memoria antes de spool a disco (no es el límite final)
FILE_UPLOAD_MAX_MEMORY_SIZE: int = 5 * 1024 * 1024  # 5MB

# 5) Extensiones permitidas (free)
# Nota: NO es seguridad real (eso es por validación y/o antivirus),
# pero te sirve para controlar tipos en UI/app.
ALLOWED_UPLOAD_EXTS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".doc",
    ".docx",
    ".xlsx",
    ".xls",
}
