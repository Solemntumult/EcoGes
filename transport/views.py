from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from comptes.mixins import roles_requis
from .models import LigneTransport, InscriptionTransport

ROLES_TRANSPORT = ["ADMIN", "SUPERADMIN", "SECRETARIAT", "PARENT"]


@login_required
@roles_requis(ROLES_TRANSPORT)
def liste_lignes(request):
    """Consultation des circuits et lignes de bus."""
    lignes = LigneTransport.objects.prefetch_related("arrets").filter(actif=True)
    total_inscrits = InscriptionTransport.objects.filter(actif=True).count()
    return render(
        request,
        "transport/lignes.html",
        {
            "lignes": lignes,
            "total_inscrits": total_inscrits,
        },
    )
