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

ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")


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


# Base de données — MySQL (administrable via phpMyAdmin)
# Toutes les valeurs sont surchargeables par variables d'environnement (voir .env.example)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("DB_NAME", "gestion_scolaire"),
        "USER": env("DB_USER", "root"),
        "PASSWORD": env("DB_PASSWORD", ""),
        "HOST": env("DB_HOST", "127.0.0.1"),
        "PORT": env("DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    }
}

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
