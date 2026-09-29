"""URLs du module Paramétrage."""

from django.urls import path

from . import views

app_name = "parametrage"

urlpatterns = [
    path("matieres/", views.matieres, name="matieres"),
    path("matieres/<int:pk>/tronc-commun/", views.basculer_tronc_commun, name="basculer_tronc_commun"),
    path("matieres/classe/<int:pk>/", views.classe_matieres, name="classe_matieres"),
    path("matieres/classe/<int:pk>/ajouter/", views.ajouter_matiere_classe, name="ajouter_matiere_classe"),
    path("matieres/classe/<int:pk>/<int:matiere_pk>/coefficient/", views.modifier_coefficient, name="modifier_coefficient"),
    path("matieres/classe/<int:pk>/<int:matiere_pk>/retirer/", views.retirer_matiere_classe, name="retirer_matiere_classe"),
    path("matieres/classe/<int:pk>/quotas/", views.quotas_horaires, name="quotas_horaires"),
    path("etablissement/", views.etablissement, name="etablissement"),
    path("horaires/", views.horaires, name="horaires"),
    path("horaires/creer/", views.horaire_editer, name="horaire_creer"),
    path("horaires/<int:pk>/editer/", views.horaire_editer, name="horaire_editer"),
    path("horaires/<int:pk>/supprimer/", views.horaire_supprimer, name="horaire_supprimer"),
]
