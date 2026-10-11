"""Formulaires du module Paramétrage (horaires journaliers et pauses)."""

from decimal import Decimal

from django import forms

from .models import (
    Classe,
    ClasseMatiereCoefficient,
    Etablissement,
    HoraireJournalier,
    LogoEtablissement,
    Matiere,
    Niveau,
    PauseHoraire,
    QuotaHoraireMatiere,
)
from personnel.models import Personnel



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
        if donnees.get("cycle") == Niveau.Cycle.SECOND_CYCLE and not donnees.get("serie"):
            self.add_error("serie", "Un niveau du second cycle doit avoir une série.")
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
    """Ajout d'une nouvelle matière à une classe précise, avec son coefficient et son quota horaire."""

    libelle = forms.CharField(
        max_length=100,
        required=True,
        label="Nom de la matière",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ex. Religion, Dessin, Musique, Informatique...",
            "autofocus": True,
        }),
        error_messages={
            "required": "Veuillez renseigner le nom de la matière.",
        },
    )
    coefficient = forms.DecimalField(
        min_value=Decimal("0.5"),
        max_value=Decimal("20"),
        initial=Decimal("1"),
        label="Coefficient",
        error_messages={
            "min_value": "Le coefficient minimum est 0,5.",
            "max_value": "Le coefficient ne peut pas dépasser 20.",
            "invalid": "Coefficient invalide.",
            "required": "Veuillez préciser le coefficient.",
        },
        widget=forms.NumberInput(attrs={"class": "form-control text-center font-monospace fw-bold", "step": "0.5"}),
    )
    heures_par_semaine = forms.DecimalField(
        min_value=Decimal("0.5"),
        max_value=Decimal("30"),
        initial=Decimal("2"),
        required=False,
        label="Quota horaire",
        widget=forms.NumberInput(attrs={"class": "form-control text-center font-monospace fw-bold", "step": "0.5", "placeholder": "2"}),
    )

    def __init__(self, *args, **kwargs):
        self.classe = kwargs.pop("classe", None)
        super().__init__(*args, **kwargs)
        if self.classe and self.classe.niveau:
            # En premier cycle, le coefficient est toujours fixé à 1 de base
            if self.classe.niveau.cycle == Niveau.Cycle.PREMIER_CYCLE:
                self.fields["coefficient"].initial = Decimal("1")
                self.fields["coefficient"].widget.attrs["readonly"] = True
                self.fields["coefficient"].help_text = "Fixé à 1 pour le 1er cycle"

    def clean_libelle(self):
        libelle = self.cleaned_data.get("libelle", "").strip()
        if not libelle:
            raise forms.ValidationError("Le nom de la matière est obligatoire.")
        if self.classe:
            # Vérifier si cette matière existe déjà dans cette classe
            from .models import ClasseMatiereCoefficient
            existe_deja = ClasseMatiereCoefficient.objects.filter(
                classe=self.classe,
                matiere__libelle__iexact=libelle,
            ).exists()
            if existe_deja:
                raise forms.ValidationError(f"La matière « {libelle} » est déjà enseignée dans cette classe.")
        return libelle

    def clean_coefficient(self):
        coef = self.cleaned_data.get("coefficient")
        if self.classe and self.classe.niveau:
            if self.classe.niveau.cycle == Niveau.Cycle.PREMIER_CYCLE:
                return Decimal("1")
        return coef


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


class ClasseForm(forms.ModelForm):
    """Création et modification d'une classe d'un niveau donné."""

    class Meta:
        model = Classe
        fields = ["niveau", "libelle", "enseignant_principal", "effectif_max"]
        widgets = {
            "niveau": forms.Select(attrs={"class": "form-select"}),
            "libelle": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Dénomination ou division (ex. 6ème A1, 3ème B, Tle D1)",
            }),
            "enseignant_principal": forms.Select(attrs={"class": "form-select"}),
            "effectif_max": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 150}),
        }
        labels = {
            "niveau": "Niveau scolaire",
            "libelle": "Dénomination de la classe",
            "enseignant_principal": "Professeur Principal (PP)",
            "effectif_max": "Capacité maximale d'élèves",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["niveau"].queryset = Niveau.objects.select_related("serie").order_by("cycle", "ordre")
        self.fields["enseignant_principal"].queryset = Personnel.objects.filter(
            est_enseignant=True, actif=True
        ).order_by("nom", "prenoms")
        self.fields["enseignant_principal"].empty_label = "-- Aucun professeur principal assigné --"

