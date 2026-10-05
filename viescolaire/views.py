from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from comptes.mixins import roles_requis
from eleves.models import Inscription
from parametrage.models import AnneeScolaire, Classe
from .models import Appel, IncidentDisciplinaire, JustificatifAbsence, Sanction, StatutPresence

ROLES_VIE_SCOLAIRE = ["ADMIN", "SUPERADMIN", "CENSEUR", "SURVEILLANT", "SECRETARIAT", "ENSEIGNANT"]


@login_required
@roles_requis(ROLES_VIE_SCOLAIRE)
def tableau_bord(request):
    """Tableau de bord de la vie scolaire : assiduité du jour et alertes."""
    aujourdhui = date.today()
    appels_jour = Appel.objects.filter(date=aujourdhui)
    total_absents = appels_jour.filter(statut=StatutPresence.ABSENT, justifie=False).count()
    total_retards = appels_jour.filter(statut=StatutPresence.RETARD).count()
    total_justifies = appels_jour.filter(justifie=True).count()
    incidents_recents = IncidentDisciplinaire.objects.select_related("eleve", "signale_par")[:10]
    classes = Classe.objects.all().order_by("niveau", "libelle")

    return render(
        request,
        "viescolaire/tableau_bord.html",
        {
            "aujourdhui": aujourdhui,
            "total_absents": total_absents,
            "total_retards": total_retards,
            "total_justifies": total_justifies,
            "incidents_recents": incidents_recents,
            "classes": classes,
        },
    )


@login_required
@roles_requis(ROLES_VIE_SCOLAIRE)
def feuille_appel(request, classe_id):
    """Feuille d'appel numérique pour une classe à une date donnée."""
    classe = get_object_or_404(Classe, pk=classe_id)
    date_str = request.GET.get("date")
    date_appel = date.fromisoformat(date_str) if date_str else date.today()
    creneau = request.GET.get("creneau", "Matin")

    annee_active = AnneeScolaire.objects.filter(active=True).first()
    inscriptions = Inscription.objects.filter(
        classe=classe, annee_scolaire=annee_active, statut=Inscription.StatutActivite.ACTIVE
    ).select_related("eleve").order_by("eleve__nom", "eleve__prenoms")

    # Charger les appels existants
    appels_existants = {
        a.inscription_id: a
        for a in Appel.objects.filter(inscription__in=inscriptions, date=date_appel, creneau=creneau)
    }

    lignes = []
    for ins in inscriptions:
        lignes.append({
            "inscription": ins,
            "appel": appels_existants.get(ins.id),
        })

    return render(
        request,
        "viescolaire/feuille_appel.html",
        {
            "classe": classe,
            "date_appel": date_appel,
            "creneau": creneau,
            "lignes": lignes,
            "statuts": StatutPresence.choices,
        },
    )


@login_required
@roles_requis(ROLES_VIE_SCOLAIRE)
def pointer_presence(request, inscription_id):
    """Enregistre ou met à jour la présence d'un élève (compatible HTMX)."""
    if request.method != "POST":
        return HttpResponse("Méthode non autorisée", status=405)

    inscription = get_object_or_404(Inscription, pk=inscription_id)
    statut = request.POST.get("statut", StatutPresence.PRESENT)
    date_str = request.POST.get("date")
    creneau = request.POST.get("creneau", "Matin")
    date_appel = date.fromisoformat(date_str) if date_str else date.today()

    appel, _ = Appel.objects.update_or_create(
        inscription=inscription,
        date=date_appel,
        creneau=creneau,
        defaults={
            "statut": statut,
            "enregistre_par": request.user,
        },
    )

    if request.headers.get("HX-Request"):
        badge_cls = {
            StatutPresence.PRESENT: "success",
            StatutPresence.ABSENT: "danger",
            StatutPresence.RETARD: "warning",
            StatutPresence.INFIRMERIE: "info",
        }.get(statut, "secondary")
        return HttpResponse(f'<span class="badge bg-{badge_cls}">{appel.get_statut_display()}</span>')

    messages.success(request, f"Présence mise à jour pour {inscription.eleve}.")
    return redirect("viescolaire:feuille_appel", classe_id=inscription.classe_id)
