from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from comptes.mixins import roles_requis
from parametrage.models import Classe
from personnel.models import Affectation
from .models import SeanceCours, DevoirMaison

ROLES_CAHIER = ["ADMIN", "SUPERADMIN", "CENSEUR", "ENSEIGNANT", "SECRETARIAT", "PARENT"]


@login_required
@roles_requis(ROLES_CAHIER)
def index(request):
    """Consultation du cahier de textes avec sélection de la classe."""
    classes = Classe.objects.all().order_by("niveau", "libelle")
    classe_id = request.GET.get("classe")
    classe_selectionnee = None
    seances = []
    devoirs = []

    if classe_id:
        classe_selectionnee = get_object_or_404(Classe, pk=classe_id)
        seances = SeanceCours.objects.filter(
            affectation__classe=classe_selectionnee
        ).select_related("affectation__matiere", "affectation__enseignant")[:20]
        devoirs = DevoirMaison.objects.filter(
            affectation__classe=classe_selectionnee
        ).select_related("affectation__matiere")[:15]
    elif request.user.role == "ENSEIGNANT":
        # Pour un enseignant, afficher ses séances récentes
        seances = SeanceCours.objects.filter(
            affectation__enseignant__utilisateur=request.user
        ).select_related("affectation__classe", "affectation__matiere")[:20]
        devoirs = DevoirMaison.objects.filter(
            affectation__enseignant__utilisateur=request.user
        ).select_related("affectation__classe", "affectation__matiere")[:15]

    return render(
        request,
        "cahier_texte/index.html",
        {
            "classes": classes,
            "classe_selectionnee": classe_selectionnee,
            "seances": seances,
            "devoirs": devoirs,
        },
    )
