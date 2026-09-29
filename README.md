# Gestion Scolaire — Plateforme Intégrée de Gestion d'École

Application web développée avec **Django** et **MySQL** permettant de gérer de bout en bout la vie administrative, pédagogique et financière d'un établissement scolaire : inscription des élèves, notes et bulletins, scolarité et paiements, facturation, et génération des documents administratifs.

Ce dépôt est l'implémentation technique du [cahier des charges](#-documentation-associée) du projet (45 cas d'utilisation couvrant 9 modules fonctionnels).

---

## Sommaire

- [Fonctionnalités](#-fonctionnalités)
- [Stack technique](#-stack-technique)
- [Architecture du projet](#-architecture-du-projet)
- [Modèle de données](#-modèle-de-données)
- [Prérequis](#-prérequis)
- [Installation](#-installation)
- [Configuration de la base de données (MySQL / phpMyAdmin)](#-configuration-de-la-base-de-données-mysql--phpmyadmin)
- [Lancer le projet](#-lancer-le-projet)
- [Rôles et permissions](#-rôles-et-permissions)
- [Structure des apps](#-structure-des-apps)
- [Commandes utiles](#-commandes-utiles)
- [Roadmap](#-roadmap)
- [Documentation associée](#-documentation-associée)

---

## Fonctionnalités

| Module | Fonctionnalités clés |
|---|---|
| **Comptes & sécurité** | Authentification, rôles (admin, censeur, secrétariat, comptable, enseignant, parent), journal d'activité |
| **Paramétrage** | Années scolaires, périodes, niveaux (+ séries du second cycle : A1, C, D, F1...), classes, matières, coefficients par couple (matière, classe), grilles tarifaires, barème de notation, horaires scolaires (modes + pauses) |
| **Élèves** | Inscription, réinscription, dossier élève, matricule auto-généré, tuteurs/parents |
| **Personnel** | Fiches enseignants/staff, affectations classe/matière (avec tarif horaire), éditeur d'emploi du temps par classe (grille + détection de conflits), rémunérations automatiques et fiches de paie |
| **Évaluations** | Saisie des notes, verrouillage par période, calcul des moyennes et rangs, génération des bulletins PDF |
| **Finances** | Échéanciers, paiements multi-modes, imputation FIFO, remises/bourses, annulation/remboursement |
| **Facturation** | Factures numérotées automatiquement, reçus de paiement PDF |
| **Documents** | Certificats de scolarité, attestations, listes de classe, convocations, cartes scolaires — via modèles personnalisables, éditeur avec aperçu temps réel, exports PDF/Word/HTML et envoi par e-mail |
| **Statistiques** | Tableaux de bord (effectifs, taux de recouvrement, moyennes), exports PDF/Excel |

> L'ensemble de ces données est d'ores et déjà géré via **l'interface d'administration Django** (`/admin/`), pleinement fonctionnelle dès l'installation. Les interfaces métier dédiées à chaque profil (secrétariat, comptabilité, enseignant...) constituent la prochaine étape de développement (voir [Roadmap](#-roadmap)).

---

## Stack technique

- **Back-end** : [Django](https://www.djangoproject.com/) (Python)
- **Base de données** : MySQL, administrable via **phpMyAdmin**
- **Génération de PDF** : [WeasyPrint](https://weasyprint.org/) (bulletins, factures, reçus, documents administratifs) à partir de gabarits HTML/CSS
- **Gestion des images** : Pillow (photos d'élèves, logos)
- **Configuration** : variables d'environnement via `python-dotenv` / `.env`

---

## Architecture du projet

Le projet est découpé en **8 applications Django** faiblement couplées, chacune correspondant à un module métier du cahier des charges :

```
gestion_scolaire/
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── gestion_scolaire/        # Configuration du projet (settings, urls, wsgi/asgi)
│
├── comptes/                 # Utilisateurs, rôles, journal d'activité
├── parametrage/             # Années scolaires, niveaux, classes, matières, tarifs, barème
├── eleves/                  # Élèves, tuteurs, inscriptions
├── personnel/                # Enseignants/staff, affectations, emploi du temps
├── evaluations/               # Évaluations, notes, bulletins
├── finances/                 # Échéances, paiements, factures, reçus, remises
├── documents/                # Documents administratifs et modèles/gabarits
└── statistiques/              # Vues et services d'agrégation (tableaux de bord)
```

Chaque app suit la structure Django standard : `models.py`, `admin.py`, `migrations/`, `views.py`, `apps.py`.

---

## Modèle de données

Les entités principales et leurs relations sont détaillées dans le cahier des charges (section *Modèle conceptuel de données*). En résumé :

- Un **Élève** possède plusieurs **Inscriptions** (une par année scolaire).
- Une **Inscription** rattache l'élève à une **Classe** et génère un ensemble d'**Échéances**.
- Chaque règlement crée un **Paiement**, imputé sur une ou plusieurs échéances, et donne lieu à un **Reçu**.
- Les **Notes** sont rattachées à une **Évaluation** (matière/classe/période) et agrégées pour produire un **Bulletin**.
- Chaque document émis est tracé dans **DocumentAdministratif** et dans le **JournalActivite**.

Le schéma physique complet (tables, clés étrangères, index) est généré automatiquement par les migrations Django et consultable/administrable directement dans **phpMyAdmin** après la première migration.

---

## Prérequis

- Python 3.11 ou supérieur
- MySQL Server 8.x et phpMyAdmin (ex. via [XAMPP](https://www.apachefriends.org/), [WAMP](https://www.wampserver.com/) ou une installation MySQL + phpMyAdmin séparée)
- pip et virtualenv (ou `venv`, inclus avec Python)
- Sur Linux/macOS, pour `mysqlclient` : les paquets système `default-libmysqlclient-dev` (ou `mysql-devel`) et `build-essential`/`gcc` doivent être installés au préalable :
  ```bash
  # Debian/Ubuntu
  sudo apt-get install default-libmysqlclient-dev build-essential pkg-config

  # macOS (Homebrew)
  brew install mysql-client pkg-config
  ```

---

## Installation

```bash
# 1. Cloner le dépôt
git clone <url-du-depot>
cd gestion_scolaire

# 2. Créer et activer un environnement virtuel
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Copier le fichier d'environnement et l'adapter
cp .env.example .env
```

Éditez ensuite `.env` avec les informations de connexion à votre base MySQL (voir section suivante) et une clé secrète Django propre à votre environnement.

---

## Configuration de la base de données (MySQL / phpMyAdmin)

1. **Créer la base de données** via phpMyAdmin :
   - Onglet **Bases de données** → nom : `gestion_scolaire` (ou celui choisi dans `.env`) → interclassement `utf8mb4_unicode_ci` → **Créer**.
2. **Créer un utilisateur MySQL dédié** (recommandé plutôt que `root` en production) via l'onglet **Comptes utilisateurs** de phpMyAdmin, avec tous les droits sur la base créée.
3. **Renseigner `.env`** avec le nom de la base, l'utilisateur, le mot de passe, l'hôte (`127.0.0.1` en local) et le port (`3306` par défaut).
4. **Appliquer les migrations** (crée automatiquement toutes les tables) :
   ```bash
   python manage.py migrate
   ```
5. Les tables apparaissent alors dans phpMyAdmin, dans la base sélectionnée, prêtes à être consultées, sauvegardées (onglet **Exporter**) ou restaurées (onglet **Importer**).

---

## Lancer le projet

```bash
# Créer un compte administrateur
python manage.py createsuperuser

# Lancer le serveur de développement
python manage.py runserver
```

- Application : http://127.0.0.1:8000/
- Interface d'administration (gestion complète des données) : http://127.0.0.1:8000/admin/

---

## Envoi d'e-mails (SMTP)

La plateforme peut envoyer des e-mails pour :
- la **réinitialisation de mot de passe** (lien « Mot de passe oublié » sur la page de connexion) ;
- l'**envoi de documents** (certificats, attestations, relances...) directement depuis l'éditeur de documents, le dossier élève ou l'historique — le document est généré en PDF (ou HTML si WeasyPrint est absent) et joint à l'e-mail.

La configuration se fait dans le fichier `.env` (voir `.env.example`) :

```dotenv
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=smtp.gmail.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_USER=votre.adresse@gmail.com
DJANGO_EMAIL_PASSWORD=votre-mot-de-passe-application
DJANGO_EMAIL_USE_TLS=True
DJANGO_DEFAULT_FROM_EMAIL=Gestion Scolaire <votre.adresse@gmail.com>
```

> **Gmail** : générez un *mot de passe d'application* (Compte Google → Sécurité → Vérification en 2 étapes → Mots de passe des applications) et utilisez-le dans `DJANGO_EMAIL_PASSWORD`. Tant que `DJANGO_EMAIL_BACKEND` reste sur `console`, les e-mails s'affichent dans la console du serveur (aucun envoi réel) — idéal en développement.

---

## Rôles et permissions

Le modèle `Utilisateur` (app `comptes`) définit sept rôles correspondant aux acteurs du cahier des charges :

| Rôle | Code | Périmètre |
|---|---|---|
| Administrateur / Direction | `ADMIN` | Accès complet, paramétrage, supervision |
| Censeur / Direction des études | `CENSEUR` | Classes, emplois du temps, validation des notes, bulletins |
| Secrétariat | `SECRETARIAT` | Inscriptions, dossiers élèves, documents administratifs |
| Comptable / Caissier(ère) | `COMPTABLE` | Scolarité, paiements, factures, reçus, relances |
| Enseignant | `ENSEIGNANT` | Saisie des notes de ses matières/classes |
| Parent / Élève | `PARENT` | Consultation (portail, évolution future) |
| Super-administrateur technique | `SUPERADMIN` | Sauvegardes, administration système |

La granularité fine des permissions (lecture/écriture/suppression par module) s'appuie sur le système de **groupes et permissions natif de Django**, configurable dans `/admin/auth/group/`.

---

## Structure des apps

| App | Modèles principaux |
|---|---|
| `comptes` | `Utilisateur`, `JournalActivite` |
| `parametrage` | `AnneeScolaire`, `Periode`, `Niveau` (+ `Serie`), `Classe`, `Matiere`, `ClasseMatiereCoefficient`, `TypeFrais`, `GrilleTarifaire`, `BaremeEvaluation`, `HoraireJournalier`, `PauseHoraire`, `Etablissement`, `LogoEtablissement` |
| `eleves` | `Eleve`, `Tuteur`, `Inscription` |
| `personnel` | `Personnel`, `Affectation` (avec `tarif_horaire`), `CreneauEmploiDuTemps` |
| `evaluations` | `Evaluation`, `Note`, `Bulletin` |
| `finances` | `Echeance`, `Remise`, `Paiement`, `ImputationPaiement`, `Facture`, `LigneFacture`, `Recu`, `FicheDePaie` |
| `documents` | `ModeleDocument`, `DocumentAdministratif` |
| `statistiques` | *(pas de modèles propres — agrégations sur les autres apps)* |

---

## Commandes utiles

```bash
# Créer de nouvelles migrations après modification des modèles
python manage.py makemigrations

# Appliquer les migrations
python manage.py migrate

# Ouvrir un shell Django (accès direct aux modèles)
python manage.py shell

# Lancer les tests
python manage.py test

# Collecter les fichiers statiques (avant déploiement en production)
python manage.py collectstatic
```

---

## Roadmap

- [x] Vues et gabarits métier par rôle (secrétariat, comptabilité, enseignant, direction)
- [x] Authentification personnalisée (connexion, verrouillage de compte, réinitialisation de mot de passe)
- [x] Génération des bulletins, factures, reçus et documents administratifs en PDF (WeasyPrint)
- [x] Tableaux de bord statistiques (effectifs, recouvrement, résultats, graphiques Chart.js)
- [x] Portail parents/élèves en lecture seule
- [ ] File de tâches asynchrone (Celery) pour la génération en masse des bulletins/factures
- [ ] Notifications par e-mail/SMS (relances de paiement, publication des bulletins)
- [ ] Déploiement production (Gunicorn + Nginx, variables d'environnement sécurisées)

## Interfaces métier

Outre `/admin/`, l'application expose désormais une interface web complète :

| Rôle | Accueil après connexion |
|---|---|
| Secrétariat | Liste des élèves (`/eleves/`) |
| Comptabilité | Impayés & relances (`/finances/`) |
| Enseignant | Ses évaluations (`/evaluations/`) |
| Direction / Censeur | Tableau de bord (`/`) |
| Parent / Élève | Portail (`/portail/`) |

### Commandes utiles

```bash
# Créer les groupes de permissions par rôle (après la migration initiale)
python manage.py creer_groupes

# Jeu de données de démonstration complet (paramétrage + élèves + notes + paiements)
python manage.py creer_demo              # base vide : tout créer
python manage.py creer_demo --reset      # vider puis reconstruire
python manage.py creer_demo --eleves 8   # 8 élèves par classe

# Sauvegarder la base MySQL dans backups/ (UC-42)
python manage.py sauvegarde_db

# Lancer les tests SANS serveur MySQL (base SQLite en mémoire)
python manage.py test --settings=gestion_scolaire.settings_test

# Lancer les tests contre MySQL (production)
python manage.py test
```

### Jeu de données de démonstration

La commande `creer_demo` peuple toute la base en une seule fois pour tester
sans saisir les données à la main :

- **Paramétrage** : année scolaire 2026-2027 (courante), 3 trimestres, 5 niveaux/classes,
  matières avec coefficients, grille tarifaire, barème, 2 modes d'horaire (journée continue
  active 07:00–15:35, journée coupée 07:30–18:30) avec récréation (10:00–10:15) et pause déjeuner ;
- **Comptes** : `censeur/censeur123!`, `secre/secre123!`, `caisse/caisse123!`, `prof/prof123!`
  (l'admin existant est conservé) ;
- **Personnel** : 3 enseignants, affectations classe/matière avec tarifs horaires (3 000–4 000 F/h),
  emploi du temps aligné sur les plages de l'horaire actif, fiches de paie du mois courant ;
- **Élèves** : 30 élèves avec tuteurs, inscriptions et échéanciers (via le service métier) ;
- **Évaluations** : devoirs + compositions sur 3 périodes, ~1 000 notes, bulletins calculés ;
- **Finances** : paiements variés (payés / partiels / impayés via FIFO), reçus, factures, remises.

Comptes de démonstration : `admin / Admin123!`, `secre / secre123!`, `caisse / caisse123!`,
`censeur / censeur123!`, `prof / prof123!`.

### Emploi du temps & rémunérations

- **Horaires scolaires** (`Paramétrage → Horaires scolaires`) : créez les modes d'horaire de
  l'établissement (journée continue 07:00–15:35, journée coupée 07:30–18:30...) et ajustez les
  pauses (récréation, pause déjeuner) — leurs horaires exacts sont libres. Un seul mode est
  actif et s'applique à toutes les classes. Les plages de cours sont calculées automatiquement
  entre les pauses.
- **Éditeur d'emploi du temps par classe** (`Emploi du temps` → une classe) : grille éditable
  jour × plage horaire, chaque cellule = matière/enseignant + salle. La détection de conflits
  (enseignant, classe, salle déjà occupés) bloque l'enregistrement. Un formulaire « créneau
  libre » permet d'ajouter des cours hors grille standard.
- **Rémunérations** (`Rémunérations`, comptable/direction) : salaire calculé automatiquement =
  heures de cours (issues de l'emploi du temps) × tarif horaire de chaque affectation
  (enseignant + matière + classe), sur toutes les classes. Mois moyen : heures hebdo × 4,33.
  Génération de la **fiche de paie** (numérotée FP-…), encaissement (mode + date), bulletin PDF,
  annulation tant qu'elle n'est pas payée.

### Matières & coefficients (gestionnaire de bulletins)

**Règle métier : un coefficient n'appartient jamais à une matière seule — il
appartient toujours au couple (matière, classe).** La même matière peut donc
avoir un coefficient différent d'une classe à l'autre, même au sein d'une même
série.

- **Séries du second cycle** : liste officielle béninoise (A1, A2, B, C, D, E,
  F1-F4, G1-G3, EA) gérée dans `Paramétrage → Matières & coefficients`.
- **Niveaux & matières** : créez un niveau du premier cycle (sans série) ou du
  second cycle (avec série, ex. 2nde D), puis les matières par niveau.
- **Coefficients par classe** (`Matières & coefficients` → `Coefficients` d'une
  classe) : ajoutez une matière existante ou nouvelle à une classe précise avec
  son coefficient, modifiez-le sans effet de bord sur les autres classes, ou
  retirez la liaison.
- **Tronc commun** : une matière peut être marquée « tronc commun » (création
  ou bouton ★). Elle est alors **liée automatiquement** à toutes les classes de
  son niveau — à la création de la matière comme à la création d'une nouvelle
  classe de ce niveau (signal `post_save`). Les liaisons créées ne sont jamais
  supprimées automatiquement : le retrait reste une action manuelle par classe.
- Le moteur de bulletins pondère chaque matière par le coefficient du couple
  (classe, matière) — défaut 1 si aucune liaison n'est définie.

### Rendu PDF (WeasyPrint)

Les bulletins, factures, reçus, certificats et cartes scolaires sont générés
avec WeasyPrint (`weasyprint==63.*`, déjà dans `requirements.txt`).

**Windows** : WeasyPrint a besoin du runtime GTK3 (DLL Pango/Cairo).
L'installeur officiel est disponible ici :
<https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases>
(installez `gtk3-runtime-…-win64.exe`, un popup UAC vous le demandera).

L'application **charge automatiquement** les DLL GTK à la volée
(`documents/pdf.py` → `os.add_dll_directory`) : les PDF fonctionnent même si
le serveur a été lancé avant l'installation du runtime.

Sans GTK, l'application retombe automatiquement sur un rendu HTML téléchargeable
(plus aucun PDF réel tant que le runtime n'est pas installé).

---

## Documentation associée

- **Cahier des charges** : `Cahier_des_charges_Gestion_Scolaire.docx` — spécifications fonctionnelles complètes (45 cas d'utilisation, exigences non fonctionnelles, planning).

---

## Licence

Projet interne — licence à définir selon le contexte de diffusion.
