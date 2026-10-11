import io
import json
from datetime import datetime, date
from decimal import Decimal

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from comptes.mixins import roles_requis
from comptes.services import journaliser
from parametrage.models import AnneeScolaire, Classe

from .forms import (
    EleveForm,
    ImportExcelElevesForm,
    InscriptionForm,
    RechercheEleveForm,
    ReinscriptionMasseForm,
    TransfertForm,
    TuteurFormSet,
)
from .models import Eleve, Inscription, Tuteur
from .services import classe_suggeree, reinscrire

ROLES_ADMIN = ["ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT"]


@login_required
@roles_requis(ROLES_ADMIN)
def liste(request):
    """Liste + recherche multicritère des élèves (UC-15).

    - Filtre par défaut sur l'année scolaire active (courante).
    - Permet de basculer vers les archives d'autres années scolaires.
    - Supporte HTMX pour le filtrage et les suggestions en direct sans rechargement.
    - Calcule la classe courante, le contact du tuteur et le solde financier.
    """
    courante = AnneeScolaire.objects.filter(est_courante=True).first()
    form = RechercheEleveForm(request.GET or None)

    annee_selectionnee = None
    if "annee" in request.GET:
        annee_id = request.GET.get("annee")
        if annee_id:
            annee_selectionnee = AnneeScolaire.objects.filter(pk=annee_id).first()
        else:
            annee_selectionnee = None  # Toutes les années
    else:
        annee_selectionnee = courante

    qs = Eleve.objects.prefetch_related(
        "tuteurs",
        "inscriptions__classe__niveau",
        "inscriptions__annee_scolaire",
        "inscriptions__echeances__imputations",
    ).order_by("nom", "prenoms")

    nom = request.GET.get("nom", "").strip()
    matricule = request.GET.get("matricule", "").strip()
    classe_id = request.GET.get("classe", "").strip()

    # Filtre sur l'inscription selon l'année et la classe
    filtre_inscription = Q(inscriptions__statut="ACTIVE")
    if annee_selectionnee:
        filtre_inscription &= Q(inscriptions__annee_scolaire=annee_selectionnee)
    if classe_id:
        filtre_inscription &= Q(inscriptions__classe_id=classe_id)

    qs = qs.filter(filtre_inscription)

    if nom:
        qs = qs.filter(Q(nom__icontains=nom) | Q(prenoms__icontains=nom))
    if matricule:
        qs = qs.filter(matricule__icontains=matricule)

    qs = qs.distinct()

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Enrichir les élèves avec classe, tuteur et solde
    for eleve in page_obj:
        if annee_selectionnee:
            ins = next(
                (i for i in eleve.inscriptions.all() if i.annee_scolaire_id == annee_selectionnee.id and i.statut == "ACTIVE"),
                None,
            )
        else:
            ins = next((i for i in eleve.inscriptions.all() if i.statut == "ACTIVE"), None) or eleve.inscriptions.first()
        eleve.inscription_affichee = ins

        tuteurs = list(eleve.tuteurs.all())
        urgence = next((t for t in tuteurs if t.contact_urgence), None)
        eleve.tuteur_principal = urgence or (tuteurs[0] if tuteurs else None)

        if ins:
            total_du = sum((e.montant_du for e in ins.echeances.all()), Decimal("0"))
            total_paye = sum((imp.montant_impute for e in ins.echeances.all() for imp in e.imputations.all()), Decimal("0"))
            eleve.solde_du = total_du - total_paye
            eleve.a_jour = (eleve.solde_du <= 0)
        else:
            eleve.solde_du = None
            eleve.a_jour = None

    contexte = {
        "eleves": page_obj,
        "form": form,
        "annee_selectionnee": annee_selectionnee,
        "annee_courante": courante,
        "annees_scolaires": AnneeScolaire.objects.all().order_by("-date_debut"),
        "total_eleves": paginator.count,
    }

    if request.headers.get("HX-Request"):
        return render(request, "eleves/_table_eleves.html", contexte)

    return render(request, "eleves/liste.html", contexte)


@login_required
@roles_requis(ROLES_ADMIN)
def modele_import_excel(request):
    """Téléchargement du modèle de fichier Excel d'importation d'élèves (Section 5.5)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Modele_Import_Eleves"

    headers = [
        "Matricule (optionnel)",
        "Nom (*)",
        "Prénoms (*)",
        "Sexe (M/F) (*)",
        "Date de naissance (JJ/MM/AAAA) (*)",
        "Lieu de naissance",
        "Classe (*)",
        "Statut inscription (NOUVEAU/REDOUBLANT/TRANSFERT/ANCIEN)",
        "Régime (EXTERNE/DEMI/INTERNE)",
        "Nom tuteur",
        "Lien parenté (PERE/MERE/TUTEUR/AUTRE)",
        "Téléphone tuteur",
        "Email tuteur",
        "Adresse",
    ]

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)

    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Exemples indicatifs
    ws.append(["", "KOUASSI", "Aya Marie", "F", "15/04/2012", "Abidjan", "6e A", "NOUVEAU", "EXTERNE", "KOUASSI Yao", "PERE", "0102030405", "yao@example.com", "Cocody"])
    ws.append(["ELV-2025-00042", "DIABATE", "Ibrahim", "M", "22/09/2011", "Bouaké", "5e B", "ANCIEN", "DEMI", "DIABATE Fatou", "MERE", "0708091011", "", "Yopougon"])

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 15)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="modele_importation_eleves.xlsx"'
    return response


@login_required
@roles_requis(ROLES_ADMIN)
def import_excel(request):
    """Assistant d'importation guidé et sécurisé de dossiers élèves (Section 5.5)."""
    annee_courante = AnneeScolaire.objects.filter(est_courante=True).first()

    if request.method == "POST":
        if "confirmer" in request.POST:
            # Étape finale : confirmation et exécution en base
            lignes_json = request.POST.get("donnees_json", "[]")
            annee_id = request.POST.get("annee_scolaire")
            annee = get_object_or_404(AnneeScolaire, pk=annee_id)
            try:
                lignes = json.loads(lignes_json)
            except Exception:
                messages.error(request, "Données d'importation invalides ou session expirée.")
                return redirect("eleves:import_excel")

            compteur_crees = 0
            compteur_reinscrits = 0
            compteur_erreurs = 0

            with transaction.atomic():
                for item in lignes:
                    if not item.get("valide"):
                        compteur_erreurs += 1
                        continue

                    classe = Classe.objects.filter(pk=item.get("classe_id")).first()
                    if not classe:
                        compteur_erreurs += 1
                        continue

                    # Élève existant ou nouveau
                    eleve = None
                    if item.get("eleve_id"):
                        eleve = Eleve.objects.filter(pk=item["eleve_id"]).first()

                    if not eleve:
                        try:
                            d_naiss = datetime.strptime(item["date_naissance"], "%Y-%m-%d").date()
                        except Exception:
                            compteur_erreurs += 1
                            continue

                        eleve = Eleve.objects.create(
                            nom=item["nom"].strip().upper(),
                            prenoms=item["prenoms"].strip().title(),
                            sexe=item["sexe"],
                            date_naissance=d_naiss,
                            lieu_naissance=item.get("lieu_naissance", ""),
                            adresse=item.get("adresse", ""),
                            regime=item.get("regime", "EXTERNE"),
                            statut="ACTIF",
                        )
                        # Création du tuteur si renseigné
                        if item.get("tuteur_nom"):
                            Tuteur.objects.create(
                                eleve=eleve,
                                nom_complet=item["tuteur_nom"],
                                lien_parente=item.get("tuteur_lien", "TUTEUR"),
                                telephone=item.get("tuteur_tel", ""),
                                email=item.get("tuteur_email", ""),
                                adresse=item.get("adresse", ""),
                                contact_urgence=True,
                            )
                        compteur_crees += 1
                    else:
                        compteur_reinscrits += 1

                    # Création de l'inscription pour l'année cible
                    inscription, created = Inscription.objects.get_or_create(
                        eleve=eleve,
                        annee_scolaire=annee,
                        defaults={
                            "classe": classe,
                            "statut_inscription": item.get("statut_inscription", "NOUVEAU"),
                            "statut": "ACTIVE",
                        },
                    )
                    if created:
                        from finances.services import generer_echeancier
                        generer_echeancier(inscription)

            journaliser(
                request.user,
                "Importation Excel",
                "Élève",
                f"Import en {annee} : {compteur_crees} créés, {compteur_reinscrits} réinscrits, {compteur_erreurs} ignorés.",
            )
            messages.success(
                request,
                f"Importation terminée avec succès : {compteur_crees} nouvel(s) élève(s), "
                f"{compteur_reinscrits} réinscription(s) effectuée(s).",
            )
            return redirect("eleves:liste")

        # Étape 1 : Analyse du fichier et prévisualisation
        form = ImportExcelElevesForm(request.POST, request.FILES)
        if form.is_valid():
            fichier = form.cleaned_data["fichier"]
            annee = form.cleaned_data["annee_scolaire"]

            lignes_analysees = []
            classes_dispos = {c.libelle.strip().lower(): c for c in Classe.objects.filter(annee_scolaire=annee)}

            try:
                if fichier.name.endswith(".xlsx"):
                    wb = openpyxl.load_workbook(fichier, data_only=True)
                    ws = wb.active
                    raw_rows = list(ws.iter_rows(values_only=True))
                else:
                    # CSV
                    content = fichier.read().decode("utf-8-sig", errors="ignore")
                    delimiter = ";" if ";" in content[:200] else ","
                    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
                    raw_rows = list(reader)

                lignes_data = raw_rows[1:]  # sauter la ligne d'en-tête
                for idx, row in enumerate(lignes_data, start=2):
                    if not row or not any(row):
                        continue

                    matricule = str(row[0] or "").strip()
                    nom = str(row[1] or "").strip()
                    prenoms = str(row[2] or "").strip()
                    sexe = str(row[3] or "").strip().upper()
                    if sexe not in ["M", "F"]:
                        sexe = "M"

                    # Date de naissance
                    date_val = row[4]
                    d_parsed = None
                    if isinstance(date_val, (datetime, date)):
                        d_parsed = date_val if isinstance(date_val, date) else date_val.date()
                    elif date_val:
                        date_str = str(date_val).strip()
                        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
                            try:
                                d_parsed = datetime.strptime(date_str, fmt).date()
                                break
                            except ValueError:
                                pass

                    lieu_naiss = str(row[5] or "").strip() if len(row) > 5 else ""
                    classe_str = str(row[6] or "").strip() if len(row) > 6 else ""
                    statut_ins = str(row[7] or "NOUVEAU").strip().upper() if len(row) > 7 else "NOUVEAU"
                    if statut_ins not in ["NOUVEAU", "REDOUBLANT", "TRANSFERT", "ANCIEN"]:
                        statut_ins = "NOUVEAU"

                    regime = str(row[8] or "EXTERNE").strip().upper() if len(row) > 8 else "EXTERNE"
                    if regime not in ["EXTERNE", "DEMI", "INTERNE"]:
                        regime = "EXTERNE"

                    tuteur_nom = str(row[9] or "").strip() if len(row) > 9 else ""
                    tuteur_lien = str(row[10] or "TUTEUR").strip().upper() if len(row) > 10 else "TUTEUR"
                    tuteur_tel = str(row[11] or "").strip() if len(row) > 11 else ""
                    tuteur_email = str(row[12] or "").strip() if len(row) > 12 else ""
                    adresse = str(row[13] or "").strip() if len(row) > 13 else ""

                    # Validation
                    erreurs = []
                    if not nom:
                        erreurs.append("Nom manquant")
                    if not prenoms:
                        erreurs.append("Prénoms manquants")
                    if not d_parsed:
                        erreurs.append("Date de naissance invalide (format attendu : JJ/MM/AAAA)")

                    classe_obj = classes_dispos.get(classe_str.lower())
                    if not classe_obj:
                        erreurs.append(f"Classe « {classe_str} » introuvable dans l'année {annee}")

                    # Détection de doublon / élève existant
                    eleve_existant = None
                    action = "CREATION"
                    if matricule:
                        eleve_existant = Eleve.objects.filter(matricule__iexact=matricule).first()
                    if not eleve_existant and nom and prenoms and d_parsed:
                        eleve_existant = Eleve.objects.filter(
                            nom__iexact=nom, prenoms__iexact=prenoms, date_naissance=d_parsed
                        ).first()

                    if eleve_existant:
                        deja_inscrit = Inscription.objects.filter(
                            eleve=eleve_existant, annee_scolaire=annee
                        ).exists()
                        if deja_inscrit:
                            erreurs.append(f"Déjà inscrit en {annee} ({eleve_existant.matricule})")
                            action = "DOUBLON"
                        else:
                            action = "REINSCRIPTION"
                            matricule = eleve_existant.matricule

                    lignes_analysees.append({
                        "ligne": idx,
                        "matricule": matricule,
                        "nom": nom,
                        "prenoms": prenoms,
                        "sexe": sexe,
                        "date_naissance": d_parsed.strftime("%Y-%m-%d") if d_parsed else "",
                        "date_naissance_fr": d_parsed.strftime("%d/%m/%Y") if d_parsed else "",
                        "lieu_naissance": lieu_naiss,
                        "classe_str": classe_str,
                        "classe_id": classe_obj.id if classe_obj else None,
                        "statut_inscription": statut_ins,
                        "regime": regime,
                        "tuteur_nom": tuteur_nom,
                        "tuteur_lien": tuteur_lien,
                        "tuteur_tel": tuteur_tel,
                        "tuteur_email": tuteur_email,
                        "adresse": adresse,
                        "eleve_id": eleve_existant.id if eleve_existant else None,
                        "action": action,
                        "valide": len(erreurs) == 0,
                        "erreurs": erreurs,
                    })

                nb_nouveaux = sum(1 for l in lignes_analysees if l["valide"] and l["action"] == "CREATION")
                nb_reinscrits = sum(1 for l in lignes_analysees if l["valide"] and l["action"] == "REINSCRIPTION")
                nb_invalides = sum(1 for l in lignes_analysees if not l["valide"])

                contexte = {
                    "annee": annee,
                    "lignes": lignes_analysees,
                    "donnees_json": json.dumps(lignes_analysees),
                    "nb_nouveaux": nb_nouveaux,
                    "nb_reinscrits": nb_reinscrits,
                    "nb_invalides": nb_invalides,
                    "total_lignes": len(lignes_analysees),
                }
                return render(request, "eleves/import_preview.html", contexte)

            except Exception as e:
                messages.error(request, f"Erreur lors de la lecture du fichier : {e}")
                return redirect("eleves:import_excel")
    else:
        form = ImportExcelElevesForm()

    return render(request, "eleves/import_form.html", {"form": form, "annee_courante": annee_courante})


@login_required
@roles_requis(ROLES_ADMIN)
def creation(request):
    """Inscription d'un nouvel élève + tuteurs + échéancier (UC-11)."""
    annee_courante = AnneeScolaire.objects.filter(est_courante=True).first()
    if annee_courante is None:
        messages.warning(request, "Aucune année scolaire n'est définie comme courante. "
                                  "Paramétrez d'abord l'année scolaire dans l'administration.")
        return redirect("eleves:liste")

    if request.method == "POST":
        form_eleve = EleveForm(request.POST, request.FILES)
        form_inscription = InscriptionForm(request.POST)
        formset_tuteurs = TuteurFormSet(request.POST)

        if form_eleve.is_valid() and form_inscription.is_valid() and formset_tuteurs.is_valid():
            with transaction.atomic():
                eleve = form_eleve.save()
                formset_tuteurs.instance = eleve
                formset_tuteurs.save()
                inscription = Inscription.objects.create(
                    eleve=eleve,
                    classe=form_inscription.cleaned_data["classe"],
                    annee_scolaire=annee_courante,
                    statut_inscription=form_inscription.cleaned_data["statut_inscription"],
                )
                from finances.services import generer_echeancier
                generer_echeancier(inscription)
            journaliser(
                request.user, "Inscription", "Élève",
                f"{eleve} inscrit en {inscription.classe} ({annee_courante}) — "
                f"échéancier généré automatiquement.",
            )
            messages.success(request, f"Élève {eleve.matricule} inscrit avec succès. "
                                      f"L'échéancier de scolarité a été généré.")
            return redirect("eleves:detail", pk=eleve.pk)
    else:
        form_eleve = EleveForm()
        form_inscription = InscriptionForm()
        formset_tuteurs = TuteurFormSet()

    contexte = {
        "form_eleve": form_eleve,
        "form_inscription": form_inscription,
        "formset_tuteurs": formset_tuteurs,
        "annee_courante": annee_courante,
    }
    return render(request, "eleves/creation.html", contexte)


@login_required
@roles_requis(ROLES_ADMIN)
def detail(request, pk):
    """Dossier élève consolidé (UC-15) : scolarité + finances + documents."""
    eleve = get_object_or_404(
        Eleve.objects.prefetch_related("tuteurs", "documents"),
        pk=pk,
    )
    inscriptions = eleve.inscriptions.select_related("classe__niveau", "annee_scolaire").all()
    inscription_courante = inscriptions.filter(statut="ACTIVE").first()

    notes = []
    bulletins = []
    situation = None
    echeances = []
    paiements = []
    factures = []
    remises = []

    if inscription_courante:
        from evaluations.models import Bulletin, Note
        notes = Note.objects.filter(inscription=inscription_courante).select_related(
            "evaluation__matiere", "evaluation__periode"
        )
        bulletins = Bulletin.objects.filter(inscription=inscription_courante)
        from finances.models import Echeance as ModEcheance
        echeances = ModEcheance.objects.filter(inscription=inscription_courante).order_by("date_echeance")
        paiements = inscription_courante.paiements.select_related("recu").order_by("-date_paiement")
        factures = inscription_courante.factures.all()
        remises = inscription_courante.remises.all()
        from finances.services import situation_inscription
        situation = situation_inscription(inscription_courante)

    total_du = sum((e.montant_du for e in echeances), Decimal("0"))

    contexte = {
        "eleve": eleve,
        "inscriptions": inscriptions,
        "inscription_courante": inscription_courante,
        "notes": notes,
        "bulletins": bulletins,
        "echeances": echeances,
        "paiements": paiements,
        "factures": factures,
        "remises": remises,
        "situation": situation,
        "total_du": total_du,
    }
    return render(request, "eleves/detail.html", contexte)


@login_required
@roles_requis(ROLES_ADMIN)
def modifier(request, pk):
    """Mise à jour du dossier (infos perso + tuteurs) (UC-13)."""
    eleve = get_object_or_404(Eleve, pk=pk)
    if request.method == "POST":
        form_eleve = EleveForm(request.POST, request.FILES, instance=eleve)
        formset_tuteurs = TuteurFormSet(request.POST, instance=eleve)
        if form_eleve.is_valid() and formset_tuteurs.is_valid():
            form_eleve.save()
            formset_tuteurs.save()
            journaliser(request.user, "Modification du dossier", "Élève", str(eleve))
            messages.success(request, "Dossier mis à jour.")
            return redirect("eleves:detail", pk=eleve.pk)
    else:
        form_eleve = EleveForm(instance=eleve)
        formset_tuteurs = TuteurFormSet(instance=eleve)
    contexte = {"form_eleve": form_eleve, "formset_tuteurs": formset_tuteurs, "eleve": eleve}
    return render(request, "eleves/modifier.html", contexte)


@login_required
@roles_requis(ROLES_ADMIN)
def transferer(request, pk):
    """Transfert / radiation avec archivage (UC-14)."""
    eleve = get_object_or_404(Eleve, pk=pk)
    if request.method == "POST":
        form = TransfertForm(request.POST)
        if form.is_valid():
            nouveau_statut = form.cleaned_data["nouveau_statut"]
            motif = form.cleaned_data["motif"]
            eleve.statut = nouveau_statut
            eleve.save(update_fields=["statut"])
            # Archivage : clôture des inscriptions actives
            Inscription.objects.filter(eleve=eleve, statut="ACTIVE").update(statut="TERMINEE")
            journaliser(
                request.user,
                f"{'Transfert' if nouveau_statut == 'TRANSFERE' else 'Radiation'}",
                "Élève",
                f"{eleve} — motif : {motif}",
            )
            messages.success(request, f"{eleve} a été archivé (statut « {eleve.get_statut_display()} »).")
            return redirect("eleves:detail", pk=eleve.pk)
    else:
        form = TransfertForm()
    contexte = {"form": form, "eleve": eleve}
    return render(request, "eleves/transferer.html", contexte)


@login_required
@roles_requis(ROLES_ADMIN)
def reinscription_masse(request):
    """Réinscription en masse par classe avec passage suggéré (UC-12)."""
    annee_cible = None
    classe_source = None
    eleves_a_reinscrire = []

    if "classe_source" in request.GET:
        form = ReinscriptionMasseForm(request.GET)
        if form.is_valid():
            annee_cible = form.cleaned_data["annee_cible"]
            classe_source = form.cleaned_data["classe_source"]
            inscriptions = Inscription.objects.filter(
                classe=classe_source, statut="ACTIVE", annee_scolaire__est_courante=True
            ).select_related("eleve")
            eleves_a_reinscrire = [
                {
                    "inscription": ins,
                    "suggeree": classe_suggeree(ins, annee_cible),
                }
                for ins in inscriptions
                if not Inscription.objects.filter(eleve=ins.eleve, annee_scolaire=annee_cible).exists()
            ]
    else:
        form = ReinscriptionMasseForm()

    if request.method == "POST" and request.POST.get("confirmer"):
        eleve_ids = request.POST.getlist("eleves")
        compteur = 0
        for eleve_id in eleve_ids:
            classe_id = request.POST.get(f"classe_{eleve_id}")
            if not classe_id:
                continue
            eleve = Eleve.objects.filter(pk=eleve_id).first()
            classe = Classe.objects.filter(pk=classe_id, annee_scolaire_id=request.POST.get("annee_cible")).first()
            if eleve and classe:
                if reinscrire(eleve, classe, classe.annee_scolaire, "ANCIEN", request.user):
                    compteur += 1
        messages.success(request, f"{compteur} élève(s) réinscrit(s) avec succès.")
        return redirect("eleves:liste")

    contexte = {
        "form": form,
        "annee_cible": annee_cible,
        "classe_source": classe_source,
        "eleves_a_reinscrire": eleves_a_reinscrire,
    }
    return render(request, "eleves/reinscription.html", contexte)


@login_required
@roles_requis(ROLES_ADMIN)
def reinscription_individuelle(request, pk):
    """Réinscription annuelle d'un élève existant (avec reçu/paiement au guichet)."""
    eleve = get_object_or_404(Eleve, pk=pk)
    annee_courante = AnneeScolaire.objects.filter(est_courante=True).first()
    if not annee_courante:
        messages.error(request, "Aucune année scolaire active n'est définie.")
        return redirect("eleves:detail", pk=eleve.pk)

    # Vérifier s'il est déjà inscrit dans l'année active
    inscription_existante = Inscription.objects.filter(eleve=eleve, annee_scolaire=annee_courante).first()
    if inscription_existante:
        messages.info(request, f"{eleve} est déjà inscrit(e) pour l'année {annee_courante} (Classe : {inscription_existante.classe.libelle}).")
        return redirect("eleves:detail", pk=eleve.pk)

    if request.method == "POST":
        form = InscriptionForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                classe = form.cleaned_data["classe"]
                statut_ins = form.cleaned_data.get("statut_inscription", "ANCIEN")
                nouvelle_inscription = Inscription.objects.create(
                    eleve=eleve,
                    classe=classe,
                    annee_scolaire=annee_courante,
                    statut_inscription=statut_ins,
                    statut="ACTIVE",
                )
                from finances.services import generer_echeancier
                generer_echeancier(nouvelle_inscription)

            journaliser(
                request.user, "Réinscription", "Élève",
                f"{eleve} réinscrit en {classe.libelle} ({annee_courante}) — échéancier généré.",
            )
            messages.success(
                request,
                f"Réinscription de {eleve} validée avec succès en {classe.libelle} pour {annee_courante}. Échéancier de scolarité généré."
            )
            return redirect("eleves:detail", pk=eleve.pk)
    else:
        form = InscriptionForm()

    return render(request, "eleves/reinscrire_individuel.html", {
        "eleve": eleve,
        "form": form,
        "annee_courante": annee_courante,
    })


@login_required
@roles_requis(ROLES_ADMIN)
def carte_scolaire(request, pk):
    """Génération de la carte scolaire PDF avec QR code (UC-16)."""
    eleve = get_object_or_404(Eleve, pk=pk)
    inscription = eleve.inscriptions.filter(statut="ACTIVE").first()
    contexte = {"eleve": eleve, "inscription": inscription}

    from documents.pdf import qr_data_uri, reponse_pdf
    contexte["qr_code"] = qr_data_uri(f"{eleve.matricule}|{eleve.nom} {eleve.prenoms}")
    contexte["photo_data_uri"] = eleve.photo_data_uri()

    from documents.models import DocumentAdministratif
    doc = DocumentAdministratif.objects.create(
        type_document="CARTE_SCOLAIRE", eleve=eleve, genere_par=request.user
    )
    contexte["doc"] = doc
    journaliser(request.user, "Édition de carte scolaire", "Élève", str(eleve))
    return reponse_pdf("documents/carte_scolaire.html", contexte, f"carte_scolaire_{eleve.matricule}")
