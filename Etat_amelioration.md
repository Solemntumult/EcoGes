# État des Lieux & Améliorations — Plateforme de Gestion Scolaire (PIGS)

> **Document de référence** — Bilan exhaustif des capacités actuelles et feuille de route des fonctionnalités à ajouter pour couvrir **l'ensemble des cas d'utilisation réels** d'une école primaire et d'un collège.
>
> Dernière mise à jour : 30 septembre 2026

---

## Sommaire

- [I. Bilan des capacités actuelles](#i-bilan-des-capacités-actuelles)
  - [1. Comptes, Sécurité & Traçabilité](#1-comptes-sécurité--traçabilité)
  - [2. Paramétrage Académique & Structurel](#2-paramétrage-académique--structurel)
  - [3. Gestion des Élèves & Admissions](#3-gestion-des-élèves--admissions)
  - [4. Personnel, Emploi du Temps & Paie](#4-personnel-emploi-du-temps--paie-horaire)
  - [5. Évaluations, Notes & Bulletins](#5-évaluations-notes--bulletins)
  - [6. Scolarité, Finances & Facturation](#6-scolarité-finances--facturation)
  - [7. Documents Administratifs & Modèles](#7-documents-administratifs--modèles)
  - [8. Tableaux de Bord & Portail Parents](#8-tableaux-de-bord--portail-parents)
- [II. Fonctionnalités à ajouter](#ii-fonctionnalités-à-ajouter)
  - [1. Vie Scolaire, Assiduité & Discipline](#1-module-vie-scolaire-assiduité--discipline)
  - [2. Cahier de Textes & Devoirs](#2-cahier-de-textes-numérique--devoirs)
  - [3. Spécificités Primaire vs Collège](#3-spécificités-pédagogiques--école-primaire-vs-collège)
  - [4. Services Annexes (Cantine, Transport, Santé, CDI)](#4-services-annexes-de-létablissement)
  - [5. Communication Temps Réel (SMS, Messagerie)](#5-communication-temps-réel)
  - [6. Finances Avancées & Paiement en Ligne](#6-finances-avancées--paiement-en-ligne)
  - [7. Admissions & Pré-inscription en Ligne](#7-admissions--portail-de-pré-inscription-en-ligne)
- [III. Synthèse comparative](#iii-synthèse-comparative)
- [IV. Prochaines étapes suggérées](#iv-prochaines-étapes-suggérées)

---

## I. Bilan des capacités actuelles

La plateforme dispose d'une base technique solide en **Django** et **MySQL**, avec une séparation claire en **9 applications Django** modulaires, couvrant **45 cas d'utilisation** (UC-01 à UC-45) issus du cahier des charges.

```
                          ┌───────────────────────────┐
                          │   GESTION SCOLAIRE (PIGS)  │
                          └─────────────┬─────────────┘
          ┌──────────────┬──────────────┼──────────────┬──────────────┐
          ▼              ▼              ▼              ▼              ▼
     [Comptes &     [Paramétrage   [Élèves &      [Évaluations   [Finances &
      Sécurité]     Académique]    Scolarité]     & Bulletins]    Facturation]
          │              │              │              │              │
          ▼              ▼              ▼              ▼              ▼
     [Personnel &   [Documents     [Tableaux de   [Portail
     Emploi du tps]  Officiels]    Bord Stats]     Parents]
```

### Récapitulatif des modèles par application

| App | Modèles principaux |
|---|---|
| `comptes` | `Utilisateur`, `JournalActivite` |
| `parametrage` | `AnneeScolaire`, `Periode`, `Niveau` (+ `Serie`), `Classe`, `Matiere`, `ClasseMatiereCoefficient`, `TypeFrais`, `GrilleTarifaire`, `BaremeEvaluation`, `HoraireJournalier`, `PauseHoraire`, `Etablissement`, `LogoEtablissement`, `QuotaHoraireMatiere` |
| `eleves` | `Eleve`, `Tuteur`, `Inscription` |
| `personnel` | `Personnel`, `Affectation` (avec `tarif_horaire`), `CreneauEmploiDuTemps`, `DisponibiliteEnseignant` |
| `evaluations` | `Evaluation`, `Note`, `NoteModification`, `Bulletin` |
| `finances` | `Echeance`, `Remise`, `Paiement`, `ImputationPaiement`, `Facture`, `LigneFacture`, `Recu`, `FicheDePaie` |
| `documents` | `ModeleDocument`, `DocumentAdministratif` |
| `statistiques` | *(pas de modèles propres — agrégations sur les autres apps)* |
| `portail` | *(pas de modèles propres — vues lecture seule sur les données élèves)* |

---

### 1. Comptes, Sécurité & Traçabilité

**App :** `comptes` — **UC couverts :** UC-01 à UC-05

| Fonctionnalité | Détail | Statut |
|---|---|:---:|
| Gestion des 7 rôles métier | Admin, Censeur, Secrétariat, Comptable, Enseignant, Parent, Super-admin technique | ✅ |
| Verrouillage de compte | Blocage temporaire automatique après tentatives de connexion échouées | ✅ |
| Réinitialisation de mot de passe | Par lien envoyé par e-mail (SMTP configurable) | ✅ |
| Journal d'activité | Enregistrement de chaque action sensible (qui, quoi, quand, objet, détails) | ✅ |
| Groupes & permissions Django | Granularité fine lecture/écriture/suppression par module | ✅ |

---

### 2. Paramétrage Académique & Structurel

**App :** `parametrage` — **UC couverts :** UC-06 à UC-10

| Fonctionnalité | Détail | Statut |
|---|---|:---:|
| Années scolaires | Année active unique, clôture d'année | ✅ |
| Périodes (trimestres/semestres) | Découpage temporel configurable avec ordre et dates | ✅ |
| Cycles & Niveaux | Primaire, Collège, Lycée | ✅ |
| Séries du second cycle | Liste officielle béninoise (A1, A2, B, C, D, E, F1-F4, G1-G3, EA) | ✅ |
| Classes & effectifs | Rattachement niveau/année, effectif max, professeur principal | ✅ |
| Matières & coefficients | Coefficient lié au couple (classe, matière) via `ClasseMatiereCoefficient` | ✅ |
| Tronc commun | Auto-liaison aux classes du niveau (signal `post_save`) | ✅ |
| Quotas horaires | Heures hebdomadaires par matière/classe | ✅ |
| Horaires scolaires | Modes d'horaires (journée continue/coupée), durée de créneau paramétrable | ✅ |
| Pauses configurables | Récréation, pause déjeuner — découpe automatique des plages de cours | ✅ |
| Grilles tarifaires | Tarification par niveau × type de frais × année | ✅ |
| Barème d'évaluation | Note max, seuil de passage, mentions (Bien, Très Bien) | ✅ |
| Identité de l'établissement | Nom, IFU, RCCM, arrêté, statut juridique, signataires, multi-logos | ✅ |

---

### 3. Gestion des Élèves & Admissions

**App :** `eleves` — **UC couverts :** UC-11 à UC-16

| Fonctionnalité | Détail | Statut |
|---|---|:---:|
| Fiche élève complète | Matricule auto-généré (`ELV-YYYY-XXXXX`), photo, état civil, régime | ✅ |
| Multi-tuteurs | Père, Mère, Tuteur légal, Autre — avec contact d'urgence | ✅ |
| Inscription avec échéancier automatique | Génération de l'échéancier dès l'inscription via la grille tarifaire | ✅ |
| Types d'inscription | Nouveau, Redoublant, Transfert entrant, Réinscription | ✅ |
| Réinscription en masse | Suggestion automatique de la classe supérieure par classe | ✅ |
| Transfert & Radiation | Procédure avec motif et archivage des inscriptions actives | ✅ |
| Carte scolaire PDF | Photo, matricule, QR code de vérification | ✅ |
| Recherche multicritère | Par nom, matricule, classe, statut | ✅ |
| Dossier élève consolidé | Vue complète : scolarité, finances, notes, documents | ✅ |

---

### 4. Personnel, Emploi du Temps & Paie Horaire

**App :** `personnel` — **UC couverts :** UC-17 à UC-19

| Fonctionnalité | Détail | Statut |
|---|---|:---:|
| Fiches personnel | Enseignants et staff (censeur, secrétaire, comptable, surveillant, autre) | ✅ |
| Affectations pédagogiques | Enseignant ↔ Classe ↔ Matière avec tarif horaire négocié | ✅ |
| Éditeur d'emploi du temps | Grille jour × heure par classe, interactif | ✅ |
| Détection de conflits | Enseignant, salle et classe déjà occupés → blocage de l'enregistrement | ✅ |
| Disponibilités enseignant | Créneaux de disponibilité hebdomadaires | ✅ |
| Rémunération horaire automatique | Calcul : heures hebdo × 4,33 × tarif horaire par affectation | ✅ |
| Fiches de paie numérotées | `FP-YYYY-XXXXXX`, encaissement, bulletin PDF | ✅ |

---

### 5. Évaluations, Notes & Bulletins

**App :** `evaluations` — **UC couverts :** UC-20 à UC-25

| Fonctionnalité | Détail | Statut |
|---|---|:---:|
| Types d'évaluations | Devoir, Composition, Interrogation — avec coefficient propre | ✅ |
| Saisie des notes sécurisée | Grille de saisie restreinte aux affectations de l'enseignant connecté | ✅ |
| Verrouillage des notes | Verrouillage par période par le censeur / direction | ✅ |
| Traçabilité post-verrouillage | Historique des modifications de notes (`NoteModification`) | ✅ |
| Calcul des moyennes pondérées | Pondération par coefficient du couple (classe, matière) | ✅ |
| Calcul automatique des rangs | Classement par ordre décroissant, gestion des ex-æquo | ✅ |
| Attribution des mentions | Selon barème (Passable, A. Bien, Bien, T. Bien) | ✅ |
| Bulletins trimestriels PDF | Logos, en-tête, appréciations, signatures, filigrane | ✅ |
| Bulletins annuels | Récapitulatif sur toutes les périodes | ✅ |
| Téléchargement groupé (ZIP) | Tous les bulletins d'une classe dans une archive | ✅ |
| Décisions de fin d'année | Admis(e), Redouble, Exclu(e) | ✅ |

---

### 6. Scolarité, Finances & Facturation

**App :** `finances` — **UC couverts :** UC-26 à UC-34

| Fonctionnalité | Détail | Statut |
|---|---|:---:|
| Échéanciers automatiques | Générés à l'inscription à partir de la grille tarifaire du niveau | ✅ |
| Bourses & remises | Bourse, Exonération partielle, Réduction commerciale — avec motif | ✅ |
| Encaissements multi-modes | Espèces, Chèque, Virement bancaire, Mobile Money | ✅ |
| Imputation FIFO | Solde automatique des échéances les plus anciennes en priorité | ✅ |
| Factures numérotées | `FA-YYYY-XXXXXX`, lignes détaillées, PDF | ✅ |
| Reçus de paiement | `RC-YYYY-XXXXXX`, PDF avec détails de l'encaissement | ✅ |
| Suivi des impayés & relances | Tableau des retards, avis de relance | ✅ |
| Annulation & remboursement | Procédure avec motif et mise à jour des soldes | ✅ |
| Fiches de paie personnel | Rémunération automatique des enseignants via emploi du temps | ✅ |

---

### 7. Documents Administratifs & Modèles

**App :** `documents` — **UC couverts :** UC-35 à UC-39

| Fonctionnalité | Détail | Statut |
|---|---|:---:|
| Modèles personnalisables | En-têtes et mentions légales éditables par type de document | ✅ |
| Certificats de scolarité | PDF numéroté (`CER-YYYY-XXXXXX`) | ✅ |
| Attestations de réussite | PDF numéroté (`ATT-YYYY-XXXXXX`) | ✅ |
| Relevés de notes | PDF numéroté (`REL-YYYY-XXXXXX`) | ✅ |
| Listes de classe | PDF avec effectifs et statistiques (`LIS-YYYY-XXXXXX`) | ✅ |
| Convocations / courriers types | PDF personnalisable (`COU-YYYY-XXXXXX`) | ✅ |
| Avis de relance financière | PDF (`AVR-YYYY-XXXXXX`) | ✅ |
| Cartes scolaires | PDF avec photo et QR code (`CAR-YYYY-XXXXXX`) | ✅ |
| Éditeur avec aperçu temps réel | Personnalisation du contenu avant génération | ✅ |
| Envoi par e-mail | Document PDF en pièce jointe directement depuis l'interface | ✅ |
| Exports multi-formats | PDF, Word, HTML | ✅ |

---

### 8. Tableaux de Bord & Portail Parents

**Apps :** `statistiques` & `portail` — **UC couverts :** UC-40 à UC-45

| Fonctionnalité | Détail | Statut |
|---|---|:---:|
| Tableau de bord direction | Effectifs par classe/niveau/sexe, taux de recouvrement, moyennes | ✅ |
| Graphiques interactifs | Chart.js (évolution des effectifs, résultats, recouvrement) | ✅ |
| Exports statistiques | PDF et Excel | ✅ |
| Sauvegarde de la base | Commande `sauvegarde_db` (dump MySQL dans `backups/`) | ✅ |
| Portail parents (lecture seule) | Accès sécurisé par email tuteur | ✅ |
| Consultation résultats | Bulletins, notes, moyennes | ✅ |
| Consultation paiements | Échéances, soldes, historique des règlements | ✅ |
| Téléchargement documents | Documents officiels (certificats, attestations, cartes) | ✅ |

---

## II. Fonctionnalités à ajouter

Pour couvrir **l'ensemble des cas d'utilisation réels** d'une école primaire et d'un collège, les modules et extensions suivants sont nécessaires :

```
                  NOUVEAUX MODULES & ÉVOLUTIONS RECOMMANDÉES
┌─────────────────────────────────┐   ┌─────────────────────────────────┐
│ 1. ASSIDUITÉ & VIE SCOLAIRE     │   │ 2. PÉDAGOGIE QUOTIDIENNE        │
│ • Feuille d'appel par heure     │   │ • Cahier de textes numérique    │
│ • Retards & Absences (justif.)  │   │ • Devoirs à la maison & rendus  │
│ • Carnet de discipline (retenues│   │ • Évaluation compétences (APC)  │
│   avertissements, exclusions)   │   │ • Examens blancs (CEP, BEPC)    │
└─────────────────────────────────┘   └─────────────────────────────────┘
┌─────────────────────────────────┐   ┌─────────────────────────────────┐
│ 3. SERVICES ANNEXES ÉCOLE       │   │ 4. COMMUNICATION & NOTIFICATIONS│
│ • Cantine & Demi-pension        │   │ • Passerelle SMS (alertes)      │
│ • Transport scolaire (bus)      │   │ • Messagerie interne parents    │
│ • Santé / Infirmerie scolaire   │   │ • Notifications instantanées    │
│ • Bibliothèque & Manuels (CDI)  │   │ • Carnet de correspondance dig. │
└─────────────────────────────────┘   └─────────────────────────────────┘
┌─────────────────────────────────┐   ┌─────────────────────────────────┐
│ 5. FINANCES & PAIEMENT EN LIGNE │   │ 6. SPÉCIFICITÉS PRIMAIRE/COLLÈGE│
│ • Passerelle Mobile Money API   │   │ • Maître unique / Décloisonnemt │
│ • Journal de caisse journalier  │   │ • Garderie périscolaire         │
│ • Suivi des dépenses/charges    │   │ • Conseils de classe & Mentions │
│ • Inscription en ligne (admis.) │   │ • Délégués élèves & orientation │
└─────────────────────────────────┘   └─────────────────────────────────┘
```

---

### 1. Module Vie Scolaire, Assiduité & Discipline

> **Priorité : 🔴 Critique** — C'est l'essence même de la vie scolaire quotidienne.

**App suggérée :** `viescolaire`

Actuellement, le système ne sait pas si un élève est présent en classe. Ce module comble ce manque fondamental.

#### 1.1 Feuille d'appel numérique

| Fonctionnalité | Détail |
|---|---|
| Pointage par séance (collège) | L'enseignant pointe au début de chaque heure de cours : Présent, Absent, En retard, À l'infirmerie |
| Pointage par demi-journée (primaire) | Le maître / la maîtresse pointe matin et après-midi |
| Signalement instantané | Alerte au bureau de la vie scolaire / censeur / surveillant général |
| Récapitulatif par élève | Compteur automatique : nombre d'absences, de retards, taux de présence |
| Intégration au bulletin | Affichage sur le bulletin trimestriel : « 4 absences dont 2 non justifiées, 3 retards » |

#### 1.2 Gestion des absences & justificatifs

| Fonctionnalité | Détail |
|---|---|
| Qualification de l'absence | Justifiée (certificat médical, motif familial) ou Injustifiée |
| Pièces justificatives | Upload de scans (certificat médical, lettre des parents) |
| Workflow de validation | Soumission par le parent → Validation par la vie scolaire |
| Alerte parentale | SMS/e-mail automatique au tuteur dès la première heure d'absence injustifiée |

#### 1.3 Gestion disciplinaire (sanctions & punitions)

| Fonctionnalité | Détail |
|---|---|
| Registre des incidents | Bavardages répétés, insolence, bagarre, oubli de matériel, triche |
| Punitions scolaires | Devoirs supplémentaires, retenues/colles (gestion des créneaux : mercredi ou samedi) |
| Sanctions officielles | Avertissement de conduite, Blâme, Exclusion temporaire (1-8 jours), Exclusion définitive |
| Conseil de discipline | Convocation, procès-verbal, décision — traçabilité complète |
| Convocation automatique | Génération de la convocation des parents pour motif disciplinaire |
| Historique par élève | Synthèse visible dans le dossier élève et le portail parents |

**Modèles à créer :**
- `Appel` (inscription, date, creneau, statut: PRESENT/ABSENT/RETARD/INFIRMERIE, justifie, motif)
- `JustificatifAbsence` (appel, fichier, valide_par, date_validation)
- `IncidentDisciplinaire` (eleve, date, type_incident, description, signale_par)
- `Sanction` (incident, type_sanction, date_debut, date_fin, decision_par, motif)
- `Retenue` (sanction, date, heure_debut, heure_fin, salle, surveillant)

---

### 2. Cahier de Textes Numérique & Devoirs

> **Priorité : 🟠 Haute** — Indispensable pour les enseignants et les parents.

**App suggérée :** `cahier_texte`

#### 2.1 Cahier de textes de la classe

| Fonctionnalité | Détail |
|---|---|
| Saisie par séance | L'enseignant saisit à la fin de chaque cours : contenu dispensé, chapitre traité, objectifs atteints |
| Suivi de l'avancement | Pourcentage du programme réalisé par matière/classe — visible par le censeur/inspecteur |
| Pièces jointes | Support, document ou lien vidéo associé au cours |

#### 2.2 Devoirs à domicile

| Fonctionnalité | Détail |
|---|---|
| Prescription de devoirs | Date de prescription, date limite de rendu, consignes détaillées |
| Documents joints | Sujet d'exercice en PDF, fiche de révision, lien vidéo |
| Consultation par les parents | Visible directement sur le portail parents/élèves |

**Modèles à créer :**
- `SeanceCours` (affectation, date, creneau, contenu, chapitre, objectifs, fichier_support)
- `DevoirMaison` (affectation, date_prescription, date_limite, consignes, fichier_sujet)

---

### 3. Spécificités Pédagogiques : École Primaire vs Collège

> **Priorité : 🟠 Haute** — Le fonctionnement pédagogique diffère radicalement entre les deux niveaux.

#### 3.1 Spécificités École Primaire

| Fonctionnalité | Détail |
|---|---|
| Enseignant titulaire unique | Affecter un maître à la classe entière sans créer N affectations individuelles |
| Évaluation par compétences (APC) | Livret d'acquisitions : Non Acquis (NA), En Cours (ECA), Acquis (A), Expert (E) — en remplacement ou complément des notes chiffrées en CI/CP/CE1 |
| Garderie périscolaire | Gestion des arrivées matinales (6h30-7h30) et études surveillées (17h-18h30) avec tarification |
| Carnet de liaison numérique | Messages ponctuels maître ↔ parents (signature numérique d'accusé de lecture) |

#### 3.2 Spécificités Collège

| Fonctionnalité | Détail |
|---|---|
| Conseils de classe trimestriels | Procès-verbal de délibération, attribution des mentions : Félicitations, Tableau d'honneur, Encouragements, Avertissement travail/conduite |
| Délégués de classe | Élection et enregistrement des délégués élèves et parents correspondants |
| Examens blancs (CEP, BEPC) | Numéros d'anonymat, répartition dans les salles d'examen, double correction |
| Orientation fin de cycle | Fiche de vœux (série souhaitée pour le lycée), avis du conseil de classe |

**Modèles à créer :**
- `CompetenceAPC` (matiere, libelle, niveau_attendu)
- `EvaluationCompetence` (inscription, competence, niveau: NA/ECA/A/E, periode, evaluateur)
- `ConseilDeClasse` (classe, periode, date, president, secretaire)
- `MentionConseil` (conseil, inscription, type_mention: FELICITATIONS/TABLEAU_HONNEUR/ENCOURAGEMENTS/AVERTISSEMENT_TRAVAIL/AVERTISSEMENT_CONDUITE)
- `DelegueClasse` (classe, eleve, type: TITULAIRE/SUPPLEANT, annee_scolaire)
- `InscriptionGarderie` (eleve, formule, tarif_mensuel)

---

### 4. Services Annexes de l'Établissement

> **Priorité : 🟡 Moyenne** — Modules optionnels mais très demandés sur le terrain.

#### 4.1 Cantine & Demi-pension

**App suggérée :** `cantine`

| Fonctionnalité | Détail |
|---|---|
| Formules d'abonnement | Annuel, mensuel, ou carnet de tickets repas |
| Pointage des présences au réfectoire | Par liste nominative ou badge |
| Menus de la semaine | Affichage sur le portail parents |
| Régimes spéciaux | Allergies alimentaires, régimes religieux/médicaux |
| Tarification et facturation | Intégré au module finances existant |

**Modèles à créer :**
- `InscriptionCantine` (inscription, formule, tarif, allergies, regime_special)
- `PresenceRepas` (inscription_cantine, date, present)
- `MenuSemaine` (semaine_debut, lundi, mardi, mercredi, jeudi, vendredi)

#### 4.2 Transport Scolaire

**App suggérée :** `transport`

| Fonctionnalité | Détail |
|---|---|
| Lignes de car/bus | Itinéraire, arrêts, horaires, chauffeur |
| Inscription au circuit | Aller-retour ou aller simple, tarification |
| Pointage des montées/descentes | Fiche par trajet |

**Modèles à créer :**
- `LigneTransport` (libelle, chauffeur, vehicule, capacite)
- `ArretTransport` (ligne, libelle, heure_passage, ordre)
- `InscriptionTransport` (inscription, ligne, arret, formule: ALLER_RETOUR/ALLER, tarif)

#### 4.3 Infirmerie & Santé Scolaire

**App suggérée :** `sante`

| Fonctionnalité | Détail |
|---|---|
| Fiche médicale confidentielle | Groupe sanguin, allergies, maladies chroniques, vaccins obligatoires |
| Personnes à contacter en urgence | Priorité d'appel en cas d'urgence vitale |
| Registre des passages à l'infirmerie | Date, heure, motif, soins administrés, retour en classe ou évacuation |
| Suivi des vaccinations | Conformité au calendrier vaccinal national |

**Modèles à créer :**
- `FicheMedicale` (eleve, groupe_sanguin, allergies, maladies_chroniques, traitements, medecin_traitant)
- `Vaccination` (eleve, vaccin, date, rappel_prevu)
- `PassageInfirmerie` (eleve, date_heure_entree, date_heure_sortie, motif, soins, issue: RETOUR_CLASSE/REPOS/EVACUATION, infirmier)

#### 4.4 Bibliothèque / CDI & Manuels Scolaires

**App suggérée :** `bibliotheque`

| Fonctionnalité | Détail |
|---|---|
| Prêt de manuels scolaires | Caution, état du livre (neuf/bon/dégradé), inventaire de retour en fin d'année |
| Catalogue de la bibliothèque | Titre, auteur, ISBN, exemplaires disponibles |
| Suivi des emprunts | Date de prêt, date de retour prévu, relances automatiques |

**Modèles à créer :**
- `Ouvrage` (titre, auteur, isbn, categorie, nombre_exemplaires, emplacement)
- `Exemplaire` (ouvrage, code_barre, etat: NEUF/BON/USE/DEGRADE)
- `Emprunt` (exemplaire, eleve, date_pret, date_retour_prevue, date_retour_effectif, etat_retour)
- `PretManuel` (exemplaire, inscription, etat_depart, etat_retour, caution)

---

### 5. Communication Temps Réel

> **Priorité : 🟠 Haute** — Le courrier papier ou l'e-mail seul ne suffit pas pour les urgences.

**App suggérée :** `communication`

#### 5.1 Passerelle SMS

| Fonctionnalité | Détail |
|---|---|
| Alerte d'absence injustifiée | SMS immédiat au tuteur dès la première heure : *« Votre enfant X est absent ce matin sans justificatif. »* |
| Relance d'échéance financière | SMS 3 jours avant l'échéance, puis à J+1 si impayé |
| Alertes événementielles | Météo, événement exceptionnel, réunion urgente de parents |
| SMS en masse | Envoi groupé par classe, niveau ou établissement entier |
| Intégration API | Passerelle SMS locale (Bénin : Lighty, Vonage, Africa's Talking) |

#### 5.2 Messagerie interne sécurisée

| Fonctionnalité | Détail |
|---|---|
| Fil de discussion | Parent ↔ Professeur principal ↔ Direction (évite l'échange de numéros WhatsApp personnels) |
| Notifications | Badge dans l'interface web + e-mail de synthèse quotidien |

**Modèles à créer :**
- `MessageSMS` (destinataire, telephone, contenu, statut: EN_ATTENTE/ENVOYE/ECHOUE, date_envoi, cout)
- `CampagneSMS` (libelle, cible: CLASSE/NIVEAU/TOUS, contenu, date_programmee, envoyee_par)
- `Conversation` (sujet, participants, date_creation)
- `MessageInterne` (conversation, auteur, contenu, date, lu_par)

---

### 6. Finances Avancées & Paiement en Ligne

> **Priorité : 🟡 Moyenne** — Extension naturelle du module finances existant.

#### 6.1 Paiement en ligne par Mobile Money

| Fonctionnalité | Détail |
|---|---|
| Intégration API | MTN MoMo, Moov Money, ou agrégateur (Kkiapay, FedaPay, PayDunya) |
| Lien de paiement | Envoyé par SMS ou affiché sur le portail parents |
| Réconciliation automatique | Webhook → échéance soldée → reçu PDF généré instantanément |
| Sécurisation | Signature HMAC des callbacks, vérification du montant |

#### 6.2 Journal de caisse & Dépenses

| Fonctionnalité | Détail |
|---|---|
| Suivi des dépenses | Achats de fournitures, factures eau/électricité, maintenance, carburant bus |
| Catégories de dépenses | Paramétrable (fonctionnement, investissement, personnel, urgences) |
| Clôture journalière | Solde théorique vs solde réel en caisse physique, écart à justifier |
| Bilan financier global | Recettes (scolarité) – Dépenses = Résultat, par mois et par année |

**Modèles à créer :**
- `TransactionMobileMoney` (paiement, reference_externe, operateur, numero_telephone, statut_api, date_confirmation)
- `CategoriDepense` (libelle, type: FONCTIONNEMENT/INVESTISSEMENT/PERSONNEL)
- `Depense` (categorie, libelle, montant, date, justificatif, enregistre_par)
- `ClotureCaisse` (date, solde_theorique, solde_reel, ecart, justification_ecart, cloture_par)

---

### 7. Admissions & Portail de Pré-inscription en Ligne

> **Priorité : 🟡 Moyenne** — Gain de temps considérable à chaque rentrée scolaire.

**App suggérée :** `admissions`

| Fonctionnalité | Détail |
|---|---|
| Formulaire public | Dépôt de dossier en ligne par les nouvelles familles (état civil, pièces, bulletins) |
| Workflow de traitement | Dossier reçu → En examen → Convoqué pour test → Admis → Inscription définitive |
| Tests d'entrée | Gestion des épreuves, notes de sélection, classement |
| Notification au parent | E-mail/SMS à chaque changement de statut du dossier |

**Modèles à créer :**
- `DemandeAdmission` (nom, prenoms, date_naissance, niveau_souhaite, classe_origine, etablissement_origine, statut: RECUE/EN_EXAMEN/CONVOQUEE/ADMISE/REFUSEE, date_soumission)
- `PieceJustificativeAdmission` (demande, type_piece, fichier)
- `TestAdmission` (demande, date, note, observations)

---

## III. Synthèse comparative

| Domaine | État Actuel | À ajouter |
|---|:---:|---|
| **Authentification & Droits** | ✅ | Rôles Surveillant général, Infirmière, Responsable cantine |
| **Paramétrage Académique** | ✅ | — (complet) |
| **Gestion des Élèves** | ✅ | Portail de pré-inscription en ligne |
| **Personnel & Emploi du temps** | ✅ | — (complet) |
| **Pédagogie & Notes** | ✅ | Cahier de textes, Devoirs à domicile, Livret de compétences APC (primaire) |
| **Finances & Facturation** | ✅ | Paiement en ligne Mobile Money, Suivi des dépenses/charges, Clôture de caisse |
| **Documents Administratifs** | ✅ | — (complet) |
| **Tableaux de Bord** | ✅ | Indicateurs assiduité, discipline, santé |
| **Portail Parents** | ✅ | Messagerie, Cahier de textes, Devoirs, Cantine |
| **Vie Scolaire & Discipline** | ❌ | Pointage présences/retards, Justificatifs, Punitions, Retenues, Conseils de discipline |
| **Services Annexes** | ❌ | Cantine, Transport scolaire, Infirmerie/Santé, Bibliothèque/CDI |
| **Communication Temps Réel** | ⚠️ (e-mail seul) | SMS en masse, Messagerie interne Parents ↔ Enseignants |
| **Spécificités Primaire** | ⚠️ (partiel) | Maître unique, Carnet de liaison, Garderie périscolaire, Évaluation APC |
| **Spécificités Collège** | ⚠️ (partiel) | Conseils de classe & mentions, Délégués, Examens blancs, Orientation |
| **Admissions** | ❌ | Formulaire public, Workflow de traitement, Tests d'entrée |

**Légende :** ✅ Fonctionnel — ⚠️ Partiel — ❌ Absent

---

## IV. Prochaines étapes suggérées

Classement par **valeur ajoutée** et **fréquence d'utilisation quotidienne** :

| Priorité | Module | Raison |
|:---:|---|---|
| 🔴 **1** | **Vie scolaire** (`viescolaire`) | L'appel est fait **chaque heure** de chaque jour — c'est l'action la plus fréquente dans un établissement |
| 🔴 **2** | **Cahier de textes** (`cahier_texte`) | Obligation légale dans de nombreux pays, utilisé quotidiennement par chaque enseignant |
| 🟠 **3** | **Communication SMS** (`communication`) | Les alertes d'absence et les relances de paiement ont un impact immédiat |
| 🟠 **4** | **Spécificités pédagogiques** | Conseils de classe (collège) et livret APC (primaire) — utilisés chaque trimestre |
| 🟡 **5** | **Cantine** (`cantine`) | Très demandé si l'établissement a une cantine (50%+ des écoles) |
| 🟡 **6** | **Santé / Infirmerie** (`sante`) | Gestion des fiches médicales et passages — exigence de sécurité |
| 🟡 **7** | **Finances avancées** | Paiement Mobile Money et journal de caisse — gain de temps comptable |
| 🔵 **8** | **Transport** (`transport`) | Utile uniquement si l'établissement gère ses propres bus |
| 🔵 **9** | **Bibliothèque** (`bibliotheque`) | Optionnel selon la taille de l'établissement |
| 🔵 **10** | **Admissions en ligne** (`admissions`) | Utile surtout lors des périodes de rentrée (saisonnier) |

---

> **Ce document sert de feuille de route vivante.** Chaque module validé sera intégré au code source et documenté dans le `README.md` principal.
