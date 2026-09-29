"""Formulaires du module Paramétrage (horaires journaliers et pauses)."""

from decimal import Decimal

from django import forms

from .models import (
    ClasseMatiereCoefficient,
    Etablissement,
    HoraireJournalier,
    LogoEtablissement,
    Matiere,
    Niveau,
    PauseHoraire,
    QuotaHoraireMatiere,
)


class EtablissementForm(forms.ModelForm):
    class Meta:
        model = Etablissement
        fields = [
            "nom_officiel", "sigle", "devise", "logo",
            "adresse", "ville", "commune", "pays", "boite_postale",
            "telephone", "email", "site_web",
            "statut_juridique", "categorie", "ministere_tutelle",
            "numero_arrete", "date_arrete", "code_etablissement",
            "annee_creation", "fondateur", "ifu", "rccm",
            "nom_directeur", "nom_censeur", "nom_comptable",
            "mentions_legales", "regime_fiscal", "formule_certification",
        ]
        widgets = {
            "nom_officiel": forms.TextInput(attrs={"class": "form-control"}),
            "sigle": forms.TextInput(attrs={"class": "form-control"}),
            "devise": forms.TextInput(attrs={"class": "form-control"}),
            "logo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "adresse": forms.TextInput(attrs={"class": "form-control"}),
            "ville": forms.TextInput(attrs={"class": "form-control"}),
            "commune": forms.TextInput(attrs={"class": "form-control"}),
            "pays": forms.TextInput(attrs={"class": "form-control"}),
            "boite_postale": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex. BP 1234"}),
            "telephone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "site_web": forms.URLInput(attrs={"class": "form-control"}),
            "statut_juridique": forms.Select(attrs={"class": "form-select"}),
            "categorie": forms.Select(attrs={"class": "form-select"}),
            "ministere_tutelle": forms.TextInput(attrs={"class": "form-control"}),
            "numero_arrete": forms.TextInput(attrs={"class": "form-control"}),
            "date_arrete": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "code_etablissement": forms.TextInput(attrs={"class": "form-control"}),
            "annee_creation": forms.NumberInput(attrs={"class": "form-control", "min": 1900, "max": 2100}),
            "fondateur": forms.TextInput(attrs={"class": "form-control"}),
            "ifu": forms.TextInput(attrs={"class": "form-control"}),
            "rccm": forms.TextInput(attrs={"class": "form-control"}),
            "nom_directeur": forms.TextInput(attrs={"class": "form-control"}),
            "nom_censeur": forms.TextInput(attrs={"class": "form-control"}),
            "nom_comptable": forms.TextInput(attrs={"class": "form-control"}),
            "mentions_legales": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "regime_fiscal": forms.TextInput(attrs={"class": "form-control"}),
            "formule_certification": forms.TextInput(attrs={"class": "form-control"}),
        }


class LogoEtablissementForm(forms.ModelForm):
    """Un logo supplémentaire de l'établissement (État, ministère, collège...)."""

    class Meta:
        model = LogoEtablissement
        fields = ["libelle", "image", "ordre", "en_tete"]
        widgets = {
            "libelle": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex. Logo de la République, Logo du collège",
            }),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "ordre": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "en_tete": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class NiveauForm(forms.ModelForm):
    """Création d'un niveau (avec série pour le second cycle)."""

    class Meta:
        model = Niveau
        fields = ["libelle", "cycle", "serie"]
        widgets = {
            "libelle": forms.TextInput(attrs={
                "class": "form-control", "placeholder": "Ex. 2nde, Terminale",
            }),
            "cycle": forms.Select(attrs={"class": "form-select"}),
            "serie": forms.Select(attrs={"class": "form-select"}),
        }

    def clean(self):
        donnees = super().clean()
        if donnees.get("cycle") == Niveau.Cycle.LYCEE and not donnees.get("serie"):
            self.add_error("serie", "Un niveau du second cycle (Lycée) doit avoir une série.")
        return donnees


class MatiereForm(forms.ModelForm):
    """Création d'une matière pour un niveau donné (le coefficient se règle
    ensuite par classe dans ClasseMatiereCoefficient)."""

    class Meta:
        model = Matiere
        fields = ["libelle", "niveau", "tronc_commun"]
        widgets = {
            "libelle": forms.TextInput(attrs={
                "class": "form-control", "placeholder": "Ex. Mathématiques",
            }),
            "niveau": forms.Select(attrs={"class": "form-select"}),
            "tronc_commun": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["niveau"].queryset = Niveau.objects.select_related("serie").all()
        self.fields["tronc_commun"].label = "Matière du tronc commun"
        self.fields["tronc_commun"].help_text = (
            "Liée automatiquement à toutes les classes de ce niveau "
            "(à leur création comme à la création de la matière)."
        )


class AjouterMatiereClasseForm(forms.Form):
    """Ajout d'une matière à une classe précise, avec son coefficient initial.

    Soit on choisit une matière existante du même niveau, soit on en crée une
    nouvelle (libellé libre) — le coefficient (matière, classe) est toujours saisi.
    """

    matiere = forms.ModelChoiceField(
        queryset=Matiere.objects.none(), required=False, label="Matière existante",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    libelle = forms.CharField(
        max_length=100, required=False, label="… ou nouvelle matière",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Nom de la matière (ex. Droit, Art Appliqué)",
        }),
    )
    coefficient = forms.DecimalField(
        min_value=Decimal("0.5"), max_value=Decimal("20"),
        initial=Decimal("1"), label="Coefficient",
        error_messages={
            "min_value": "Le coefficient minimum est 0,5.",
            "max_value": "Le coefficient ne peut pas dépasser 20.",
            "invalid": "Coefficient invalide.",
        },
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.5"}),
    )

    def __init__(self, *args, **kwargs):
        self.classe = kwargs.pop("classe", None)
        super().__init__(*args, **kwargs)
        if self.classe is not None:
            deja_liees = ClasseMatiereCoefficient.objects.filter(
                classe=self.classe
            ).values_list("matiere_id", flat=True)
            self.fields["matiere"].queryset = (
                Matiere.objects.filter(niveau=self.classe.niveau)
                .exclude(pk__in=deja_liees).order_by("libelle")
            )

    def clean(self):
        donnees = super().clean()
        if not donnees.get("matiere") and not (donnees.get("libelle") or "").strip():
            raise forms.ValidationError(
                "Choisissez une matière existante ou saisissez le nom d'une nouvelle matière."
            )
        return donnees


class CoefficientForm(forms.Form):
    """Modification du coefficient d'une matière pour une classe précise."""

    coefficient = forms.DecimalField(
        min_value=Decimal("0.5"), max_value=Decimal("20"),
        error_messages={
            "min_value": "Le coefficient minimum est 0,5.",
            "max_value": "Le coefficient ne peut pas dépasser 20.",
            "invalid": "Coefficient invalide.",
        },
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.5"}),
    )


class HoraireForm(forms.ModelForm):
    class Meta:
        model = HoraireJournalier
        fields = ["libelle", "actif", "heure_debut_journee", "heure_fin_journee", "duree_creneau_base", "affichage_cellule"]
        widgets = {
            "libelle": forms.TextInput(attrs={"class": "form-control"}),
            "actif": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "heure_debut_journee": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "heure_fin_journee": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "duree_creneau_base": forms.NumberInput(attrs={"class": "form-control", "min": 15, "max": 120, "step": 5}),
            "affichage_cellule": forms.Select(attrs={"class": "form-select"}),
        }

    def clean(self):
        donnees = super().clean()
        debut = donnees.get("heure_debut_journee")
        fin = donnees.get("heure_fin_journee")
        if debut and fin and fin <= debut:
            self.add_error("heure_fin_journee", "L'heure de fin doit être postérieure à l'heure de début.")
        return donnees


class PauseHoraireForm(forms.ModelForm):
    class Meta:
        model = PauseHoraire
        fields = ["libelle", "heure_debut", "heure_fin"]
        widgets = {
            "libelle": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex. Récréation"}),
            "heure_debut": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "heure_fin": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
        }

    def clean(self):
        donnees = super().clean()
        debut = donnees.get("heure_debut")
        fin = donnees.get("heure_fin")
        if debut and fin and fin <= debut:
            self.add_error("heure_fin", "L'heure de fin doit être postérieure à l'heure de début.")
        return donnees


class QuotaHoraireForm(forms.ModelForm):
    class Meta:
        model = QuotaHoraireMatiere
        fields = ["matiere", "classe", "heures_par_semaine"]
        widgets = {
            "matiere": forms.Select(attrs={"class": "form-select"}),
            "classe": forms.Select(attrs={"class": "form-select"}),
            "heures_par_semaine": forms.NumberInput(attrs={
                "class": "form-control", "step": "0.5", "min": "0.5",
                "placeholder": "Ex. 4",
            }),
        }
