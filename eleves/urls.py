"""URLs du module Élèves."""

from django.urls import path

from . import views

app_name = "eleves"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("creer/", views.creation, name="creation"),
    path("reinscription/", views.reinscription_masse, name="reinscription"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/modifier/", views.modifier, name="modifier"),
    path("<int:pk>/transferer/", views.transferer, name="transferer"),
    path("<int:pk>/carte-scolaire/", views.carte_scolaire, name="carte_scolaire"),
]
