"""URLs du module Finances."""

from django.urls import path

from . import views

app_name = "finances"

urlpatterns = [
    path("", views.impayes, name="impayes"),
    path("encaisser/", views.encaisser, name="encaisser"),
    path("compte/<int:inscription_pk>/", views.compte_eleve, name="compte_eleve"),
    path("relance/<int:inscription_pk>/", views.relance, name="relance"),
    path("recu/<int:pk>/", views.recu, name="recu"),
    path("compte/<int:inscription_pk>/facture/", views.emettre_facture, name="emettre_facture"),
    path("facture/<int:pk>/pdf/", views.facture_pdf, name="facture_pdf"),
    path("facture/<int:pk>/annuler/", views.annuler_facture_vue, name="annuler_facture"),
    path("paiement/<int:pk>/annuler/", views.annuler_paiement_vue, name="annuler_paiement"),
    path("remises/", views.remises, name="remises"),
    path("etats-caisse/", views.etats_caisse, name="etats_caisse"),
    path("etats-caisse/export/", views.export_caisse, name="export_caisse"),
]
