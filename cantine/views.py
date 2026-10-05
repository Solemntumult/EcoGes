from datetime import date
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from comptes.mixins import roles_requis
from .models import MenuSemaine, InscriptionCantine, PresenceRepas

ROLES_CANTINE = ["ADMIN", "SUPERADMIN", "RESPONSABLE_CANTINE", "SECRETARIAT", "PARENT"]


@login_required
@roles_requis(ROLES_CANTINE)
def menu_actuel(request):
    """Consultation du menu de la cantine pour la semaine en cours."""
    aujourdhui = date.today()
    menu = MenuSemaine.objects.filter(date_debut__lte=aujourdhui, date_fin__gte=aujourdhui).first()
    if not menu:
        menu = MenuSemaine.objects.first()
    inscrits_count = InscriptionCantine.objects.filter(actif=True).count()

    return render(
        request,
        "cantine/menu.html",
        {
            "menu": menu,
            "inscrits_count": inscrits_count,
            "aujourdhui": aujourdhui,
        },
    )
