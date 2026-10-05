from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from comptes.mixins import roles_requis
from .models import DemandeAdmission

ROLES_ADMISSIONS = ["ADMIN", "SUPERADMIN", "SECRETARIAT", "CENSEUR"]


@login_required
@roles_requis(ROLES_ADMISSIONS)
def liste_demandes(request):
    """Tableau de suivi des demandes de pré-inscription en ligne."""
    statut_filtre = request.GET.get("statut")
    demandes = DemandeAdmission.objects.select_related("niveau_souhaite", "annee_scolaire").all()
    if statut_filtre:
        demandes = demandes.filter(statut=statut_filtre)

    return render(
        request,
        "admissions/liste.html",
        {
            "demandes": demandes[:50],
            "statut_filtre": statut_filtre,
            "statuts": DemandeAdmission.Statut.choices,
        },
    )
