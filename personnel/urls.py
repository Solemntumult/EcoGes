"""URLs du module Personnel."""

from django.urls import path

from . import views

app_name = "personnel"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("creer/", views.fiche, name="creer"),
    path("affectations/", views.affectations, name="affectations"),
    path("<int:pk>/disponibilites/", views.disponibilites, name="disponibilites"),
    path("affectations/<int:pk>/supprimer/", views.supprimer_affectation, name="supprimer_affectation"),
    path("emploi-du-temps/", views.edt_par_classe, name="edt_par_classe"),
    path("emploi-du-temps/classe/<int:pk>/", views.edt_classe, name="edt_classe"),
    path("emploi-du-temps/classe/<int:pk>/generer/", views.generer_edt, name="generer_edt"),
    path("emploi-du-temps/classe/<int:pk>/envoyer/", views.envoyer_edt, name="envoyer_edt"),
    path("emploi-du-temps/enseignant/", views.edt_enseignant, name="edt_enseignant"),
    path("emploi-du-temps/creer/", views.creer_creneau, name="creer_creneau"),
    path("emploi-du-temps/<int:pk>/modifier/", views.modifier_creneau, name="modifier_creneau"),
    path("emploi-du-temps/<int:pk>/supprimer/", views.supprimer_creneau, name="supprimer_creneau"),
    path("emploi-du-temps/api/affectations/", views.api_recherche_affectations, name="api_recherche_affectations"),
    path("remunerations/", views.remunerations, name="remunerations"),
    path("remunerations/fiche-paie/<int:pk>/", views.fiche_paie, name="fiche_paie"),
    path("remunerations/fiche-paie/<int:pk>/pdf/", views.fiche_paie_pdf, name="fiche_paie_pdf"),
    path("remunerations/fiche-paie/<int:pk>/payer/", views.fiche_paie_payer, name="fiche_paie_payer"),
    path("remunerations/fiche-paie/<int:pk>/annuler/", views.fiche_paie_annuler, name="fiche_paie_annuler"),
]
