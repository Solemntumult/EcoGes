from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from comptes.mixins import roles_requis
from .models import PassageInfirmerie, FicheMedicale

ROLES_SANTE = ["ADMIN", "SUPERADMIN", "INFIRMIER", "CENSEUR", "SECRETARIAT"]


@login_required
@roles_requis(ROLES_SANTE)
def registre(request):
    """Registre des passages récents à l'infirmerie."""
    passages = PassageInfirmerie.objects.select_related("eleve", "enregistre_par")[:30]
    total_visites = PassageInfirmerie.objects.count()
    return render(
        request,
        "sante/registre.html",
        {
            "passages": passages,
            "total_visites": total_visites,
        },
    )
