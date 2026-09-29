"""URLs du module Documents."""

from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("generer/", views.generer, name="generer"),
    path("editeur/", views.editeur, name="editeur"),
    path("exporter/", views.exporter, name="exporter"),
    path("eleve/<int:pk>/", views.pour_eleve, name="pour_eleve"),
    path("liste-classe/", views.liste_classe, name="liste_classe"),
    path("courrier/", views.courrier, name="courrier"),
    path("historique/", views.historique, name="historique"),
    path("envoyer/", views.envoyer_existant, name="envoyer_existant"),
]
