from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from comptes.mixins import roles_requis
from .models import Ouvrage, Emprunt

ROLES_BIBLIO = ["ADMIN", "SUPERADMIN", "SECRETARIAT", "ENSEIGNANT", "PARENT"]


@login_required
@roles_requis(ROLES_BIBLIO)
def catalogue(request):
    """Consultation du catalogue des ouvrages du CDI."""
    ouvrages = Ouvrage.objects.prefetch_related("exemplaires").all()
    q = request.GET.get("q")
    if q:
        ouvrages = ouvrages.filter(titre__icontains=q) | ouvrages.filter(auteur__icontains=q)
    total_ouvrages = Ouvrage.objects.count()
    emprunts_en_cours = Emprunt.objects.filter(date_retour_effective__isnull=True).count()

    return render(
        request,
        "bibliotheque/catalogue.html",
        {
            "ouvrages": ouvrages[:40],
            "total_ouvrages": total_ouvrages,
            "emprunts_en_cours": emprunts_en_cours,
            "q": q or "",
        },
    )
