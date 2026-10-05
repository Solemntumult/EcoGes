# EcoGes (Gestion Scolaire) — Plateforme Intégrée de Gestion d'Établissement Scolaire

Application web complète développée avec **Django 5.2**, **PostgreSQL 16**, **Celery**, **Redis** et **Docker**, permettant de gérer de bout en bout la vie administrative, pédagogique, financière et parascolaire d'un établissement scolaire : inscriptions, scolarité et paiements, notes et bulletins, fiches de paie, vie scolaire, cahier de texte, cantine, santé, transport, bibliothèque et génération des documents officiels.

Ce dépôt concrétise l'implémentation technique du [cahier des charges](#-documentation-associée) du projet et son extension modulaire moderne (architecture type PRONOTE / Single-Tenant d'établissement).

---

## Sommaire

- [Fonctionnalités & Modules](#-fonctionnalités--modules)
- [Stack technique](#-stack-technique)
- [Architecture du projet](#-architecture-du-projet)
- [Modèle de données & Architecture Single-Tenant](#-modèle-de-données--architecture-single-tenant)
- [Prérequis](#-prérequis)
- [Démarrage rapide avec Docker (Recommandé)](#-démarrage-rapide-avec-docker-recommandé)
- [Installation locale sans Docker](#-installation-locale-sans-docker)
- [Configuration des variables d'environnement (.env)](#-configuration-des-variables-denvironnement-env)
- [Traitements asynchrones (Celery & Redis)](#-traitements-asynchrones-celery--redis)
- [Sécurité & Cookies](#-sécurité--cookies)
- [Rôles et permissions](#-rôles-et-permissions)
- [Interfaces métier & URLs](#-interfaces-métier--urls)
- [Structure détaillée des applications](#-structure-détaillée-des-applications)
- [Commandes utiles & Jeu de démonstration](#-commandes-utiles--jeu-de-démonstration)
- [Règles métier clés](#-règles-métier-clés)
  - [Emploi du temps & rémunérations](#emploi-du-temps--rémunérations)
  - [Matières & coefficients (Règle béninoise)](#matières--coefficients-règle-béninoise)
  - [Moteur de rendu PDF (WeasyPrint)](#moteur-de-rendu-pdf-weasyprint)
- [Roadmap & État d'avancement](#-roadmap--état-davancement)
- [Documentation associée](#-documentation-associée)

---

## Fonctionnalités & Modules

Le projet couvre 17 modules spécialisés :

| Module | Périmètre et fonctionnalités clés |
|---|---|
| **Comptes & sécurité** | Authentification sécurisée, 7 rôles métier, verrouillage anti-bruteforce, journal d'audit complet |
| **Paramétrage** | Années scolaires, trimestres/semestres, niveaux & séries officielles (A1, A2, B, C, D, E, F1-F4...), classes, matières, coefficients par couple (matière, classe), grilles tarifaires, barème, horaires et pauses |
| **Élèves** | Inscription, réinscription, dossier scolaire complet, matricule auto-généré, fiches tuteurs |
| **Personnel & Paie** | Dossiers enseignants et administratifs, affectations classe/matière avec tarifs horaires, éditeur d'emploi du temps avec détection des conflits de créneaux/salles, calcul automatique des rémunérations et fiches de paie |
| **Évaluations & Notes** | Saisie des devoirs/compositions, verrouillage par période, calcul automatique des moyennes, classements et génération des bulletins PDF |
| **Finances & Caisse** | Échéanciers de scolarité, encaissements multi-modes (espèces, virement, mobile money), imputation FIFO, bourses et remises, annulations contrôlées, états de caisse |
| **Facturation & Reçus** | Factures numérotées, reçus de paiement horodatés avec QR-Code de vérification |
| **Documents officiels** | Certificats de scolarité, attestations, listes de classe, convocations, cartes d'identité scolaires — éditeur de gabarits avec aperçu temps réel et génération PDF/Word/HTML |
| **Statistiques & KPIs** | Tableaux de bord de direction (effectifs, recouvrement, alertes impayés, pyramide des âges, graphiques Chart.js) |
| **Portail Famille** | Espace de consultation en ligne pour les parents et élèves (notes, emploi du temps, situation financière) |
| **Vie Scolaire** | Feuilles d'appel par heure/créneau, suivi des absences, retards, dispenses, sanctions et retenues |
| **Cahier de Texte** | Journal de classe numérique par séance, leçons dispensées, devoirs à la maison et pièces jointes |
| **Messagerie & Communication** | Messagerie interne sécurisée entre direction, enseignants et parents, notifications et annonces |
| **Cantine Scolaire** | Gestion des menus hebdomadaires, régimes alimentaires, abonnements et pointage des repas |
| **Infirmerie & Santé** | Fiches médicales élèves (allergies, vaccins, contacts urgence), registre des passages à l'infirmerie |
| **Transport Scolaire** | Lignes de transport, arrêts de ramassage, chauffeurs et affectation des élèves par circuit |
| **Bibliothèque / CDI** | Catalogue des ouvrages (ISBN, auteur, catégorie), gestion des exemplaires, prêts et retours |
| **Admissions en ligne** | Dépôt des dossiers de candidature, pièces justificatives et arbitrage des admissions |

---

## Stack technique

- **Framework Web** : [Django 5.2](https://www.djangoproject.com/) (Python 3.12+)
- **Base de données principale** : **PostgreSQL 16** (moteur par défaut, typages avancés, index B-Tree & composites)
- **Base de données alternative** : MySQL 8.x (supporté via configuration dans `.env` / `settings.py`)
- **Tâches asynchrones & Cache** : **Celery 5.4** orchestré avec **Redis 7** (broker & backend de résultats)
- **Conteneurisation** : **Docker & Docker Compose** (orchestration multi-services prête pour la production)
- **Génération de documents** : [WeasyPrint 63](https://weasyprint.org/) (bulletins, factures, reçus, attestations), [python-docx](https://python-docx.readthedocs.io/) (Word), [openpyxl](https://openpyxl.readthedocs.io/) (Excel), [qrcode](https://pypi.org/project/qrcode/)
- **Frontend & Design** : HTML5, Bootstrap 5 épuré ("Neo-Precision", bordures 0px strictes), HTMX (interactivité dynamique), Chart.js, typographie Google Font Inter

---

## Architecture du projet

```
EcoGes/
├── docker-compose.yml          # Orchestration des conteneurs (web, db, redis, celery_worker)
├── Dockerfile                  # Image Docker Python 3.12-slim avec dépendances WeasyPrint et C
├── requirements.txt            # Dépendances Python (Django, psycopg2, celery, redis, weasyprint...)
├── .env.example                # Modèle de variables d'environnement
├── manage.py                   # Point d'entrée des commandes Django
│
├── gestion_scolaire/           # Configuration globale (settings, urls, celery.py, wsgi/asgi)
│
├── comptes/                    # Utilisateurs, 7 rôles métier, journal d'audit
├── parametrage/                # Années scolaires, niveaux, séries, classes, matières, coefficients, tarifs
├── eleves/                     # Fiches élèves, tuteurs, inscriptions, dossiers
├── personnel/                  # Enseignants, affectations, emplois du temps, fiches de paie
├── evaluations/                # Évaluations, notes, moyennes, rangs, bulletins de notes
├── finances/                   # Échéanciers, paiements, caisse, factures, reçus, remises
├── documents/                  # Éditeur de modèles et génération de documents administratifs
├── statistiques/               # KPIs, tableaux de bord de direction et rapports
├── portail/                    # Espace famille / élève en lecture seule
│
├── viescolaire/                # Feuilles d'appel, suivi des absences, retards et sanctions
├── cahier_texte/               # Séances de cours, travail à faire, progression pédagogique
├── communication/              # Messagerie interne et diffusion d'annonces
├── cantine/                    # Formules, menus hebdomadaires et inscriptions repas
├── sante/                      # Registre de l'infirmerie, fiches médicales, allergies
├── transport/                  # Lignes de bus, arrêts, inscriptions aux circuits
├── bibliotheque/               # Catalogue des livres du CDI, gestion des emprunts
└── admissions/                 # Formulaire de candidature et validation des dossiers
```

---

## Modèle de données & Architecture Single-Tenant

L'application suit une architecture **Single-Tenant d'établissement** (modèle PRONOTE) :
- Chaque établissement scolaire dispose de son instance et de sa base de données isolée.
- Fonctionnement autonome **garanti sur réseau local (LAN)**, même en cas de coupure de connexion Internet.
- Optimisation des index (`django-index-design`) sur toutes les clés de recherche fréquentes (`Eleve`, `Paiement`, `Evaluation`, `Inscription`, `JournalActivite`).
- Verrous de cohérence sur les opérations financières pour prévenir tout risque de double imputation.

---

## Prérequis

### Option A : Déploiement Docker (Conseillé)
- [Docker](https://docs.docker.com/get-docker/) et [Docker Compose](https://docs.docker.com/compose/) installés sur votre machine (Windows, macOS ou Linux).

### Option B : Installation Locale Standard
- **Python 3.11** ou supérieur
- **PostgreSQL 16** (ou MySQL 8.x)
- **Redis 7** (nécessaire pour exécuter Celery et le cache)
- Runtime **GTK3** (pour le rendu PDF WeasyPrint sous Windows) ou paquets Cairo/Pango sous Linux

---

## Démarrage rapide avec Docker (Recommandé)

Le moyen le plus simple et le plus rapide pour démarrer le projet sans installer de dépendances système complexes (PostgreSQL, Redis, GTK3) est d'utiliser Docker Compose.

```bash
# 1. Cloner le projet
git clone <url-du-depot>
cd EcoGes

# 2. Préparer le fichier de configuration
cp .env.example .env

# 3. Construire et démarrer les conteneurs (web, db, redis, celery_worker)
docker compose up -d --build

# 4. Appliquer les migrations de base de données
docker compose exec web python manage.py migrate

# 5. Créer les groupes de permissions par défaut
docker compose exec web python manage.py creer_groupes

# 6. (Optionnel) Charger le jeu complet de données de démonstration
docker compose exec web python manage.py creer_demo

# 7. Créer un compte super-administrateur
docker compose exec web python manage.py createsuperuser
```

L'application est immédiatement accessible :
- **Application Web** : [http://localhost:8000](http://localhost:8000)
- **Console d'administration** : [http://localhost:8000/admin/](http://localhost:8000/admin/)

Pour consulter les logs en temps réel :
```bash
docker compose logs -f web celery_worker
```

Pour arrêter la pile :
```bash
docker compose down
```

---

## Installation locale sans Docker

Si vous préférez exécuter le projet directement dans votre terminal local :

### 1. Environnement Python & Dépendances

```bash
# 1. Créer et activer l'environnement virtuel
python -m venv venv
# Sous Windows :
venv\Scripts\activate
# Sous Linux / macOS :
source venv/bin/activate

# 2. Installer les packages
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Base de données PostgreSQL

1. Installez PostgreSQL et créez la base de données :
   ```sql
   CREATE DATABASE gestion_scolaire;
   CREATE USER postgres WITH ENCRYPTED PASSWORD 'postgres';
   GRANT ALL PRIVILEGES ON DATABASE gestion_scolaire TO postgres;
   ```
2. Adaptez votre fichier `.env` :
   ```dotenv
   DB_NAME=gestion_scolaire
   DB_USER=postgres
   DB_PASSWORD=postgres
   DB_HOST=127.0.0.1
   DB_PORT=5432
   ```

*(Si vous souhaitez utiliser MySQL à la place de PostgreSQL, commentez le bloc PostgreSQL et décommentez le bloc MySQL dans `gestion_scolaire/settings.py` et dans `requirements.txt`).*

### 3. Migrations & Données initiales

```bash
python manage.py migrate
python manage.py creer_groupes
python manage.py creer_demo              # Peuple automatiquement la base
python manage.py createsuperuser         # Crée votre accès administrateur
```

### 4. Lancement des services

Dans des fenêtres de terminal distinctes :

```bash
# Terminal 1 : Serveur Web Django
python manage.py runserver

# Terminal 2 : Worker Celery (si Redis est lancé)
celery -A gestion_scolaire worker -l info
```

---

## Configuration des variables d'environnement (.env)

Toutes les options de configuration sont personnalisables via `.env` :

```dotenv
# Sécurité & Debug
DJANGO_SECRET_KEY=cle-secrete-ultra-longue-et-aleatoire
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,web

# Base de Données (PostgreSQL par défaut)
DB_NAME=gestion_scolaire
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db                 # Utilisez '127.0.0.1' si vous tournez hors Docker
DB_PORT=5432

# File de tâches asynchrone (Celery & Redis)
CELERY_BROKER_URL=redis://redis:6379/0      # redis://127.0.0.1:6379/0 hors Docker
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Envoi d'e-mails (SMTP)
DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend  # ou smtp
DJANGO_EMAIL_HOST=smtp.gmail.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_USER=votre-email@gmail.com
DJANGO_EMAIL_PASSWORD=votre-mot-de-passe-d-application
DJANGO_EMAIL_USE_TLS=True
DJANGO_DEFAULT_FROM_EMAIL=Gestion Scolaire <no-reply@votredomaine.com>
```

> **Mode Développement** : avec `DJANGO_EMAIL_BACKEND=console`, les e-mails générés s'affichent directement dans le flux de logs sans requérir de serveur SMTP.

---

## Traitements asynchrones (Celery & Redis)

Le projet intègre nativement **Celery 5.4** configuré avec **Redis** pour fluidifier l'expérience utilisateur :
- Génération en masse des bulletins de notes PDF de fin de trimestre.
- Envoi groupé des quittances, reçus d'encaissement et relances d'impayés par e-mail.
- Suivi et historique d'exécution via `django-celery-results`.
- Configuration de tolérance aux pannes (`task_acks_late = True`, time-limit stricte à 30 minutes, `prefetch_multiplier = 1`).

---

## Sécurité & Cookies

La sécurité a été renforcée selon les recommandations `django-security` :
- **Protection des sessions** : `SESSION_COOKIE_HTTPONLY = True`, `SameSite = 'Lax'`.
- **Protection anti-détournement** : `X_FRAME_OPTIONS = "SAMEORIGIN"` (permet la prévisualisation des PDF dans les modales tout en empêchant le détournement de clic).
- **Protection XSS & Sniffing MIME** : `SECURE_CONTENT_TYPE_NOSNIFF = True`, `SECURE_BROWSER_XSS_FILTER = True`.
- **Verrouillage de compte** : blocage temporaire automatique après 5 tentatives infructueuses pendant 30 minutes (`VERROUILLAGE_TENTATIVES = 5`).
- **Production (`DEBUG = False`)** : bascule automatique vers `SECURE_SSL_REDIRECT = True`, `SESSION_COOKIE_SECURE = True`, et HSTS activé (`31536000` secondes avec `includeSubDomains`).

---

## Rôles et permissions

Le modèle `Utilisateur` (app `comptes`) intègre 7 rôles correspondant au fonctionnement hiérarchique d'un établissement :

| Rôle | Code | Périmètre d'accès |
|---|---|---|
| **Administrateur / Direction** | `ADMIN` | Accès intégral, statistiques, validations stratégiques, clôtures |
| **Censeur / Dir. Études** | `CENSEUR` | Emplois du temps, affectations, validation des notes, délibérations |
| **Secrétariat** | `SECRETARIAT` | Inscriptions, gestion des dossiers élèves, certificats et attestations |
| **Comptable / Caisse** | `COMPTABLE` | Scolarité, quittances, encaissements, états de caisse, fiches de paie |
| **Enseignant** | `ENSEIGNANT` | Saisie des notes, cahier de texte, feuilles d'appel et devoirs |
| **Parent / Élève** | `PARENT` | Consultation du dossier scolaire, notes, factures acquittées, absences |
| **Super-administrateur** | `SUPERADMIN` | Maintenance système, sauvegardes de base, journalisation d'audit |

---

## Interfaces métier & URLs

Outre l'interface Django native accessible sur `/admin/`, l'application propose des espaces métiers dédiés :

| Espace | URL | Description |
|---|---|---|
| **Tableau de Bord Exécutif** | `/` | Vue synthétique de direction (KPIs, effectifs, recouvrement, journal) |
| **Élèves & Dossiers** | `/eleves/` | Liste, création, transfert, consultation et réinscriptions |
| **Finances & Scolarité** | `/finances/` | Encaissements, impayés, états de caisse, remises et relances |
| **Évaluations & Bulletins** | `/evaluations/` | Saisie des notes, délibérations, génération des bulletins PDF |
| **Personnel & Paie** | `/personnel/` | Enseignants, créneaux d'emploi du temps, fiches de paie |
| **Paramétrage** | `/parametrage/` | Niveaux, séries, classes, matières, coefficients, horaires |
| **Documents officiels** | `/documents/` | Éditeur WYSIWYG de gabarits, certificats, cartes scolaires |
| **Statistiques & Rapports** | `/statistiques/` | Indicateurs de performance, taux de réussite, bilan financier |
| **Vie Scolaire** | `/vie-scolaire/` | Feuilles d'appel, gestion des absences, retards et retenues |
| **Cahier de Texte** | `/cahier-texte/` | Séances quotidiennes, travail à domicile, pièces jointes |
| **Messagerie interne** | `/communication/` | Échanges sécurisés direction / enseignants / familles |
| **Cantine Scolaire** | `/cantine/` | Menus, allergènes, abonnements et pointage |
| **Santé & Infirmerie** | `/sante/` | Registre médical, dispenses, passages infirmerie |
| **Transport** | `/transport/` | Circuits de ramassage, arrêts et élèves assignés |
| **Bibliothèque (CDI)** | `/bibliotheque/` | Catalogue des livres, prêts en cours, retards |
| **Admissions** | `/admissions/` | Dépôt et instruction des dossiers d'admission |
| **Portail Famille** | `/portail/` | Espace élève / parent en consultation sécurisée |

---

## Structure détaillée des applications

| App | Modèles principaux |
|---|---|
| `comptes` | `Utilisateur`, `JournalActivite` |
| `parametrage` | `AnneeScolaire`, `Periode`, `Niveau`, `Serie`, `Classe`, `Matiere`, `ClasseMatiereCoefficient`, `GrilleTarifaire`, `HoraireJournalier`, `PauseHoraire`, `Etablissement` |
| `eleves` | `Eleve`, `Tuteur`, `Inscription` |
| `personnel` | `Personnel`, `Affectation` (avec `tarif_horaire`), `CreneauEmploiDuTemps`, `DisponibiliteEnseignant` |
| `evaluations` | `Evaluation`, `Note`, `Bulletin`, `DetailBulletin` |
| `finances` | `Echeance`, `Paiement`, `ImputationPaiement`, `Facture`, `Recu`, `Remise`, `FicheDePaie`, `ClotureCaisse` |
| `documents` | `ModeleDocument`, `DocumentAdministratif` |
| `statistiques` | Services d'agrégation, calculs de taux et projections analytiques |
| `portail` | Vues sécurisées et tableau de bord parent/élève |
| `viescolaire` | `FeuilleAppel`, `LigneAppel`, `IncidentDiscipline`, `Sanction` |
| `cahier_texte` | `CahierDeTexte`, `SeanceCours`, `DevoirMaison` |
| `communication` | `Conversation`, `MessageInterne`, `AnnonceGenerale` |
| `cantine` | `MenuCantine`, `Plat`, `InscriptionCantine`, `PointageRepas` |
| `sante` | `FicheMedicale`, `PassageInfirmerie`, `ProtocoleUrgence` |
| `transport` | `LigneTransport`, `ArretTransport`, `AbonnementTransport` |
| `bibliotheque` | `Ouvrage`, `Exemplaire`, `Emprunt` |
| `admissions` | `DossierAdmission`, `PieceJointeAdmission` |

---

## Commandes utiles & Jeu de démonstration

```bash
# Créer les groupes et permissions initiales
python manage.py creer_groupes

# Créer des données de test complètes (élèves, évaluations, paiements, emplois du temps)
python manage.py creer_demo              # Création standard
python manage.py creer_demo --reset      # Réinitialiser puis reconstruire
python manage.py creer_demo --eleves 10  # Définir le nombre d'élèves par classe

# Exécuter la suite de tests automatisés (avec SQLite en mémoire pour rapidité)
python manage.py test --settings=gestion_scolaire.settings_test

# Exécuter les tests sur la base PostgreSQL
python manage.py test

# Sauvegarder la base de données
python manage.py sauvegarde_db
```

### Comptes de démonstration préconfigurés

Après l'exécution de `creer_demo`, vous pouvez vous connecter avec :

- **Direction / Admin** : `admin` / `Admin123!`
- **Secrétariat** : `secre` / `secre123!`
- **Comptabilité / Caisse** : `caisse` / `caisse123!`
- **Censeur** : `censeur` / `censeur123!`
- **Enseignant** : `prof` / `prof123!`

---

## Règles métier clés

### Emploi du temps & rémunérations
- **Horaires scolaires** : configuration des créneaux actifs (journée continue ou coupée) et calcul automatique des plages horaires entre les pauses récréatives.
- **Grille & détection des conflits** : contrôle instantané empêchant qu'un enseignant, une classe ou une salle ne soit assigné deux fois au même créneau horaire.
- **Calcul de rémunération** : `heures de cours hebdomadaires × tarif horaire affecté × 4,33`, avec émission de la fiche de paie officielle et traçabilité comptable.

### Matières & coefficients (Règle béninoise)
> **Règle fondamentale** : un coefficient n'appartient pas à une matière de manière isolée, mais au **couple (matière, classe)**. Une même matière peut avoir un coefficient différent d'une classe à l'autre au sein d'une même série.
- Prise en charge des séries officielles du second cycle (A1, A2, B, C, D, E, F1-F4, G1-G3, EA).
- Option **Tronc commun** qui lie automatiquement la matière aux classes du niveau par signal Django.

### Moteur de rendu PDF (WeasyPrint)
- Génération au format vectoriel haute fidélité des bulletins, factures, quittances et cartes d'identité scolaires.
- **Sous Docker** : préinstallé et configuré avec toutes les polices et dépendances C nécessaires.
- **Sous Windows natif** : nécessite le runtime [GTK3 for Windows](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases). En cas d'absence, le système bascule automatiquement sur un export HTML imprimable.

---

## Roadmap & État d'avancement

- [x] Refonte de l'interface en design "Neo-Precision" (0px border-radius, pure typographie Inter)
- [x] Migration de la base de données vers PostgreSQL 16
- [x] Conteneurisation complète multi-services avec Docker & Docker Compose
- [x] Intégration de Celery 5.4 et Redis pour l'asynchronisme
- [x] Optimisation des index de base de données (`django-index-design`)
- [x] Durcissement des cookies et de la sécurité applicative (`django-security`)
- [x] Ajout des 8 nouveaux modules scolaires (Vie scolaire, Cahier de texte, Cantine, Santé, Transport, Bibliothèque, Communication, Admissions)
- [x] Authentification avec verrouillage anti-bruteforce et journal d'audit
- [ ] API REST (Django REST Framework) pour futures applications mobiles parents/professeurs
- [ ] Module de synchronisation hors-ligne (mode hybride Intranet / Cloud)

---

## Documentation associée

- **Cahier des charges fonctionnel** : `Cahier_des_charges_Gestion_Scolaire.docx`
- **Bilan technique des apports** : `BILAN_APPORTS.md`
- **Feuille de route d'amélioration** : `Etat_amelioration.md`

---

## Licence

Projet sous licence propriétaire — Réservé à l'établissement exploitant.
