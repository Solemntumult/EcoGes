"""Services du module Personnel : conflits d'horaires, heures & rémunération."""

from datetime import date, datetime
from decimal import Decimal

from .models import Affectation, CreneauEmploiDuTemps

# Mois moyen : 52 semaines / 12 mois ≈ 4,33 semaines par mois.
FACTEUR_HEURES_MENSUEL = Decimal("4.33")


def _chevauche(a, b):
    """True si deux créneaux du même jour se chevauchent dans le temps."""
    return a.heure_debut < b.heure_fin and b.heure_debut < a.heure_fin


def verifier_conflits(creneau, exclure=None):
    """Retourne la liste des conflits d'horaires pour un créneau (UC-19).

    Conflits vérifiés : enseignant déjà occupé, classe déjà occupée,
    salle déjà utilisée (même jour, heures qui se chevauchent).

    ``exclure`` : ensemble de pk de créneaux à ignorer (ex. le créneau
    existant qu'une sauvegarde de grille s'apprête à remplacer).
    """
    conflits = []
    if creneau.pk:
        autres = CreneauEmploiDuTemps.objects.exclude(pk=creneau.pk)
    else:
        autres = CreneauEmploiDuTemps.objects.all()
    if exclure:
        autres = autres.exclude(pk__in=[pk for pk in exclure if pk])

    enseignant = autres.filter(
        affectation__personnel=creneau.affectation.personnel, jour=creneau.jour
    )
    for c in enseignant:
        if _chevauche(creneau, c):
            conflits.append(f"L'enseignant est déjà en cours : {c}")

    classe = autres.filter(
        affectation__classe=creneau.affectation.classe, jour=creneau.jour
    )
    for c in classe:
        if _chevauche(creneau, c):
            conflits.append(f"La classe a déjà un cours : {c}")

    if creneau.salle:
        salle = autres.filter(salle=creneau.salle, jour=creneau.jour)
        for c in salle:
            if _chevauche(creneau, c):
                conflits.append(f"La salle « {creneau.salle} » est déjà occupée : {c}")

    return conflits


# ---------------------------------------------------------------------------
# Heures de cours & rémunération des enseignants
# ---------------------------------------------------------------------------

def _duree_heures(creneau):
    """Durée d'un créneau en heures (Decimal, arrondi 0,01)."""
    debut = datetime.combine(date.min, creneau.heure_debut)
    fin = datetime.combine(date.min, creneau.heure_fin)
    return Decimal(str((fin - debut).total_seconds() / 3600)).quantize(Decimal("0.01"))


def heures_hebdo_affectation(affectation):
    """Total d'heures hebdomadaires couvertes par les créneaux d'une affectation."""
    return sum((_duree_heures(c) for c in affectation.creneaux.all()), Decimal("0"))


def detail_remuneration(enseignant, annee=None):
    """Heures hebdo et montants par affectation d'un enseignant (UC rémunération).

    Retourne : lignes (matière, classe, heures_hebdo, tarif_horaire,
    montant_hebdo), total_hebdo et montant_mensuel (≈ hebdo × 4,33).
    Seules les affectations ayant des heures de cours sont comptées.
    """
    if annee is None:
        from parametrage.models import AnneeScolaire
        annee = AnneeScolaire.objects.filter(est_courante=True).first()
    affectations = (
        Affectation.objects.filter(personnel=enseignant, annee_scolaire=annee)
        .select_related("matiere", "classe").prefetch_related("creneaux")
        if annee else Affectation.objects.none()
    )
    lignes = []
    for aff in affectations:
        heures = heures_hebdo_affectation(aff)
        if heures <= 0:
            continue  # pas d'heures planifiées → rien à rémunérer
        montant_hebdo = (heures * aff.tarif_horaire).quantize(Decimal("0.01"))
        lignes.append({
            "matiere": aff.matiere.libelle,
            "classe": aff.classe.libelle,
            "heures_hebdo": heures,
            "tarif_horaire": aff.tarif_horaire,
            "montant_hebdo": montant_hebdo,
        })
    total_hebdo = sum((ligne["heures_hebdo"] for ligne in lignes), Decimal("0")).quantize(Decimal("0.01"))
    montant_mensuel = sum(
        (ligne["montant_hebdo"] * FACTEUR_HEURES_MENSUEL for ligne in lignes), Decimal("0")
    ).quantize(Decimal("0.01"))
    return {"lignes": lignes, "total_hebdo": total_hebdo, "montant_mensuel": montant_mensuel}

def suivi_quotas(classe):
    """Retourne le suivi des quotas horaires pour chaque matière de la classe.

    Pour chaque matière ayant un quota défini ou des heures planifiées,
    retourne : matière, heures planifiées par semaine, quota, et statut.
    """
    from parametrage.models import Matiere, QuotaHoraireMatiere

    quotas = {
        q.matiere_id: q.heures_par_semaine
        for q in QuotaHoraireMatiere.objects.filter(classe=classe)
    }
    creneaux = CreneauEmploiDuTemps.objects.filter(
        affectation__classe=classe
    ).select_related("affectation__matiere")

    heures_par_matiere = {}
    for c in creneaux:
        mid = c.affectation.matiere_id
        heures_par_matiere[mid] = heures_par_matiere.get(mid, Decimal("0")) + _duree_heures(c)

    matieres_ids = set(quotas.keys()) | set(heures_par_matiere.keys())
    matieres = {m.pk: m for m in Matiere.objects.filter(pk__in=matieres_ids)}

    resultat = []
    for mid in sorted(matieres_ids, key=lambda m: getattr(matieres.get(m), "libelle", "")):
        mat = matieres.get(mid)
        if not mat:
            continue
        planifie = heures_par_matiere.get(mid, Decimal("0"))
        quota = quotas.get(mid)
        resultat.append({
            "matiere": mat.libelle,
            "heures_planifiees": planifie,
            "quota": quota,
            "atteint": quota is not None and planifie >= quota,
            "depasse": quota is not None and planifie > quota,
        })
    return resultat

def generer_emploi_du_temps_classe(classe):
    """Génère automatiquement l'emploi du temps pour une classe.
    
    L'algorithme découpe les quotas horaires en blocs de 3h maximum.
    Il cherche à placer ces blocs dans la grille en respectant les disponibilités
    du professeur et en évitant les chevauchements.
    """
    from parametrage.models import QuotaHoraireMatiere, HoraireJournalier
    from personnel.models import DisponibiliteEnseignant

    horaire = HoraireJournalier.obtenir_actif()
    if not horaire:
        return 0
        
    plages = horaire.plages_horaires()
    jours = ["LUN", "MAR", "MER", "JEU", "VEN"]

    # Nettoyage de la grille existante
    CreneauEmploiDuTemps.objects.filter(affectation__classe=classe).delete()

    quotas = QuotaHoraireMatiere.objects.filter(classe=classe)
    affectations = Affectation.objects.filter(classe=classe).select_related("personnel")
    aff_par_matiere = {a.matiere_id: a for a in affectations}
    
    blocs = []
    from parametrage.models import ClasseMatiereCoefficient
    coeffs = {
        c.matiere_id: float(c.coefficient)
        for c in ClasseMatiereCoefficient.objects.filter(classe=classe)
    }

    for quota in quotas:
        h_restantes = float(quota.heures_par_semaine)
        coef = coeffs.get(quota.matiere_id, 1.0)
        while h_restantes > 0:
            if h_restantes >= 4:
                blocs.append((quota.matiere_id, 2, coef))
                h_restantes -= 2
            elif h_restantes >= 3:
                blocs.append((quota.matiere_id, 3, coef))
                h_restantes -= 3
            else:
                blocs.append((quota.matiere_id, h_restantes, coef))
                h_restantes = 0
                
    # Tri: d'abord par coefficient (importance), puis par durée du bloc
    blocs.sort(key=lambda x: (x[2], x[1]), reverse=True)
    dispos = {}
    for a in affectations:
        dispos[a.personnel_id] = list(DisponibiliteEnseignant.objects.filter(
            personnel_id=a.personnel_id, annee_scolaire=a.annee_scolaire
        ))
        
    def _chevauche_temps(deb1, fin1, deb2, fin2):
        return deb1 < fin2 and deb2 < fin1
        
    def prof_est_dispo(prof_id, jour, heure_debut, heure_fin):
        if not dispos.get(prof_id):
            return True
        for d in dispos[prof_id]:
            if d.jour == jour and d.heure_debut <= heure_debut and d.heure_fin >= heure_fin:
                return True
        return False
        
    def prof_est_libre(prof_id, jour, heure_debut, heure_fin):
        for c in CreneauEmploiDuTemps.objects.filter(affectation__personnel_id=prof_id, jour=jour):
            if _chevauche_temps(heure_debut, heure_fin, c.heure_debut, c.heure_fin):
                return False
        return True

    def classe_est_libre(jour, heure_debut, heure_fin):
        for c in CreneauEmploiDuTemps.objects.filter(affectation__classe=classe, jour=jour):
            if _chevauche_temps(heure_debut, heure_fin, c.heure_debut, c.heure_fin):
                return False
        return True

    creneaux_crees = 0

    for matiere_id, duree_h, _ in blocs:
        aff = aff_par_matiere.get(matiere_id)
        if not aff:
            continue
            
        place_trouvee = False
        nb_creneaux = max(1, int((duree_h * 60) // horaire.duree_creneau_base))
        
        for jour in jours:
            if place_trouvee: break
            for idx in range(len(plages)):
                if idx + nb_creneaux > len(plages):
                    continue
                
                heure_debut = plages[idx][0]
                heure_fin = plages[idx + nb_creneaux - 1][1]
                
                traverse_pause = False
                for i in range(nb_creneaux - 1):
                    if plages[idx + i][1] != plages[idx + i + 1][0]:
                        traverse_pause = True
                        break
                
                if traverse_pause: continue
                if not prof_est_dispo(aff.personnel_id, jour, heure_debut, heure_fin): continue
                if not prof_est_libre(aff.personnel_id, jour, heure_debut, heure_fin): continue
                if not classe_est_libre(jour, heure_debut, heure_fin): continue
                
                CreneauEmploiDuTemps.objects.create(
                    affectation=aff, jour=jour,
                    heure_debut=heure_debut, heure_fin=heure_fin
                )
                creneaux_crees += 1
                place_trouvee = True
                break

    return creneaux_crees
