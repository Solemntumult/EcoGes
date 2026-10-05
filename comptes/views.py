"""Vues du module Comptes : authentification, tableau de bord, journal, utilisateurs."""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import CreationUtilisateurForm
from .mixins import roles_requis
from .models import JournalActivite, Utilisateur
from .services import journaliser, redirection_apres_connexion

from parametrage.models import AnneeScolaire, Classe


# ---------------------------------------------------------------------------
# Authentification (UC-02, UC-03)
# ---------------------------------------------------------------------------

def connexion(request):
    """Connexion personnalisée avec verrouillage de compte après échecs répétés."""
    if request.user.is_authenticated:
        return redirect(redirection_apres_connexion(request.user))

    # Page demandée avant connexion (?next=) — redirigée après succès si sûre
    next_url = request.POST.get("next") or request.GET.get("next") or ""

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        utilisateur = Utilisateur.objects.filter(username=username).first()
        if utilisateur and utilisateur.est_bloque:
            messages.error(
                request,
                f"Ce compte est verrouillé jusqu'au "
                f"{utilisateur.bloque_jusqua:%d/%m/%Y à %H:%M}. Contactez l'administrateur.",
            )
        elif utilisateur is not None and not utilisateur.actif:
            messages.error(request, "Ce compte est désactivé. Contactez l'administrateur.")
        else:
            identifie = authenticate(request, username=username, password=password)
            if identifie is not None:
                Utilisateur.objects.filter(pk=identifie.pk).update(tentatives_connexion=0)
                login(request, identifie)
                journaliser(identifie, "Connexion", "Compte", f"Connexion réussie ({identifie.get_role_display()})")
                messages.success(request, f"Bienvenue, {identifie.get_full_name() or identifie.username} !")
                if next_url and url_has_allowed_host_and_scheme(
                    next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
                ):
                    return redirect(next_url)
                return redirect(redirection_apres_connexion(identifie))

            # Échec : comptabilisation des tentatives
            if utilisateur is not None:
                utilisateur.tentatives_connexion += 1
                restantes = settings.VERROUILLAGE_TENTATIVES - utilisateur.tentatives_connexion
                if restantes <= 0:
                    utilisateur.bloque_jusqua = timezone.now() + timedelta(
                        minutes=settings.VERROUILLAGE_DUREE_MINUTES
                    )
                    utilisateur.tentatives_connexion = 0
                    utilisateur.save(update_fields=["bloque_jusqua", "tentatives_connexion"])
                    journaliser(
                        utilisateur, "Verrouillage de compte",
                        "Compte",
                        f"Compte verrouillé {settings.VERROUILLAGE_DUREE_MINUTES} min après échecs répétés.",
                    )
                    messages.error(
                        request,
                        f"Trop de tentatives échouées. Compte verrouillé pour "
                        f"{settings.VERROUILLAGE_DUREE_MINUTES} minutes.",
                    )
                else:
                    utilisateur.save(update_fields=["tentatives_connexion"])
                    messages.error(request, f"Identifiants invalides. Il reste {restantes} tentative(s).")
            else:
                messages.error(request, "Identifiants invalides.")

    return render(request, "registration/login.html", {"next": next_url})


@require_POST
@login_required
def deconnexion(request):
    journaliser(request.user, "Déconnexion", "Compte")
    logout(request)
    return redirect("connexion")


# ---------------------------------------------------------------------------
# Tableau de bord d'accueil (par rôle)
# ---------------------------------------------------------------------------

@login_required
def accueil(request):
    """Tableau de bord différencié selon le rôle de l'utilisateur."""
    from django.db.models import Count
    from eleves.models import Eleve, Inscription
    from evaluations.models import Bulletin
    from finances.models import Echeance, ImputationPaiement, Paiement
    from viescolaire.models import Appel
    from admissions.models import DemandeAdmission

    role = request.user.role
    annee_courante = AnneeScolaire.objects.filter(est_courante=True).first()
    aujourdhui = timezone.localdate()
    contexte = {
        "annee_courante": annee_courante,
        "aujourdhui": aujourdhui,
    }

    if role in ("ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT", "SURVEILLANT", "COMPTABLE"):
        contexte["effectifs_actifs"] = Eleve.objects.filter(statut="ACTIF").count()
        contexte["nb_classes"] = (
            Classe.objects.filter(annee_scolaire=annee_courante).count() if annee_courante else 0
        )
        contexte["nb_inscriptions"] = (
            Inscription.objects.filter(annee_scolaire=annee_courante, statut="ACTIVE").count()
            if annee_courante else 0
        )
        contexte["absents_jour"] = Appel.objects.filter(date=aujourdhui, statut="ABSENT").count()
        contexte["retards_jour"] = Appel.objects.filter(date=aujourdhui, statut="RETARD").count()
        contexte["admissions_attente"] = DemandeAdmission.objects.filter(statut__in=["RECUE", "EN_EXAMEN"]).count()

        # Liste des classes avec effectifs
        classes_qs = Classe.objects.filter(annee_scolaire=annee_courante).select_related("niveau") if annee_courante else Classe.objects.none()
        classes_apercu = list(classes_qs.annotate(
            nb_eleves=Count("inscriptions", filter=Q(inscriptions__statut="ACTIVE"))
        ).order_by("niveau__ordre", "libelle")[:8])
        contexte["classes_apercu"] = classes_apercu
        contexte["chart_classes_labels"] = [c.libelle for c in classes_apercu]
        contexte["chart_classes_data"] = [c.nb_eleves for c in classes_apercu]

        # Activité récente
        contexte["dernieres_activites"] = JournalActivite.objects.select_related("utilisateur").order_by("-date_heure")[:6]

    if role in ("ADMIN", "SUPERADMIN", "CENSEUR", "COMPTABLE"):
        total_du = Echeance.objects.aggregate(total=Sum("montant_du"))["total"] or Decimal("0")
        total_paye = ImputationPaiement.objects.aggregate(total=Sum("montant_impute"))["total"] or Decimal("0")
        reste_du = total_du - total_paye
        taux_recouvrement = round((total_paye / total_du) * 100, 1) if total_du else Decimal("0")
        contexte["total_du"] = total_du
        contexte["total_paye"] = total_paye
        contexte["reste_du"] = reste_du
        contexte["taux_recouvrement"] = taux_recouvrement
        contexte["nb_impayes"] = Echeance.objects.exclude(statut="PAYE").count()
        contexte["encaissements_jour"] = (
            Paiement.objects.filter(date_paiement__date=aujourdhui, statut="VALIDE")
            .aggregate(total=Sum("montant"))["total"] or Decimal("0")
        )
        contexte["derniers_paiements"] = (
            Paiement.objects.filter(statut="VALIDE")
            .select_related("inscription__eleve", "inscription__classe")
            .order_by("-date_paiement")[:5]
        )

    if role == "ENSEIGNANT":
        personnel = getattr(request.user, "fiche_personnel", None)
        if personnel is not None:
            affectations = personnel.affectations.all()
            if annee_courante:
                affectations = affectations.filter(annee_scolaire=annee_courante)
            contexte["mes_classes"] = Classe.objects.filter(
                id__in=affectations.values_list("classe_id", flat=True)
            ).distinct()
            contexte["nb_affectations"] = affectations.count()

    if role in ("ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT"):
        contexte["nb_bulletins"] = Bulletin.objects.filter(est_annuel=False).count()

    return render(request, "comptes/dashboard.html", contexte)


# ---------------------------------------------------------------------------
# Gestion des utilisateurs (UC-01)
# ---------------------------------------------------------------------------

@login_required
@roles_requis(["ADMIN", "SUPERADMIN"])
def liste_utilisateurs(request):
    qs = Utilisateur.objects.all().order_by("username")
    requete = request.GET.get("q", "").strip()
    role = request.GET.get("role", "")
    if requete:
        qs = qs.filter(
            Q(username__icontains=requete)
            | Q(first_name__icontains=requete)
            | Q(last_name__icontains=requete)
            | Q(email__icontains=requete)
        )
    if role:
        qs = qs.filter(role=role)
    paginator = Paginator(qs, 25)
    contexte = {
        "utilisateurs": paginator.get_page(request.GET.get("page")),
        "roles": Utilisateur.Role.choices,
        "requete": requete,
        "role_filtre": role,
    }
    return render(request, "comptes/utilisateurs.html", contexte)


@login_required
@roles_requis(["ADMIN", "SUPERADMIN"])
def creer_utilisateur(request):
    if request.method == "POST":
        form = CreationUtilisateurForm(request.POST)
        if form.is_valid():
            utilisateur = form.save()
            # Rattachement au groupe correspondant au rôle (UC-04), si créé
            nom_groupe = {
                "ADMIN": "Administration",
                "SUPERADMIN": "Super administration",
                "CENSEUR": "Censeurs",
                "SECRETARIAT": "Secrétariat",
                "COMPTABLE": "Comptabilité",
                "ENSEIGNANT": "Enseignants",
                "PARENT": "Parents",
            }.get(utilisateur.role)
            if nom_groupe:
                from django.contrib.auth.models import Group
                groupe = Group.objects.filter(name=nom_groupe).first()
                if groupe:
                    utilisateur.groups.add(groupe)
            journaliser(
                request.user, "Création de compte", "Utilisateur",
                f"Compte « {utilisateur.username} » créé avec le rôle {utilisateur.get_role_display()}.",
            )
            messages.success(request, f"Compte « {utilisateur.username} » créé avec succès.")
            return redirect("utilisateurs")
    else:
        form = CreationUtilisateurForm()
    return render(request, "comptes/utilisateur_form.html", {"form": form})


@login_required
@roles_requis(["ADMIN", "SUPERADMIN"])
def activer_desactiver_utilisateur(request, pk):
    utilisateur = get_object_or_404(Utilisateur, pk=pk)
    if utilisateur == request.user:
        messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
        return redirect("utilisateurs")
    # Bascule simultanée de `actif` (interface métier) et `is_active` (Django/admin)
    utilisateur.actif = not utilisateur.actif
    utilisateur.is_active = utilisateur.actif
    utilisateur.save(update_fields=["actif", "is_active"])
    journaliser(request.user, "Modification de compte", "Utilisateur",
                f"Compte « {utilisateur.username} » {'activé' if utilisateur.actif else 'désactivé'}.")
    messages.success(request, "Statut du compte mis à jour.")
    return redirect("utilisateurs")


# ---------------------------------------------------------------------------
# Journal d'activité (UC-05)
# ---------------------------------------------------------------------------

@login_required
@roles_requis(["ADMIN", "SUPERADMIN", "CENSEUR"])
def journal(request):
    qs = JournalActivite.objects.select_related("utilisateur").all()
    utilisateur = request.GET.get("utilisateur", "").strip()
    action = request.GET.get("action", "").strip()
    date_debut = request.GET.get("date_debut", "").strip()
    date_fin = request.GET.get("date_fin", "").strip()

    if utilisateur:
        qs = qs.filter(
            Q(utilisateur__username__icontains=utilisateur)
            | Q(utilisateur__first_name__icontains=utilisateur)
            | Q(utilisateur__last_name__icontains=utilisateur)
        )
    if action:
        qs = qs.filter(Q(action__icontains=action) | Q(objet_concerne__icontains=action))
    if date_debut:
        qs = qs.filter(date_heure__date__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_heure__date__lte=date_fin)

    paginator = Paginator(qs, 50)
    contexte = {
        "entrees": paginator.get_page(request.GET.get("page")),
        "utilisateur": utilisateur,
        "action": action,
        "date_debut": date_debut,
        "date_fin": date_fin,
    }
    return render(request, "comptes/journal.html", contexte)


# ---------------------------------------------------------------------------
# Réinitialisation de mot de passe (UC-03) — gabarits Django personnalisés
# ---------------------------------------------------------------------------

class ReinitialisationMotDePasseView(PasswordResetView):
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("mot_de_passe_envoye")
    from_email = settings.DEFAULT_FROM_EMAIL


class MotDePasseEnvoyeView(PasswordResetDoneView):
    template_name = "registration/password_reset_done.html"


class MotDePasseConfirmeView(PasswordResetConfirmView):
    template_name = "registration/password_reset_confirm.html"
    success_url = reverse_lazy("mot_de_passe_complet")


class MotDePasseCompletView(PasswordResetCompleteView):
    template_name = "registration/password_reset_complete.html"
