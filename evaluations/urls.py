"""URLs du module Évaluations."""

from django.urls import path

from . import views

app_name = "evaluations"

urlpatterns = [
    path("", views.mes_evaluations, name="mes_evaluations"),
    path("creer/", views.creer_evaluation, name="creer_evaluation"),
    path("classe/<int:pk>/", views.par_classe, name="par_classe"),
    path("<int:pk>/saisie/", views.saisie_notes, name="saisie_notes"),
    path("<int:pk>/verrouiller/", views.verrouiller, name="verrouiller"),
    path("carnet/classe/<int:pk>/", views.carnet_notes_classe, name="carnet_notes_classe"),
    path("carnet/classe/<int:pk>/ajouter-interrogation/", views.ajouter_interrogation_carnet, name="ajouter_interrogation_carnet"),
    path("carnet/interrogation/<int:pk>/supprimer/", views.supprimer_interrogation, name="supprimer_interrogation"),
    path("carnet/saisir/<int:pk>/", views.saisir_notes_classe, name="saisir_notes_classe"),
    path("carnet/valider-pp/<int:pk>/", views.valider_notes_pp, name="valider_notes_pp"),
    path("bulletins/", views.bulletins_classe, name="bulletins_classe"),
    path("bulletins/zip/", views.bulletins_zip, name="bulletins_zip"),
    path("bulletins/<int:pk>/telecharger/", views.telecharger_bulletin, name="telecharger_bulletin"),
    path("releve/<int:pk>/", views.releve_annuel, name="releve_annuel"),
    path("decisions/", views.decisions, name="decisions"),
]
