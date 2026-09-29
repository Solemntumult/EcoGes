"""URLs du module Comptes."""

from django.urls import path

from . import views

# NB : pas de namespace — ces vues sont incluses à la racine du projet
# (connexion, accueil...) et référencées par leur nom simple.

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("connexion/", views.connexion, name="connexion"),
    path("deconnexion/", views.deconnexion, name="deconnexion"),

    # Réinitialisation de mot de passe (UC-03)
    path("mot-de-passe/", views.ReinitialisationMotDePasseView.as_view(), name="mot_de_passe"),
    path("mot-de-passe/envoye/", views.MotDePasseEnvoyeView.as_view(), name="mot_de_passe_envoye"),
    path(
        "mot-de-passe/<uidb64>/<token>/",
        views.MotDePasseConfirmeView.as_view(),
        name="mot_de_passe_confirme",
    ),
    path("mot-de-passe/complet/", views.MotDePasseCompletView.as_view(), name="mot_de_passe_complet"),

    # Journal d'activité (UC-05)
    path("journal/", views.journal, name="journal"),

    # Utilisateurs (UC-01, UC-04)
    path("utilisateurs/", views.liste_utilisateurs, name="utilisateurs"),
    path("utilisateurs/creer/", views.creer_utilisateur, name="creer_utilisateur"),
    path("utilisateurs/<int:pk>/activer/", views.activer_desactiver_utilisateur, name="activer_utilisateur"),
]
