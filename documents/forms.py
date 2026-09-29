"""Formulaires du module Documents administratifs."""

from django import forms

from eleves.models import Eleve, Inscription
from parametrage.models import AnneeScolaire, Classe

from .models import ModeleDocument


class DocumentEleveForm(forms.Form):
    """Génération d'un document pour un élève (UC-35, UC-36)."""

    eleve = forms.ModelChoiceField(
        queryset=Eleve.objects.select_related().order_by("nom", "prenoms"),
        label="Élève",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    type_document = forms.ChoiceField(
        choices=[
            (code, label)
            for code, label in ModeleDocument.TypeDocument.choices
            if code in ("CERTIFICAT_SCOLARITE", "ATTESTATION_REUSSITE", "RELEVE_NOTES", "CARTE_SCOLAIRE")
        ],
        label="Type de document",
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class ListeClasseForm(forms.Form):
    """Liste de classe avec filtres (sexe, statut de paiement) (UC-37)."""

    classe = forms.ModelChoiceField(
        queryset=Classe.objects.none(),
        label="Classe",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    sexe = forms.ChoiceField(
        choices=[("", "Tous")] + list(Eleve.Sexe.choices),
        required=False, label="Sexe",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    statut_paiement = forms.ChoiceField(
        choices=[("", "Tous"), ("A_JOUR", "À jour"), ("IMPAYE", "En impayé")],
        required=False, label="Statut de paiement",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        annee = AnneeScolaire.objects.filter(est_courante=True).first()
        if annee:
            self.fields["classe"].queryset = Classe.objects.filter(
                annee_scolaire=annee
            ).select_related("niveau")


class CourrierForm(forms.Form):
    """Courriers types (convocation, avertissement, mise en demeure) (UC-38)."""

    inscription = forms.ModelChoiceField(
        queryset=Inscription.objects.none(),
        label="Élève",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    type_courrier = forms.ChoiceField(
        choices=[
            ("CONVOCATION", "Convocation de parents"),
            ("AVERTISSEMENT", "Avertissement"),
            ("MISE_EN_DEMEURE", "Mise en demeure de paiement"),
        ],
        label="Type de courrier",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    motif = forms.CharField(
        required=False, label="Motif (optionnel)",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        annee = AnneeScolaire.objects.filter(est_courante=True).first()
        qs = Inscription.objects.select_related("eleve", "classe", "annee_scolaire")
        if annee:
            qs = qs.filter(annee_scolaire=annee, statut="ACTIVE")
        self.fields["inscription"].queryset = qs.order_by("eleve__nom")
