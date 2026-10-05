"""
Configuration Django du projet Gestion Scolaire.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Charge les variables du fichier .env (s'il existe) dans l'environnement.
# Les variables système déjà définies ne sont jamais écrasées.
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:  # python-dotenv optionnel en cas d'installation minimale
    pass


def env(key, default=None):
    return os.environ.get(key, default)


# SECURITY WARNING: garder la clé secrète... secrète en production !
SECRET_KEY = env("DJANGO_SECRET_KEY", "django-insecure-changeme-en-production")

DEBUG = env("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
for host in ("testserver", "localhost", "127.0.0.1", "web"):
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Apps métier du projet
    "comptes",
    "parametrage",
    "eleves",
    "personnel",
    "evaluations",
    "finances",
    "documents",
    "statistiques",
    "portail",

    # Nouveaux modules & services scolaires (Feuille de route Etat_amelioration.md)
    "viescolaire",
    "cahier_texte",
    "communication",
    "cantine",
    "sante",
    "transport",
    "bibliotheque",
    "admissions",

    # Tâches asynchrones (Celery)
    "django_celery_results",
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

ROOT_URLCONF = "gestion_scolaire.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Menu de navigation contextuel au rôle de l'utilisateur
                "comptes.context_processors.menu_app",
            ],
        },
    },
]

WSGI_APPLICATION = "gestion_scolaire.wsgi.application"


# ==============================================================================
# Base de données
# ==============================================================================

# --- Configuration active : PostgreSQL (Recommandée pour production & concurrence) ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", "gestion_scolaire"),
        "USER": env("DB_USER", "postgres"),
        "PASSWORD": env("DB_PASSWORD", "postgres"),
        "HOST": env("DB_HOST", "db"),
        "PORT": env("DB_PORT", "5432"),
    }
}

# --- Configuration MySQL (décommenter si vous utilisez MySQL / phpMyAdmin) ---
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.mysql",
#         "NAME": env("DB_NAME", "gestion_scolaire"),
#         "USER": env("DB_USER", "root"),
#         "PASSWORD": env("DB_PASSWORD", ""),
#         "HOST": env("DB_HOST", "127.0.0.1"),
#         "PORT": env("DB_PORT", "3306"),
#         "OPTIONS": {
#             "charset": "utf8mb4",
#         },
#     }
# }


# Modèle utilisateur personnalisé (voir comptes/models.py)
AUTH_USER_MODEL = "comptes.Utilisateur"


# Validation des mots de passe

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalisation

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Porto-Novo"
USE_I18N = True
USE_TZ = True


# Fichiers statiques et médias

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Authentification

LOGIN_URL = "connexion"
LOGIN_REDIRECT_URL = "accueil"
LOGOUT_REDIRECT_URL = "connexion"

# Verrouillage de compte après échecs répétés (voir comptes/views.py)
VERROUILLAGE_TENTATIVES = 5
VERROUILLAGE_DUREE_MINUTES = 30

# E-mail (réinitialisation de mot de passe, envoi de documents)
EMAIL_BACKEND = env("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("DJANGO_EMAIL_HOST", "")
EMAIL_PORT = int(env("DJANGO_EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("DJANGO_EMAIL_USER", "")
EMAIL_HOST_PASSWORD = env("DJANGO_EMAIL_PASSWORD", "")
EMAIL_USE_TLS = env("DJANGO_EMAIL_USE_TLS", "True") == "True"
DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL", "Gestion Scolaire <no-reply@exemple.com>")

# Documentations générées
DOCUMENTS_SEUIL_IMPACT = float(env("SEUIL_IMPAYE_BLOCAGE", "0"))

# Pages d'erreur personnalisées
handler403 = "gestion_scolaire.views.handler403"
handler404 = "gestion_scolaire.views.handler404"
handler500 = "gestion_scolaire.views.handler500"


# ==============================================================================
# Sécurité & Cookies (Best Practices django-security)
# ==============================================================================

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "SAMEORIGIN"  # Permet l'aperçu PDF dans l'application tout en bloquant le détournement
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

if not DEBUG:
    SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT", "True") == "True"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 an
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


# ==============================================================================
# Configuration Celery & Redis (Traitements asynchrones & files de tâches)
# ==============================================================================

CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", "django-db")
CELERY_CACHE_BACKEND = "django-cache"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60        # Limite stricte : 30 minutes (ex. génération massive de PDF)
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60   # Limite douce : 25 minutes
CELERY_WORKER_PREFETCH_MULTIPLIER = 1   # Évite la monopolisation des tâches longues par un seul worker
CELERY_TASK_ACKS_LATE = True            # Ré-achemine la tâche si le worker plante brutalement
CELERY_RESULT_EXPIRES = 60 * 60 * 24    # Conservation des résultats : 24 heures


