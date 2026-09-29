"""Commande : jeu de données de démonstration complet.

Usage :
    python manage.py creer_demo                  # ajoute les données manquantes
    python manage.py creer_demo --reset          # vide tout puis reconstruit
    python manage.py creer_demo --eleves 8       # 8 élèves par classe

Peuple le paramétrage (année scolaire, périodes, niveaux, classes, matières,
grille tarifaire, barème), des comptes de démonstration, le personnel et les
affectations, des élèves avec tuteurs et échéanciers, des évaluations/notes
avec bulletins, et des paiements variés (payés, partiels, impayés).

Réutilise les services métier (generer_echeancier, imputer_paiement,
generer_bulletin...) pour que les données soient cohérentes avec l'application.
"""

import random
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from comptes.models import JournalActivite, Utilisateur
from parametrage.models import (
    AnneeScolaire, BaremeEvaluation, Classe, ClasseMatiereCoefficient,
    Etablissement, GrilleTarifaire, HoraireJournalier, LogoEtablissement,
    Matiere, Niveau, PauseHoraire, Periode, Serie, TypeFrais,
)
from personnel.models import Affectation, CreneauEmploiDuTemps, Personnel
from eleves.models import Eleve, Inscription, Tuteur
from evaluations.models import Bulletin, Evaluation, Note, NoteModification
from finances.models import Echeance, Facture, FicheDePaie, ImputationPaiement, Paiement, Recu, Remise
from finances.services import (
    creer_fiche_paie, generer_echeancier, generer_facture, generer_recu, imputer_paiement,
)
from evaluations.services import generer_bulletin

# Tarif horaire (F / heure) par matière, appliqué aux affectations de démonstration
TARIFS_HORAIRES = {
    "Mathématiques": Decimal("4000"),
    "Physique-Chimie": Decimal("4000"),
    "Français": Decimal("3500"),
    "Histoire-Géographie": Decimal("3500"),
    "Anglais": Decimal("3000"),
    "SVT": Decimal("3000"),
}

ANNEE_LIBELLE = "2026-2027"
DATE_DEBUT = date(2026, 9, 1)
DATE_FIN = date(2027, 7, 31)

PERIODES = [
    ("1er trimestre", date(2026, 9, 1), date(2026, 11, 30)),
    ("2e trimestre", date(2026, 12, 1), date(2027, 2, 28)),
    ("3e trimestre", date(2027, 3, 1), date(2027, 5, 31)),
]

NIVEAUX = [
    ("6ème", Niveau.Cycle.COLLEGE, 1),
    ("5ème", Niveau.Cycle.COLLEGE, 2),
    ("4ème", Niveau.Cycle.COLLEGE, 3),
    ("3ème", Niveau.Cycle.COLLEGE, 4),
    ("2nde", Niveau.Cycle.LYCEE, 5),
    ("1ère", Niveau.Cycle.LYCEE, 6),
    ("Terminale", Niveau.Cycle.LYCEE, 7),
]

# Séries officielles du second cycle au Bénin (seule la série D est utilisée
# par les classes de démonstration, mais toute la liste est disponible).
SERIES = [
    ("A1", "Lettres-Langues"),
    ("A2", "Lettres-Sciences Humaines"),
    ("B", "Lettres-Sciences Sociales"),
    ("C", "Sciences et Techniques (Maths-Physique)"),
    ("D", "Biologie-Géologie"),
    ("E", "Mathématiques et Techniques"),
    ("F1", "Construction Mécanique"),
    ("F2", "Électronique"),
    ("F3", "Électrotechnique"),
    ("F4", "Génie Civil"),
    ("G1", "Techniques Administratives"),
    ("G2", "Techniques Quantitatives de Gestion"),
    ("G3", "Techniques Commerciales"),
    ("EA", "Eau et Assainissement"),
]

CLASSES = ["6ème A", "6ème B", "5ème A", "4ème A", "3ème A", "2nde D", "1ère D", "Terminale D"]

# (matière, coefficient) — appliqué à tous les niveaux, adapté selon le niveau
MATIERES = [
    ("Mathématiques", Decimal("3")),
    ("Français", Decimal("2")),
    ("Anglais", Decimal("1")),
    ("Histoire-Géographie", Decimal("2")),
    ("SVT", Decimal("1")),
]
MATIERES_AVANCEES = MATIERES + [("Physique-Chimie", Decimal("2"))]

TYPES_FRAIS = ["Inscription", "Scolarité", "Examen", "Tenue"]
GRILLE = {"Inscription": Decimal("15000"), "Scolarité": Decimal("60000"),
          "Examen": Decimal("5000"), "Tenue": Decimal("10000")}

ENSAIGNANTS = [
    ("HOUNSOU", "Koffi", ["Mathématiques", "Physique-Chimie"]),
    ("ADJAKOSSA", "Mireille", ["Français", "Histoire-Géographie"]),
    ("SOSSOU", "Boris", ["Anglais", "SVT"]),
]

NOMS = ["AGOSSOU", "HOUESSOU", "DOSSOU", "ADJOVI", "GBAGUIDI", "YEHOUENOU",
        "ZINSOU", "AKPAKI", "BOKO", "TONAKPON", "AZONHIHO", "KPONOU",
        "OLOULINDE", "SAGBO", "TOKPONTO"]
PRENOMS = ["Jean-Marc", "Aïcha", "Sèna", "Grâce", "Rachida", "Marcellin",
           "Estelle", "Félicien", "Naomie", "Bénédicte", "Arnaud", "Cédric",
           "Mariam", "Idrissou", "Chantal"]

PREFIXE = "[creer_demo]"


def _png_octets(dessin, taille=240):
    """Génère une petite image PNG (Pillow) pour les logos/avatars de démo."""
    from io import BytesIO
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (taille, taille), "#ffffff")
    dessin(ImageDraw.Draw(img), taille)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _dessiner_logo_republique(d, taille):
    """Drapeau du Bénin (bande verte + jaune/rouge) en guise de logo d'État."""
    d.rectangle((0, 0, int(taille * 0.4), taille), fill="#008751")
    d.rectangle((int(taille * 0.4), 0, taille, int(taille * 0.5)), fill="#FCD116")
    d.rectangle((int(taille * 0.4), int(taille * 0.5), taille, taille), fill="#E8112D")


def _dessiner_logo_college(d, taille):
    """Emblème simple : anneaux bleus, pour le logo de l'établissement."""
    m = int(taille * 0.05)
    d.ellipse((m, m, taille - m, taille - m), fill="#1d4ed8")
    m2 = int(taille * 0.22)
    d.ellipse((m2, m2, taille - m2, taille - m2), fill="#ffffff")
    m3 = int(taille * 0.33)
    d.ellipse((m3, m3, taille - m3, taille - m3), fill="#1d4ed8")


def _dessiner_avatar(d, taille, sexe):
    """Avatar silhouette d'élève (photo de démonstration)."""
    d.rectangle((0, 0, taille, taille), fill="#c7d2fe" if sexe == "M" else "#fbcfe8")
    teinte = "#4f46e5" if sexe == "M" else "#db2777"
    tete = int(taille * 0.2)
    d.ellipse((tete, int(taille * 0.08), taille - tete, int(taille * 0.45)), fill=teinte)
    d.ellipse((int(taille * 0.05), int(taille * 0.5), int(taille * 0.95), int(taille * 1.15)), fill=teinte)

MOIS_NOMS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
             "août", "septembre", "octobre", "novembre", "décembre"]


def mois_nom(m):
    return MOIS_NOMS[m - 1] if 1 <= m <= 12 else str(m)


class Command(BaseCommand):
    help = "Crée un jeu de données de démonstration complet."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Supprime toutes les données existantes avant de reconstruire (destructif !).",
        )
        parser.add_argument(
            "--yes", action="store_true",
            help="Confirme l'action destructrice --reset sans question interactive.",
        )
        parser.add_argument(
            "--eleves", type=int, default=6,
            help="Nombre d'élèves par classe (défaut : 6).",
        )

    # ------------------------------------------------------------------ #

    def handle(self, *args, **options):
        self.rng = random.Random(42)  # données reproductibles
        self.nb_eleves = options["eleves"]

        if options["reset"]:
            if not options["yes"]:
                # Confirmation interactive ; hors terminal (scripts, CI), on refuse
                reponse = ""
                try:
                    if sys.stdin.isatty():
                        reponse = input(
                            "⚠️  --reset supprimera TOUTES les données actuelles. "
                            "Continuer ? [o/N] "
                        ).strip().lower()
                except (EOFError, OSError):
                    reponse = ""
                if reponse not in ("o", "oui", "y", "yes"):
                    raise CommandError(
                        "Annulé — aucune donnée supprimée. "
                        "Pour un usage non interactif, ajoutez --yes."
                    )
            self.stdout.write(self.style.WARNING(
                PREFIXE + " Purge des données existantes..."
            ))
            self._purge()

        annee, creee = AnneeScolaire.objects.get_or_create(
            libelle=ANNEE_LIBELLE,
            defaults={"date_debut": DATE_DEBUT, "date_fin": DATE_FIN, "est_courante": True},
        )
        if creee:
            annee.est_courante = True
            annee.save(update_fields=["est_courante"])
        self.annee = annee

        # S'il existe déjà des données (année non re-paramétrée), on ne duplique pas.
        if Eleve.objects.exists() and not options["reset"]:
            self.stdout.write(self.style.WARNING(
                f"{PREFIXE} Des données existent déjà. Utilisez --reset pour "
                "tout reconstruire, ou lancez sur une base vide."
            ))
            return

        self._parametrage()
        self._comptes()
        self._personnel()
        self._eleves()
        self._evaluations()
        self._finances()
        self._paie()
        self._documents()
        self._journal()
        self._recap()

    # ------------------------------------------------------------------ #
    # Purge (ordre respectant les contraintes PROTECT / CASCADE)
    # ------------------------------------------------------------------ #

    def _purge(self):
        self.stdout.write(PREFIXE + " Purge des données existantes...")
        for modele in (NoteModification, Note, Bulletin, Evaluation,
                       CreneauEmploiDuTemps, FicheDePaie, ImputationPaiement, Recu,
                       Facture, Paiement, Remise, Echeance, Inscription,
                       Tuteur, Eleve, Affectation, Personnel,
                       ClasseMatiereCoefficient, Classe, Matiere,
                       Periode, GrilleTarifaire, BaremeEvaluation, Niveau,
                       TypeFrais, PauseHoraire, HoraireJournalier,
                       Etablissement, AnneeScolaire, Serie):
            modele.objects.all().delete()
        from documents.models import DocumentAdministratif
        DocumentAdministratif.objects.all().delete()

    # ------------------------------------------------------------------ #
    # Paramétrage
    # ------------------------------------------------------------------ #

    def _parametrage(self):
        bareme, _ = BaremeEvaluation.objects.get_or_create(annee_scolaire=self.annee)
        bareme.save()

        for ordre, (libelle, debut, fin) in enumerate(PERIODES, start=1):
            Periode.objects.get_or_create(
                annee_scolaire=self.annee, ordre=ordre,
                defaults={"libelle": libelle, "date_debut": debut, "date_fin": fin},
            )
        self.periodes = {p.ordre: p for p in self.annee.periodes.all()}

        self.niveaux = {}
        for libelle, cycle, ordre in NIVEAUX:
            niveau, _ = Niveau.objects.get_or_create(
                libelle=libelle, defaults={"cycle": cycle, "ordre": ordre}
            )
            self.niveaux[libelle] = niveau

        # Classes rattachées à l'année courante
        self.classes = []
        for libelle_classe in CLASSES:
            niveau = self.niveaux[libelle_classe.split(" ")[0]]
            classe, _ = Classe.objects.get_or_create(
                niveau=niveau, annee_scolaire=self.annee, libelle=libelle_classe,
                defaults={"effectif_max": 50},
            )
            self.classes.append(classe)

        # Matières par niveau (aucun coefficient stocké sur la matière —
        # le coefficient appartient au couple (matière, classe)).
        # Toutes les matières de démo sont du tronc commun : le signal
        # post_save les lie automatiquement aux classes du niveau.
        self.matieres = {}
        for niveau in self.niveaux.values():
            for libelle, _coefficient in MATIERES_AVANCEES:
                matiere, _ = Matiere.objects.get_or_create(
                    libelle=libelle, niveau=niveau,
                )
                if not matiere.tronc_commun:
                    matiere.tronc_commun = True
                    matiere.save(update_fields=["tronc_commun"])
                self.matieres.setdefault(niveau.libelle, []).append(matiere)

        # Séries officielles du second cycle
        self.series = {}
        for code, libelle in SERIES:
            serie, _ = Serie.objects.get_or_create(code=code, defaults={"libelle": libelle})
            self.series[code] = serie
        # Attribution de la série D aux niveaux du second cycle
        serie_d = self.series["D"]
        for libelle_niveau in ("2nde", "1ère", "Terminale"):
            Niveau.objects.filter(libelle=libelle_niveau).update(serie=serie_d)

        # Coefficients (matière, classe) — la source unique de vérité des bulletins.
        # Les liaisons ont déjà été créées par le signal tronc commun : on
        # positionne explicitement le coefficient voulu pour la démonstration.
        coef_par_libelle = dict(MATIERES_AVANCEES)
        for classe in self.classes:
            for matiere in self.matieres[classe.niveau.libelle]:
                cmc, _ = ClasseMatiereCoefficient.objects.get_or_create(
                    classe=classe, matiere=matiere,
                )
                coef = coef_par_libelle.get(matiere.libelle, Decimal("1"))
                if cmc.coefficient != coef:
                    cmc.coefficient = coef
                    cmc.save(update_fields=["coefficient"])

        # Types de frais + grille tarifaire
        self.types_frais = {}
        for libelle in TYPES_FRAIS:
            tf, _ = TypeFrais.objects.get_or_create(libelle=libelle)
            self.types_frais[libelle] = tf
        for niveau in self.niveaux.values():
            for libelle, montant in GRILLE.items():
                GrilleTarifaire.objects.get_or_create(
                    niveau=niveau, annee_scolaire=self.annee,
                    type_frais=self.types_frais[libelle],
                    defaults={"montant": montant},
                )

        # Modes d'horaire (journée continue actif, journée coupée en réserve)
        horaire_continu, _ = HoraireJournalier.objects.get_or_create(
            libelle="Journée continue (07:00–15:35)",
            defaults={"actif": True,
                      "heure_debut_journee": time(7, 0),
                      "heure_fin_journee": time(15, 35)},
        )
        horaire_coupe, _ = HoraireJournalier.objects.get_or_create(
            libelle="Journée coupée (07:30–18:30)",
            defaults={"actif": False,
                      "heure_debut_journee": time(7, 30),
                      "heure_fin_journee": time(18, 30)},
        )
        pauses = [
            (horaire_continu, "Récréation", time(10, 0), time(10, 15)),
            (horaire_continu, "Pause déjeuner", time(12, 0), time(13, 0)),
            (horaire_coupe, "Récréation", time(10, 0), time(10, 15)),
            (horaire_coupe, "Pause déjeuner", time(12, 30), time(15, 0)),
        ]
        for horaire, libelle, debut, fin in pauses:
            PauseHoraire.objects.get_or_create(
                horaire=horaire, libelle=libelle,
                defaults={"heure_debut": debut, "heure_fin": fin},
            )

        # Établissement — identité affichée sur tous les documents PDF
        Etablissement.objects.get_or_create(
            pk=1,
            defaults={
                "nom_officiel": "Complexe Scolaire La Réussite",
                "sigle": "CSR",
                "devise": "Savoir · Excellence · Discipline",
                "adresse": "Rue 128, Fidjrossè",
                "ville": "Cotonou",
                "commune": "Cotonou",
                "pays": "Bénin",
                "boite_postale": "BP 2468 Cotonou",
                "telephone": "+229 21 30 45 67",
                "email": "contact@csreussite.bj",
                "site_web": "www.csreussite.bj",
                "statut_juridique": Etablissement.StatutJuridique.PRIVE_LAIC,
                "categorie": Etablissement.Categorie.COMPLEXE,
                "ministere_tutelle": ("Ministère des Enseignements Secondaire, Technique "
                                       "et de la Formation Professionnelle"),
                "numero_arrete": "N° 2024/089/MESTFP/DEPES-COT",
                "date_arrete": date(2024, 8, 12),
                "code_etablissement": "CE-0423",
                "annee_creation": 2012,
                "fondateur": "M. Frédéric AKPAKI",
                "ifu": "4202301234567",
                "rccm": "RB/COT/22 B 12345",
                "nom_directeur": "M. Frédéric AKPAKI",
                "nom_censeur": "Mme Bernadette HOUESSOU",
                "nom_comptable": "M. Romaric TOSSOU",
                "mentions_legales": ("Document émis par le Complexe Scolaire La Réussite — "
                                      "toute falsification est punie par la loi."),
                "regime_fiscal": "Exonération de TVA (Code Général des Impôts)",
                "formule_certification": ("Nous, soussignés, certifions que l'élève ci-dessous "
                                           "désigné est régulièrement inscrit dans notre établissement."),
            },
        )

        # Logos multiples (État + collège) — générés en PNG pour la démo
        from django.core.files.base import ContentFile
        etab = Etablissement.obtenir()
        if not etab.logos.exists():
            for ordre, (libelle, dessin) in enumerate((
                ("Logo de la République du Bénin", _dessiner_logo_republique),
                ("Logo du Complexe Scolaire La Réussite", _dessiner_logo_college),
            ), start=1):
                logo = LogoEtablissement.objects.create(
                    etablissement=etab, libelle=libelle, ordre=ordre, en_tete=True
                )
                logo.image.save(
                    f"logo_demo_{ordre}.png", ContentFile(_png_octets(dessin)), save=True
                )

        self.stdout.write(self.style.SUCCESS(
            f"{PREFIXE} Paramétrage : {len(self.classes)} classes, "
            f"{len(self.matieres) * len(MATIERES_AVANCEES)} matières, "
            f"{len(GRILLE)} types de frais, {etab.logos.count()} logos."
        ))

    # ------------------------------------------------------------------ #
    # Comptes de démonstration
    # ------------------------------------------------------------------ #

    def _creer_utilisateur(self, username, password, role, email="", nom="", prenoms=""):
        user, _ = Utilisateur.objects.get_or_create(
            username=username,
            defaults={"role": role, "email": email,
                      "first_name": prenoms, "last_name": nom},
        )
        user.role = role
        if email:
            user.email = email
        user.actif = True
        user.is_active = True
        user.set_password(password)
        user.save()
        return user

    def _comptes(self):
        self.users = {
            "censeur": self._creer_utilisateur("censeur", "censeur123!", "CENSEUR",
                                               nom="Direction", prenoms="des études"),
            "secre": self._creer_utilisateur("secre", "secre123!", "SECRETARIAT",
                                             email="secretariat@exemple.com",
                                             nom="Secrétariat", prenoms="Service"),
            "caisse": self._creer_utilisateur("caisse", "caisse123!", "COMPTABLE",
                                              email="comptabilite@exemple.com",
                                              nom="Comptabilité", prenoms="Service"),
            "prof": self._creer_utilisateur("prof", "prof123!", "ENSEIGNANT",
                                            email="prof@exemple.com",
                                            nom="Koffi", prenoms="HOUNSOU"),
        }
        self.stdout.write(self.style.SUCCESS(
            f"{PREFIXE} Comptes : censeur/censeur123!, secre/secre123!, "
            "caisse/caisse123!, prof/prof123! (admin existant conservé)"
        ))

    # ------------------------------------------------------------------ #
    # Personnel & affectations
    # ------------------------------------------------------------------ #

    def _personnel(self):
        self.enseignants = []
        for nom, prenoms, matieres in ENSAIGNANTS:
            pers, _ = Personnel.objects.get_or_create(
                nom=nom, prenoms=prenoms,
                defaults={"fonction": Personnel.Fonction.ENSEIGNANT,
                          "qualification": "Licence",
                          "telephone": "+22990" + str(self.rng.randint(100000, 999999)),
                          "email": f"{nom.lower()}@exemple.com",
                          "date_embauche": date(2019, 9, 1)},
            )
            self.enseignants.append(pers)

        # Personnel administratif lié aux comptes
        self.pers_censeur, _ = Personnel.objects.get_or_create(
            nom="Direction", prenoms="des études",
            defaults={"fonction": Personnel.Fonction.CENSEUR, "utilisateur": self.users["censeur"]},
        )
        self.pers_secretaire, _ = Personnel.objects.get_or_create(
            nom="Secrétariat", prenoms="Service",
            defaults={"fonction": Personnel.Fonction.SECRETAIRE, "utilisateur": self.users["secre"]},
        )
        self.pers_comptable, _ = Personnel.objects.get_or_create(
            nom="Comptabilité", prenoms="Service",
            defaults={"fonction": Personnel.Fonction.COMPTABLE, "utilisateur": self.users["caisse"]},
        )

        # L'enseignant 1 est aussi lié au compte « prof »
        self.enseignants[0].utilisateur = self.users["prof"]
        self.enseignants[0].save(update_fields=["utilisateur"])

        # Affectations enseignant ↔ classe/matière + créneaux d'emploi du temps
        self.affectations = []
        jours = ["LUN", "MAR", "MER", "JEU", "VEN"]
        # Créneaux alignés sur les plages de l'horaire actif (continue 7h–15h35)
        horaire_actif = HoraireJournalier.obtenir_actif()
        segments = horaire_actif.segments() if horaire_actif else []
        # Chaque enseignant a 5 jours × (jusqu'à 3) plages : on attribue une
        # plage unique par affectation → aucun conflit d'horaires entre ses cours.
        nb_plages = min(3, len(segments)) if segments else 0
        slots_libres = {
            p.pk: {(jour, t) for jour in jours for t in range(nb_plages)} for p in self.enseignants
        }
        for classe in self.classes:
            for matiere in self.matieres[classe.niveau.libelle]:
                enseignant = self._enseignant_pour(matiere)
                affectation, _ = Affectation.objects.get_or_create(
                    personnel=enseignant, classe=classe, matiere=matiere,
                    annee_scolaire=self.annee,
                )
                affectation.tarif_horaire = TARIFS_HORAIRES.get(matiere.libelle, Decimal("3000"))
                affectation.save(update_fields=["tarif_horaire"])
                self.affectations.append(affectation)
                matiere.enseignants.add(enseignant)
                # Plage libre pour cet enseignant (aucun conflit entre ses cours)
                if not segments:
                    continue
                libres = slots_libres[enseignant.pk]
                if not libres:
                    continue
                jour, t = sorted(libres)[0]
                libres.discard((jour, t))
                debut, fin = segments[t]
                CreneauEmploiDuTemps.objects.get_or_create(
                    affectation=affectation, jour=jour, heure_debut=debut,
                    defaults={"heure_fin": fin, "salle": f"Salle {jours.index(jour) * nb_plages + t + 1}"},
                )

        self.stdout.write(self.style.SUCCESS(
            f"{PREFIXE} Personnel : {len(self.enseignants)} enseignants, "
            f"{len(self.affectations)} affectations (tarifs horaires posés), "
            "emploi du temps généré (sans conflit)."
        ))

    def _enseignant_pour(self, matiere):
        """Retourne l'enseignant référent de la matière."""
        libelle = str(matiere)
        if "Mathématiques" in libelle or "Physique" in libelle:
            return self.enseignants[0]
        if "Français" in libelle or "Histoire" in libelle:
            return self.enseignants[1]
        return self.enseignants[2]

    # ------------------------------------------------------------------ #
    # Élèves, tuteurs, inscriptions, échéanciers
    # ------------------------------------------------------------------ #

    def _eleves(self):
        self.inscriptions = []
        for classe in self.classes:
            for i in range(self.nb_eleves):
                nom = self.rng.choice(NOMS)
                prenoms = self.rng.choice(PRENOMS)
                sexe = "M" if self.rng.random() > 0.45 else "F"
                eleve = Eleve.objects.create(
                    nom=nom, prenoms=prenoms,
                    sexe=sexe,
                    date_naissance=date(2011, self.rng.randint(1, 12), self.rng.randint(1, 28)),
                    lieu_naissance=self.rng.choice(["Cotonou", "Porto-Novo", "Parakou",
                                                    "Abomey-Calavi", "Ouidah", "Lokossa"]),
                    adresse=f"Quartier {self.rng.choice(['Fidjrossè', 'Cadjehoun', 'Akpakpa'])}",
                    regime=self.rng.choice([Eleve.Regime.EXTERNE, Eleve.Regime.DEMI_PENSIONNAIRE,
                                            Eleve.Regime.INTERNE]),
                )
                # Photo de démonstration (avatar silhouette)
                from django.core.files.base import ContentFile
                eleve.photo.save(
                    f"demo_{eleve.matricule}.png",
                    ContentFile(_png_octets(lambda d, t: _dessiner_avatar(d, t, sexe))),
                    save=True,
                )
                statut_inscription = self.rng.choice(
                    [Inscription.StatutInscription.NOUVEAU,
                     Inscription.StatutInscription.ANCIEN,
                     Inscription.StatutInscription.REDOUBLANT]
                )
                inscription = Inscription.objects.create(
                    eleve=eleve, classe=classe, annee_scolaire=self.annee,
                    statut_inscription=statut_inscription,
                )
                # Date d'inscription passée pour un échéancier réaliste
                # (refresh nécessaire : auto_now_add laisserait la date du jour)
                Inscription.objects.filter(pk=inscription.pk).update(
                    date_inscription=date(2026, 9, 15)
                )
                inscription.refresh_from_db(fields=["date_inscription"])
                self._creer_tuteur(eleve)
                generer_echeancier(inscription, nb_versements=2)
                self.inscriptions.append(inscription)

        self.stdout.write(self.style.SUCCESS(
            f"{PREFIXE} Élèves : {Eleve.objects.count()} inscrits "
            f"({len(self.inscriptions)} inscriptions, échéanciers générés)."
        ))

    def _creer_tuteur(self, eleve):
        lien = Tuteur.LienParente.MERE if eleve.sexe == "F" else Tuteur.LienParente.PERE
        email = f"{eleve.nom.lower()}.{eleve.prenoms.split()[0].lower()}@exemple.com"
        Tuteur.objects.create(
            eleve=eleve,
            nom_complet=f"Mme {eleve.nom}" if lien == Tuteur.LienParente.MERE else f"M. {eleve.nom}",
            lien_parente=lien,
            telephone="+22997" + str(self.rng.randint(1000000, 9999999)),
            email=email,
            adresse=eleve.adresse,
            contact_urgence=True,
        )

    # ------------------------------------------------------------------ #
    # Évaluations, notes, bulletins
    # ------------------------------------------------------------------ #

    def _evaluations(self):
        n_notes = 0
        for classe in self.classes:
            inscriptions = list(classe.inscriptions.filter(statut="ACTIVE"))
            for matiere in self.matieres[classe.niveau.libelle]:
                affectation = Affectation.objects.filter(
                    classe=classe, matiere=matiere, annee_scolaire=self.annee
                ).first()
                for ordre, periode in self.periodes.items():
                    for type_eval, coef, decalage in (
                        ("DEVOIR", Decimal("1"), 20),
                        ("COMPOSITION", Decimal("2"), 45),
                    ):
                        evaluation = Evaluation.objects.create(
                            matiere=matiere, classe=classe, periode=periode,
                            type_evaluation=type_eval, coefficient=coef,
                            date=periode.date_debut + timedelta(days=decalage),
                        )
                        for inscription in inscriptions:
                            Note.objects.create(
                                evaluation=evaluation, inscription=inscription,
                                valeur=Decimal(self.rng.choice(
                                    [5.0, 6.5, 8.0, 9.5, 10.5, 11.5, 12.5, 13.5,
                                     14.5, 15.5, 16.5, 17.5, 18.5]
                                )),
                                saisi_par=affectation.personnel if affectation else None,
                            )
                            n_notes += 1

        # Bulletins (périodes + annuel) via le moteur de calcul métier
        n_bulletins = 0
        for inscription in self.inscriptions:
            for ordre in self.periodes:
                if generer_bulletin(inscription, periode=self.periodes[ordre]) is not None:
                    n_bulletins += 1
            if generer_bulletin(inscription, est_annuel=True) is not None:
                n_bulletins += 1

        self.stdout.write(self.style.SUCCESS(
            f"{PREFIXE} Évaluations : {Evaluation.objects.count()} évaluations, "
            f"{n_notes} notes, {n_bulletins} bulletins."
        ))

    # ------------------------------------------------------------------ #
    # Finances : paiements variés, remises, factures
    # ------------------------------------------------------------------ #

    def _finances(self):
        caisse = self.users["caisse"]
        n_paiements = 0
        dates = [date(2026, 9, 25), date(2026, 10, 20), date(2026, 11, 25),
                 date(2026, 12, 10), date(2027, 1, 20), date(2027, 2, 15)]
        date_index = 0

        for i, inscription in enumerate(self.inscriptions):
            echeances = list(Echeance.objects.filter(inscription=inscription).order_by("date_echeance"))
            total_du = sum((e.montant_du for e in echeances), Decimal("0"))

            scenario = i % 5
            if scenario == 4:            # 20 % : impayé
                montants = []
            elif scenario in (1, 2):     # 40 % : paiement partiel (1re échéance)
                montants = [echeances[0].montant_du] if echeances else []
            else:                        # 40 % : entièrement payé en 3 versements
                tiers = (total_du / 3).quantize(Decimal("0.01"))
                montants = [tiers, tiers, total_du - 2 * tiers]

            for montant in montants:
                mode = self.rng.choice(list(Paiement.ModePaiement.choices))[0]
                paiement = Paiement.objects.create(
                    inscription=inscription, montant=montant, mode_paiement=mode,
                    reference=f"DEMO-{n_paiements + 1:04d}", encaisse_par=caisse,
                )
                imputer_paiement(paiement, utilisateur=caisse)
                jour_paiement = dates[date_index % len(dates)]
                Paiement.objects.filter(pk=paiement.pk).update(
                    date_paiement=timezone.make_aware(datetime.combine(jour_paiement, time.min))
                )
                date_index += 1
                n_paiements += 1
                if n_paiements % 2 == 0:
                    generer_recu(paiement)

            # Quelques remises et factures pour illustrer le module
            if i in (2, 8):
                Remise.objects.create(
                    inscription=inscription, type_remise=Remise.Type.BOURSE,
                    montant=Decimal("20000"), motif="Bourse d'excellence (jeu de démo)",
                    accorde_par=self.users["censeur"],
                )
            if scenario in (1, 2, 4):
                generer_facture(inscription)  # facture émise sur le solde restant

        self.stdout.write(self.style.SUCCESS(
            f"{PREFIXE} Finances : {n_paiements} paiements, "
            f"{Recu.objects.count()} reçus, {Facture.objects.count()} factures, "
            f"{Remise.objects.count()} remises."
        ))

    # ------------------------------------------------------------------ #
    # Fiches de paie des enseignants (mois courant)
    # ------------------------------------------------------------------ #

    def _paie(self):
        maintenant = timezone.localtime()
        n_fiches = 0
        for pers in self.enseignants:
            fiche, creee = creer_fiche_paie(pers, maintenant.month, maintenant.year)
            if creee:
                n_fiches += 1
        self.stdout.write(self.style.SUCCESS(
            f"{PREFIXE} Fiches de paie : {n_fiches} générée(s) pour "
            f"{mois_nom(maintenant.month)} {maintenant.year} "
            f"({FicheDePaie.objects.count()} au total)."
        ))

    # ------------------------------------------------------------------ #
    # Documents & journal (pour l'historique / portail)
    # ------------------------------------------------------------------ #

    def _documents(self):
        from documents.models import DocumentAdministratif
        secre = self.users["secre"]
        for i in range(3):
            if i < len(self.inscriptions):
                DocumentAdministratif.objects.create(
                    type_document="CERTIFICAT_SCOLARITE",
                    eleve=self.inscriptions[i].eleve, genere_par=secre,
                )
        if self.inscriptions:
            DocumentAdministratif.objects.create(
                type_document="CARTE_SCOLAIRE",
                eleve=self.inscriptions[1].eleve, genere_par=secre,
            )
        self.stdout.write(self.style.SUCCESS(
            f"{PREFIXE} Documents : {DocumentAdministratif.objects.count()} documents émis."
        ))

    def _journal(self):
        JournalActivite.objects.create(
            utilisateur=self.users["secre"], action="Inscription",
            objet_concerne="Élève",
            detail=f"Jeu de démonstration : {Eleve.objects.count()} élèves inscrits.",
        )
        JournalActivite.objects.create(
            utilisateur=self.users["caisse"], action="Encaissement",
            objet_concerne="Paiement",
            detail=f"Jeu de démonstration : {Paiement.objects.count()} paiements imputés (FIFO).",
        )
        JournalActivite.objects.create(
            utilisateur=self.users["censeur"], action="Bulletin",
            objet_concerne="Évaluation",
            detail=f"Jeu de démonstration : {Bulletin.objects.count()} bulletins générés.",
        )

    def _recap(self):
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS(f"{PREFIXE} JEU DE DÉMONSTRATION PRÊT — {ANNEE_LIBELLE}"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"  • Année scolaire        : {self.annee} (courante)")
        self.stdout.write(f"  • Périodes              : {len(PERIODES)}")
        self.stdout.write(f"  • Classes               : {Classe.objects.count()}")
        self.stdout.write(f"  • Matières              : {Matiere.objects.count()}")
        self.stdout.write(f"  • Matières tronc commun : {Matiere.objects.filter(tronc_commun=True).count()}")
        self.stdout.write(f"  • Élèves                : {Eleve.objects.count()}")
        self.stdout.write(f"  • Inscriptions          : {Inscription.objects.count()}")
        self.stdout.write(f"  • Évaluations           : {Evaluation.objects.count()}")
        self.stdout.write(f"  • Notes                 : {Note.objects.count()}")
        self.stdout.write(f"  • Bulletins             : {Bulletin.objects.count()}")
        self.stdout.write(f"  • Échéances             : {Echeance.objects.count()}")
        self.stdout.write(f"  • Paiements             : {Paiement.objects.count()}")
        self.stdout.write(f"  • Factures              : {Facture.objects.count()}")
        self.stdout.write(f"  • Reçus                 : {Recu.objects.count()}")
        self.stdout.write(f"  • Établissement         : {Etablissement.obtenir()}")
        self.stdout.write(f"  • Logos (en-tête)       : {Etablissement.obtenir().logos.filter(en_tete=True).count()}")
        self.stdout.write(f"  • Élèves avec photo     : {Eleve.objects.exclude(photo='').count()}")
        self.stdout.write(f"  • Séries (second cycle) : {Serie.objects.count()}")
        self.stdout.write(f"  • Coefficients (classe) : {ClasseMatiereCoefficient.objects.count()}")
        self.stdout.write(f"  • Horaire actif         : {HoraireJournalier.obtenir_actif()}")
        self.stdout.write(f"  • Fiches de paie        : {FicheDePaie.objects.count()}")
        self.stdout.write("  • Comptes               : admin/Admin123!, censeur/censeur123!, "
                          "secre/secre123!, caisse/caisse123!, prof/prof123!")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            "Astuce : connectez-vous avec admin/Admin123! pour voir les statistiques, "
            "ou secre/secre123! pour le module élèves."
        ))
