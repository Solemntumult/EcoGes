"""Formulaires du module Élèves (inscription, recherche, transfert, réinscription)."""

from django import forms

from parametrage.models import AnneeScolaire, Classe

from .models import Eleve, Inscription, Tuteur


class RechercheEleveForm(forms.Form):
    """Recherche multicritère (UC-15) : nom, matricule, classe, statut."""

    nom = forms.CharField(required=False, label="Nom / prénoms",
                          widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nom ou prénoms"}))
    matricule = forms.CharField(required=False, label="Matricule",
                                widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "ELV-..."}))
    classe = forms.ModelChoiceField(queryset=Classe.objects.none(), required=False, label="Classe",
                                    widget=forms.Select(attrs={"class": "form-select"}))
    statut = forms.ChoiceField(
        choices=[("", "Tous les statuts")] + list(Eleve.Statut.choices),
        required=False, label="Statut",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["classe"].queryset = Classe.objects.select_related("niveau", "annee_scolaire").all()


class EleveForm(forms.ModelForm):
    class Meta:
        model = Eleve
        fields = ["nom", "prenoms", "sexe", "date_naissance", "lieu_naissance",
                  "photo", "adresse", "regime"]
        widgets = {
            "nom": forms.TextInput(attrs={"class": "form-control"}),
            "prenoms": forms.TextInput(attrs={"class": "form-control"}),
            "sexe": forms.Select(attrs={"class": "form-select"}),
            "date_naissance": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "lieu_naissance": forms.TextInput(attrs={"class": "form-control"}),
            "photo": forms.FileInput(attrs={"class": "form-control"}),
            "adresse": forms.TextInput(attrs={"class": "form-control"}),
            "regime": forms.Select(attrs={"class": "form-select"}),
        }


class TuteurForm(forms.ModelForm):
    class Meta:
        model = Tuteur
        fields = ["nom_complet", "lien_parente", "telephone", "email", "adresse", "contact_urgence"]
        widgets = {
            "nom_complet": forms.TextInput(attrs={"class": "form-control"}),
            "lien_parente": forms.Select(attrs={"class": "form-select"}),
            "telephone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "adresse": forms.TextInput(attrs={"class": "form-control"}),
            "contact_urgence": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


TuteurFormSet = forms.inlineformset_factory(
    Eleve, Tuteur, form=TuteurForm, extra=1, can_delete=True
)


class InscriptionForm(forms.ModelForm):
    """Choix de la classe et du statut pour une inscription."""

    class Meta:
        model = Inscription
        fields = ["classe", "statut_inscription"]
        widgets = {
            "classe": forms.Select(attrs={"class": "form-select"}),
            "statut_inscription": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        annee = AnneeScolaire.objects.filter(est_courante=True).first()
        self.annee_courante = annee
        if annee:
            self.fields["classe"].queryset = Classe.objects.filter(annee_scolaire=annee).select_related("niveau")


class TransfertForm(forms.Form):
    """Transfert / radiation d'un élève (UC-14)."""

    nouveau_statut = forms.ChoiceField(
        choices=[("TRANSFERE", "Transféré vers un autre établissement"),
                 ("RADIE", "Radié / exclu")],
        label="Opération",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    motif = forms.CharField(
        label="Motif",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )


class ReinscriptionMasseForm(forms.Form):
    """Sélection de l'année cible et de la classe source (UC-12)."""

    annee_cible = forms.ModelChoiceField(
        queryset=AnneeScolaire.objects.all(), label="Année scolaire cible",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    classe_source = forms.ModelChoiceField(
        queryset=Classe.objects.none(), label="Classe d'origine",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        annee = kwargs.get("initial", {}).get("annee_cible")
        if annee:
            self.fields["classe_source"].queryset = Classe.objects.filter(annee_scolaire=annee)
