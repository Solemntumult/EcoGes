"""Services du module Comptes : journalisation, menus, groupes, redirections."""

from django.urls import NoReverseMatch, reverse

from .models import JournalActivite, Utilisateur


def journaliser(utilisateur, action, objet_concerne="", detail=""):
    """Trace une action sensible dans le JournalActivite (UC-05).

    Peut être appelé depuis n'importe quelle app. ``utilisateur`` peut être
    un objet User authentifié ou None (action anonyme).
    """
    if utilisateur is None or not getattr(utilisateur, "is_authenticated", False):
        return
    try:
        JournalActivite.objects.create(
            utilisateur=utilisateur,
            action=action,
            objet_concerne=objet_concerne[:255],
            detail=detail,
        )
    except Exception:
        # La journalisation ne doit jamais bloquer l'action métier.
        pass


# ---------------------------------------------------------------------------
# Menu de navigation contextuel au rôle
# ---------------------------------------------------------------------------

# Chaque entrée : (titre, icône Bootstrap, nom de vue, rôles autorisés)
_MENU = [
    ("Accueil", "house-door", "accueil", {"ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT", "COMPTABLE", "ENSEIGNANT"}),
    ("Élèves", "people", "eleves:liste", {"ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT"}),
    ("Personnel", "person-video3", "personnel:liste", {"ADMIN", "SUPERADMIN"}),
    ("Emploi du temps", "calendar-week", "personnel:edt_par_classe", {"ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT", "ENSEIGNANT"}),
    ("Horaires scolaires", "clock-history", "parametrage:horaires", {"ADMIN", "SUPERADMIN", "CENSEUR"}),
    ("Établissement", "building", "parametrage:etablissement", {"ADMIN", "SUPERADMIN"}),
    ("Matières & coefficients", "bookmark-star", "parametrage:matieres", {"ADMIN", "SUPERADMIN", "CENSEUR"}),
    ("Rémunérations", "cash-stack", "personnel:remunerations", {"ADMIN", "SUPERADMIN", "COMPTABLE"}),
    ("Évaluations", "clipboard-check", "evaluations:mes_evaluations", {"ADMIN", "SUPERADMIN", "CENSEUR", "ENSEIGNANT"}),
    ("Bulletins", "file-earmark-text", "evaluations:bulletins_classe", {"ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT"}),
    ("Finances", "cash-coin", "finances:impayes", {"ADMIN", "SUPERADMIN", "COMPTABLE"}),
    ("Documents", "files", "documents:accueil", {"ADMIN", "SUPERADMIN", "SECRETARIAT", "CENSEUR", "COMPTABLE"}),
    ("Éditeur de documents", "pencil-square", "documents:editeur", {"ADMIN", "SUPERADMIN", "SECRETARIAT", "CENSEUR", "COMPTABLE"}),
    ("Statistiques", "bar-chart", "statistiques:dashboard", {"ADMIN", "SUPERADMIN", "CENSEUR"}),
    ("Journal", "clock-history", "journal", {"ADMIN", "SUPERADMIN", "CENSEUR"}),
    ("Utilisateurs", "person-plus", "utilisateurs", {"ADMIN", "SUPERADMIN"}),
    ("Portail", "globe", "portail:accueil", {"PARENT"}),
]


def get_menu(utilisateur):
    """Retourne la liste des entrées de menu accessibles au rôle de l'utilisateur.

    Un superutilisateur Django voit l'intégralité du menu.
    """
    if utilisateur is None or not utilisateur.is_authenticated:
        return []
    entrees = []
    for titre, icone, url_name, roles in _MENU:
        if utilisateur.is_superuser or utilisateur.role in roles:
            try:
                entrees.append({"titre": titre, "icone": icone, "href": reverse(url_name)})
            except NoReverseMatch:
                continue
    if utilisateur.is_superuser or utilisateur.role in ("ADMIN", "SUPERADMIN"):
        entrees.append({"titre": "Administration Django", "icone": "gear", "href": "/admin/", "externe": True})
    return entrees


def redirection_apres_connexion(utilisateur):
    """URL d'accueil selon le rôle (UC-02)."""
    routes = {
        Utilisateur.Role.ADMIN: "accueil",
        Utilisateur.Role.SUPERADMIN: "accueil",
        Utilisateur.Role.CENSEUR: "accueil",
        Utilisateur.Role.SECRETARIAT: "eleves:liste",
        Utilisateur.Role.COMPTABLE: "finances:impayes",
        Utilisateur.Role.ENSEIGNANT: "evaluations:mes_evaluations",
        Utilisateur.Role.PARENT: "portail:accueil",
    }
    if utilisateur.is_superuser:
        return reverse("accueil")
    return reverse(routes.get(utilisateur.role, "accueil"))
