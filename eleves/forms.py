"""Formulaires du module Élèves (inscription, recherche, transfert, réinscription)."""

from django import forms

from parametrage.models import AnneeScolaire, Classe

from .models import Eleve, Inscription, Tuteur


class RechercheEleveForm(forms.Form):
    """Recherche multicritère (UC-15) : nom, matricule, classe, année."""

    annee = forms.ModelChoiceField(
        queryset=AnneeScolaire.objects.none(),
        required=False,
        empty_label="Toutes les années scolaires",
        label="Année scolaire",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    classe = forms.ModelChoiceField(
        queryset=Classe.objects.none(),
        required=False,
        label="Classe",
        empty_label="Toutes les classes",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    nom = forms.CharField(
        required=False,
        label="Nom / prénoms",
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "Nom ou prénom..."}),
    )
    matricule = forms.CharField(
        required=False,
        label="Matricule",
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "ELV-..."}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["annee"].queryset = AnneeScolaire.objects.all().order_by("-date_debut")
        self.fields["classe"].label_from_instance = lambda obj: obj.libelle
        courante = AnneeScolaire.objects.filter(est_courante=True).first()
        selected_annee = None
        if "annee" in self.data:
            annee_val = self.data.get("annee")
            if annee_val:
                selected_annee = AnneeScolaire.objects.filter(pk=annee_val).first()
        elif courante:
            self.fields["annee"].initial = courante
            selected_annee = courante

        classes_qs = Classe.objects.select_related("niveau", "annee_scolaire")
        if selected_annee:
            classes_qs = classes_qs.filter(annee_scolaire=selected_annee)
        self.fields["classe"].queryset = classes_qs


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
    """Sélection de l'année cible et de la classe source pour la reconduction de classe."""

    annee_cible = forms.ModelChoiceField(
        queryset=AnneeScolaire.objects.all(),
        label="Année scolaire cible (future)",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    classe_source = forms.ModelChoiceField(
        queryset=Classe.objects.none(),
        label="Classe d'origine à promouvoir",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        courante = AnneeScolaire.objects.filter(est_courante=True).first()
        if courante and not self.initial.get("annee_cible"):
            suivante = AnneeScolaire.objects.filter(date_debut__gt=courante.date_debut).order_by("date_debut").first()
            self.fields["annee_cible"].initial = suivante or courante

        # Les classes sources sont celles de l'année courante ou antérieures
        if courante:
            self.fields["classe_source"].queryset = Classe.objects.filter(
                annee_scolaire=courante
            ).select_related("niveau")
        else:
            self.fields["classe_source"].queryset = Classe.objects.select_related("niveau", "annee_scolaire").all()


class ImportExcelElevesForm(forms.Form):
    """Importation guidée de dossiers élèves depuis un fichier Excel ou CSV."""

    annee_scolaire = forms.ModelChoiceField(
        queryset=AnneeScolaire.objects.all(),
        label="Année scolaire d'inscription",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    fichier = forms.FileField(
        label="Fichier Excel (.xlsx) ou CSV (.csv)",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": ".xlsx,.csv"}),
        help_text="Sélectionnez un fichier conforme au modèle d'importation téléchargeable ci-dessus.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        courante = AnneeScolaire.objects.filter(est_courante=True).first()
        if courante:
            self.fields["annee_scolaire"].initial = courante
