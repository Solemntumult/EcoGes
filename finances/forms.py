"""Formulaires du module Finances (encaissement, remises, états de caisse)."""

from decimal import Decimal

from django import forms

from eleves.models import Inscription

from .models import Echeance, Paiement, Remise


class PaiementForm(forms.ModelForm):
    """Encaissement d'un paiement avec imputation FIFO ou manuelle (UC-27)."""

    imputation_manuelle = forms.BooleanField(
        required=False,
        label="Imputation manuelle (sinon : automatique sur les échéances les plus anciennes — FIFO)",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    echeances = forms.ModelMultipleChoiceField(
        queryset=Echeance.objects.none(),
        required=False,
        label="Échéances à imputer (imputation manuelle)",
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": 8}),
    )

    class Meta:
        model = Paiement
        fields = ["inscription", "montant", "mode_paiement", "reference"]
        widgets = {
            "inscription": forms.Select(attrs={"class": "form-select"}),
            "montant": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0.01"}),
            "mode_paiement": forms.Select(attrs={"class": "form-select"}),
            "reference": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex. N° de chèque ou transaction"}),
        }

    def __init__(self, *args, **kwargs):
        initial = kwargs.get("initial", {}) or {}
        super().__init__(*args, **kwargs)
        # Inscription présélectionnée : URL (?inscription=) ou formulaire POST
        inscription_id = (self.data.get("inscription") if self.data else None) or initial.get("inscription")

        annee_courante = None
        from parametrage.models import AnneeScolaire
        annee_courante = AnneeScolaire.objects.filter(est_courante=True).first()
        qs = Inscription.objects.select_related("eleve", "classe", "annee_scolaire")
        if annee_courante:
            qs = qs.filter(annee_scolaire=annee_courante, statut="ACTIVE")
        self.fields["inscription"].queryset = qs

        if inscription_id:
            self.fields["echeances"].queryset = Echeance.objects.filter(
                inscription_id=inscription_id
            ).exclude(statut=Echeance.Statut.PAYE).order_by("date_echeance")

    def clean_montant(self):
        montant = self.cleaned_data["montant"]
        if montant <= 0:
            raise forms.ValidationError("Le montant doit être positif.")
        return montant


class RemiseForm(forms.ModelForm):
    """Octroi d'une remise / bourse avec motif (UC-33)."""

    class Meta:
        model = Remise
        fields = ["inscription", "type_remise", "montant", "motif"]
        widgets = {
            "inscription": forms.Select(attrs={"class": "form-select"}),
            "type_remise": forms.Select(attrs={"class": "form-select"}),
            "montant": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0.01"}),
            "motif": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from parametrage.models import AnneeScolaire
        annee = AnneeScolaire.objects.filter(est_courante=True).first()
        qs = Inscription.objects.select_related("eleve", "classe")
        if annee:
            qs = qs.filter(annee_scolaire=annee, statut="ACTIVE")
        self.fields["inscription"].queryset = qs


class EtatCaisseForm(forms.Form):
    """États de caisse journaliers / mensuels (UC-32)."""

    date_debut = forms.DateField(
        label="Du", widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )
    date_fin = forms.DateField(
        label="Au", widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )

    def clean(self):
        donnees = super().clean()
        if donnees.get("date_debut") and donnees.get("date_fin") \
                and donnees["date_fin"] < donnees["date_debut"]:
            self.add_error("date_fin", "La date de fin doit être postérieure à la date de début.")
        return donnees
