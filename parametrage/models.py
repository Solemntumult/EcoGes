from django.db import models


class AnneeScolaire(models.Model):
    libelle = models.CharField(max_length=20, unique=True, help_text="Ex. 2026-2027")
    date_debut = models.DateField()
    date_fin = models.DateField()
    est_courante = models.BooleanField(default=False)
    cloturee = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date_debut"]
        verbose_name = "Année scolaire"
        verbose_name_plural = "Années scolaires"

    def __str__(self):
        return self.libelle


class Periode(models.Model):
    """Trimestre ou semestre d'une année scolaire."""

    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name="periodes")
    libelle = models.CharField(max_length=50, help_text="Ex. 1er trimestre")
    ordre = models.PositiveSmallIntegerField(default=1)
    date_debut = models.DateField()
    date_fin = models.DateField()

    class Meta:
        ordering = ["annee_scolaire", "ordre"]
        unique_together = ("annee_scolaire", "ordre")

    def __str__(self):
        return f"{self.libelle} ({self.annee_scolaire})"


class Serie(models.Model):
    """Série du second cycle au Bénin (A1, A2, B, C, D, E, F1-F4, G1-G3, EA...)."""

    code = models.CharField(max_length=10, unique=True, help_text="Ex. A1, C, D, F1")
    libelle = models.CharField(max_length=120, blank=True, help_text="Ex. Biologie-Géologie")

    class Meta:
        ordering = ["code"]
        verbose_name = "Série"
        verbose_name_plural = "Séries"

    def __str__(self):
        return f"{self.code}" + (f" — {self.libelle}" if self.libelle else "")


class Niveau(models.Model):
    class Cycle(models.TextChoices):
        PRIMAIRE = "PRIMAIRE", "Primaire"
        COLLEGE = "COLLEGE", "Collège"
        LYCEE = "LYCEE", "Lycée"

    libelle = models.CharField(max_length=50, help_text="Ex. 6ème, 2nde")
    cycle = models.CharField(max_length=10, choices=Cycle.choices)
    ordre = models.PositiveSmallIntegerField(default=1)
    serie = models.ForeignKey(
        Serie, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="niveaux",
        help_text="Série du second cycle (ex. D) — laisser vide en premier cycle.",
    )

    class Meta:
        ordering = ["cycle", "ordre"]

    def __str__(self):
        return f"{self.libelle} {self.serie.code}" if self.serie_id else self.libelle


class Classe(models.Model):
    niveau = models.ForeignKey(Niveau, on_delete=models.PROTECT, related_name="classes")
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name="classes")
    libelle = models.CharField(max_length=50, help_text="Ex. 6ème A")
    effectif_max = models.PositiveSmallIntegerField(default=50)
    enseignant_principal = models.ForeignKey(
        "personnel.Personnel", on_delete=models.SET_NULL, null=True, blank=True, related_name="classes_principales"
    )

    class Meta:
        unique_together = ("niveau", "annee_scolaire", "libelle")
        ordering = ["niveau__ordre", "libelle"]

    def __str__(self):
        return f"{self.libelle} ({self.annee_scolaire})"

    @property
    def effectif_actuel(self):
        return self.inscriptions.filter(statut="ACTIVE").count()


class Matiere(models.Model):
    """Matière d'enseignement — le coefficient N'appARTIENT PAS à la matière.

    Il appartient toujours au couple (matière, classe) : voir
    ``ClasseMatiereCoefficient``. La même matière peut donc avoir un
    coefficient différent d'une classe à l'autre.
    """

    libelle = models.CharField(max_length=100)
    niveau = models.ForeignKey(Niveau, on_delete=models.CASCADE, related_name="matieres")
    tronc_commun = models.BooleanField(
        default=False,
        help_text="Matière du tronc commun : liée automatiquement à toutes les classes du niveau "
                  "(à la création d'une classe comme d'une matière).",
    )
    enseignants = models.ManyToManyField(
        "personnel.Personnel", blank=True, related_name="matieres_enseignees"
    )

    class Meta:
        unique_together = ("libelle", "niveau")
        ordering = ["niveau", "libelle"]

    def __str__(self):
        return f"{self.libelle} - {self.niveau}"


class ClasseMatiereCoefficient(models.Model):
    """Coefficient d'une matière pour une classe précise (gestionnaire de bulletins).

    Règle métier : un coefficient n'appartient jamais à une matière seule — il
    appartient TOUJOURS au couple (matière, classe). Mathématiques en 2nde D et
    Mathématiques en Terminale D sont deux valeurs indépendantes, même si les
    deux classes sont « série D ».
    """

    classe = models.ForeignKey(
        Classe, on_delete=models.CASCADE, related_name="matiere_coefficients"
    )
    matiere = models.ForeignKey(
        Matiere, on_delete=models.CASCADE, related_name="coefficients_par_classe"
    )
    coefficient = models.DecimalField(max_digits=4, decimal_places=1, default=1)

    class Meta:
        unique_together = ("classe", "matiere")
        ordering = ["matiere__libelle"]
        verbose_name = "Coefficient matière-classe"
        verbose_name_plural = "Coefficients matière-classe"

    def __str__(self):
        return f"{self.matiere.libelle} ({self.classe.libelle}) : {self.coefficient}"


class TypeFrais(models.Model):
    libelle = models.CharField(max_length=100, help_text="Ex. Inscription, Scolarité, Examen, Tenue")

    def __str__(self):
        return self.libelle


class GrilleTarifaire(models.Model):
    niveau = models.ForeignKey(Niveau, on_delete=models.CASCADE, related_name="grilles_tarifaires")
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name="grilles_tarifaires")
    type_frais = models.ForeignKey(TypeFrais, on_delete=models.PROTECT)
    montant = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ("niveau", "annee_scolaire", "type_frais")
        verbose_name = "Grille tarifaire"
        verbose_name_plural = "Grilles tarifaires"

    def __str__(self):
        return f"{self.type_frais} - {self.niveau} ({self.annee_scolaire}) : {self.montant}"


class Etablissement(models.Model):
    """Identité de l'établissement — configuration unique réutilisée par tous les documents.

    Saisie une seule fois (page « Établissement » ou admin Django), puis chaque PDF
    (bulletin, facture, reçu, certificat, carte scolaire...) affiche le logo, le nom
    officiel, l'adresse, l'IFU, les mentions légales et les signataires.
    """

    class StatutJuridique(models.TextChoices):
        PUBLIC = "PUBLIC", "Public"
        PRIVE_LAIC = "PRIVE_LAIC", "Privé laïc"
        PRIVE_CONFESSIONNEL = "PRIVE_CONFESSIONNEL", "Privé confessionnel"

    class Categorie(models.TextChoices):
        MATERNELLE = "MATERNELLE", "Maternelle"
        PRIMAIRE = "PRIMAIRE", "Primaire"
        COLLEGE = "COLLEGE", "Collège"
        LYCEE = "LYCEE", "Lycée"
        COMPLEXE = "COMPLEXE", "Complexe scolaire"

    # --- Identité ----------------------------------------------------------
    nom_officiel = models.CharField(max_length=200, default="GESTION SCOLAIRE",
                                    help_text="Nom figurant sur l'autorisation d'ouverture.")
    sigle = models.CharField(max_length=30, blank=True, help_text="Ex. CEG, CS, CPG...")
    devise = models.CharField(max_length=200, blank=True)
    logo = models.ImageField(upload_to="etablissement/", blank=True, null=True,
                             help_text="PNG fond transparent, idéalement ≥ 1000×1000 px.")
    adresse = models.CharField(max_length=255, blank=True, help_text="Rue / quartier")
    ville = models.CharField(max_length=100, blank=True)
    commune = models.CharField(max_length=100, blank=True)
    pays = models.CharField(max_length=100, default="Bénin")
    boite_postale = models.CharField(max_length=30, blank=True, help_text="BP")
    telephone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    site_web = models.URLField(blank=True)

    # --- Statut légal ------------------------------------------------------
    statut_juridique = models.CharField(max_length=25, choices=StatutJuridique.choices,
                                        default=StatutJuridique.PRIVE_LAIC)
    categorie = models.CharField(max_length=15, choices=Categorie.choices,
                                 default=Categorie.COLLEGE)
    ministere_tutelle = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Ex. Ministère des Enseignements Secondaire, Technique et de la Formation Professionnelle",
    )
    numero_arrete = models.CharField(max_length=100, blank=True, help_text="Arrêté d'autorisation d'ouverture")
    date_arrete = models.DateField(null=True, blank=True)
    code_etablissement = models.CharField(max_length=50, blank=True,
                                          help_text="Matricule attribué par le ministère de l'Éducation")
    annee_creation = models.PositiveSmallIntegerField(null=True, blank=True)
    fondateur = models.CharField(max_length=150, blank=True)
    ifu = models.CharField(max_length=30, blank=True,
                           help_text="Identifiant Fiscal Unique — obligatoire sur les factures au Bénin")
    rccm = models.CharField(max_length=50, blank=True, help_text="Registre du Commerce et du Crédit Mobilier")

    # --- Signataires (signature manuscrite après impression) ----------------
    nom_directeur = models.CharField(max_length=150, blank=True)
    nom_censeur = models.CharField(max_length=150, blank=True)
    nom_comptable = models.CharField(max_length=150, blank=True)

    # --- Mentions légales & fiscalité --------------------------------------
    mentions_legales = models.TextField(blank=True,
                                        help_text="Texte de pied de page (clause anti-falsification, validité...)")
    regime_fiscal = models.CharField(max_length=200, blank=True,
                                     help_text="Ex. Exonération de TVA sur les frais de scolarité")
    formule_certification = models.CharField(
        max_length=255, blank=True, default="",
        help_text="Formule de certification standard des certificats",
    )

    class Meta:
        verbose_name = "Établissement"
        verbose_name_plural = "Établissement (configuration unique)"

    def __str__(self):
        return self.nom_officiel

    @classmethod
    def obtenir(cls):
        """Retourne l'unique configuration (créée vide par défaut si absente)."""
        etab, _ = cls.objects.get_or_create(pk=1)
        return etab

    @property
    def logos_en_tete(self):
        """Logos affichés dans l'en-tête des documents (triés par ordre)."""
        return self.logos.filter(en_tete=True).order_by("ordre", "pk")


class LogoEtablissement(models.Model):
    """Logo de l'établissement (plusieurs possibles).

    Certains établissements affichent plusieurs logos dans leurs documents :
    logo de l'État / ministère de tutelle, logo du collège, logo de la
    République... Chacun a un libellé (pour l'identifier dans l'interface),
    un ordre d'affichage et peut être inclus ou non dans l'en-tête des
    documents générés.
    """

    etablissement = models.ForeignKey(
        Etablissement, on_delete=models.CASCADE, related_name="logos"
    )
    libelle = models.CharField(
        max_length=100, blank=True, default="",
        help_text="Ex. Logo de la République, Logo du ministère, Logo du collège",
    )
    image = models.ImageField(
        upload_to="etablissement/logos/",
        help_text="PNG fond transparent, idéalement ≥ 1000×1000 px.",
    )
    ordre = models.PositiveSmallIntegerField(default=0, help_text="Ordre d'affichage dans l'en-tête.")
    en_tete = models.BooleanField(
        default=True,
        help_text="Coché = affiché dans l'en-tête de tous les documents générés.",
    )

    class Meta:
        ordering = ["ordre", "pk"]
        verbose_name = "Logo"
        verbose_name_plural = "Logos"

    def __str__(self):
        return self.libelle or f"Logo {self.pk}"


class HoraireJournalier(models.Model):
    """Mode d'horaire de l'établissement (coupé / journée continue).

    Un seul horaire est actif à la fois : il s'applique à toutes les classes.
    Les pauses (récréation, déjeuner...) sont découpées hors de la journée
    pour former les plages de cours affichées dans l'éditeur d'emploi du temps.
    """

    class AffichageCellule(models.TextChoices):
        MATIERE_ET_PROFESSEUR = 'MATIERE_PROF', 'Matière + Professeur'
        MATIERE_SEULE = 'MATIERE', 'Matière seule'
        PROFESSEUR_SEUL = 'PROFESSEUR', 'Professeur seul'

    libelle = models.CharField(max_length=100, help_text="Ex. Journée continue (07:00–15:35)")
    actif = models.BooleanField(default=False, help_text="Un seul horaire peut être actif à la fois.")
    heure_debut_journee = models.TimeField(help_text="Heure de début des cours le matin.")
    heure_fin_journee = models.TimeField(help_text="Heure de fin des cours le soir.")
    duree_creneau_base = models.PositiveSmallIntegerField(default=60, help_text="Durée d'un créneau de base en minutes (ex. 45, 55, 60).")
    affichage_cellule = models.CharField(max_length=15, choices=AffichageCellule.choices, default=AffichageCellule.MATIERE_ET_PROFESSEUR, help_text="Contenu affiché dans chaque case de l'emploi du temps.")

    class Meta:
        ordering = ["-actif", "libelle"]
        verbose_name = "Horaire journalier"
        verbose_name_plural = "Horaires journaliers"

    def __str__(self):
        actif = " ✓" if self.actif else ""
        return f"{self.libelle} ({self.heure_debut_journee:%H:%M}–{self.heure_fin_journee:%H:%M}){actif}"

    @classmethod
    def obtenir_actif(cls):
        """Retourne l'horaire actuellement appliqué (ou None)."""
        return cls.objects.filter(actif=True).first()

    def segments(self):
        """Plages de cours de la journée, en soustrayant les pauses.

        Retourne une liste de couples (heure_debut, heure_fin) triés.
        """
        plages = [(self.heure_debut_journee, self.heure_fin_journee)]
        for pause in self.pauses.order_by("heure_debut"):
            nouvelles = []
            for debut, fin in plages:
                if pause.heure_fin <= debut or pause.heure_debut >= fin:
                    nouvelles.append((debut, fin))        # pause hors de la plage
                elif pause.heure_debut <= debut and pause.heure_fin >= fin:
                    continue                              # pause couvre toute la plage
                else:
                    if pause.heure_debut > debut:
                        nouvelles.append((debut, pause.heure_debut))
                    if pause.heure_fin < fin:
                        nouvelles.append((pause.heure_fin, fin))
            plages = nouvelles
        return sorted(plages, key=lambda p: (p[0], p[1]))

    def plages_horaires(self):
        """Créneaux de cours découpés selon la durée de base configurable.

        Subdivise les segments (plages entre pauses) en tranches de
        ``duree_creneau_base`` minutes : c'est sur cette grille que
        l'éditeur d'emploi du temps aligne les cours, chaque cours
        pouvant occuper un ou plusieurs créneaux consécutifs.
        Le dernier créneau de chaque segment peut être plus court.
        """
        from datetime import date, datetime, timedelta

        duree = timedelta(minutes=self.duree_creneau_base)
        plages = []
        for debut, fin in self.segments():
            courant = datetime.combine(date.min, debut)
            limite = datetime.combine(date.min, fin)
            while courant < limite:
                suivant = courant + duree
                if suivant > limite:
                    suivant = limite
                plages.append((courant.time(), suivant.time()))
                courant = suivant
        return plages


class PauseHoraire(models.Model):
    """Pause dans la journée (récréation, pause déjeuner...) — durée ajustable."""

    horaire = models.ForeignKey(HoraireJournalier, on_delete=models.CASCADE, related_name="pauses")
    libelle = models.CharField(max_length=100, help_text="Ex. Récréation, Pause déjeuner")
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()

    class Meta:
        ordering = ["horaire", "heure_debut"]

    def __str__(self):
        return f"{self.libelle} ({self.heure_debut:%H:%M}–{self.heure_fin:%H:%M})"


class QuotaHoraireMatiere(models.Model):
    """Quota d'heures hebdomadaires à planifier pour une matière dans une classe."""

    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name="quotas_horaires")
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name="quotas_horaires")
    heures_par_semaine = models.DecimalField(
        max_digits=4, decimal_places=1,
        help_text="Nombre d'heures de cours par semaine pour cette matière dans cette classe.",
    )

    class Meta:
        unique_together = ("matiere", "classe")
        ordering = ["matiere__libelle"]
        verbose_name = "Quota horaire"
        verbose_name_plural = "Quotas horaires"

    def __str__(self):
        return f"{self.matiere.libelle} ({self.classe.libelle}) : {self.heures_par_semaine}h/sem"


class BaremeEvaluation(models.Model):
    """Configuration du système de notation (seuils de mentions, note de passage)."""

    annee_scolaire = models.OneToOneField(
        AnneeScolaire, on_delete=models.CASCADE, related_name="bareme"
    )
    note_max = models.DecimalField(max_digits=4, decimal_places=1, default=20)
    seuil_passage = models.DecimalField(max_digits=4, decimal_places=1, default=10)
    seuil_mention_bien = models.DecimalField(max_digits=4, decimal_places=1, default=14)
    seuil_mention_tres_bien = models.DecimalField(max_digits=4, decimal_places=1, default=16)

    class Meta:
        verbose_name = "Barème d'évaluation"
        verbose_name_plural = "Barèmes d'évaluation"

    def __str__(self):
        return f"Barème {self.annee_scolaire}"
