"""URLs du module Portail."""

from django.urls import path

from . import views

app_name = "portail"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("eleve/<int:eleve_pk>/", views.dossier, name="dossier"),
    path("document/<int:doc_pk>/", views.document, name="document"),
]
