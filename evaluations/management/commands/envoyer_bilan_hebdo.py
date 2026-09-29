import datetime
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from django.template.loader import render_to_string
from evaluations.models import Note
from eleves.models import Inscription, Tuteur

class Command(BaseCommand):
    help = 'Envoie un bilan hebdomadaire des notes validées aux parents.'

    def handle(self, *args, **options):
        maintenant = timezone.now()
        il_y_a_7_jours = maintenant - datetime.timedelta(days=7)
        
        # Récupérer toutes les notes validées saisies/modifiées dans les 7 derniers jours
        nouvelles_notes = Note.objects.filter(
            evaluation__saisie_verrouillee=True,
            date_saisie__gte=il_y_a_7_jours
        ).select_related('evaluation', 'evaluation__matiere', 'inscription', 'inscription__eleve')

        if not nouvelles_notes.exists():
            self.stdout.write(self.style.SUCCESS("Aucune nouvelle note validée cette semaine."))
            return

        # Grouper par inscription
        notes_par_inscription = {}
        for note in nouvelles_notes:
            insc = note.inscription
            if insc not in notes_par_inscription:
                notes_par_inscription[insc] = []
            notes_par_inscription[insc].append(note)

        emails_envoyes = 0

        for inscription, notes in notes_par_inscription.items():
            tuteurs = Tuteur.objects.filter(eleve=inscription.eleve).exclude(email='')
            
            if not tuteurs.exists():
                continue

            destinataires = [t.email for t in tuteurs]
            
            # Préparer le contexte
            context = {
                'eleve': inscription.eleve,
                'classe': inscription.classe,
                'notes': notes,
                'date_debut': il_y_a_7_jours.strftime('%d/%m/%Y'),
                'date_fin': maintenant.strftime('%d/%m/%Y'),
            }
            
            sujet = f"Bilan hebdomadaire des notes - {inscription.eleve.nom} {inscription.eleve.prenoms}"
            message_html = render_to_string('emails/bilan_hebdo.html', context)
            message_txt = render_to_string('emails/bilan_hebdo.txt', context)

            try:
                send_mail(
                    subject=sujet,
                    message=message_txt,
                    html_message=message_html,
                    from_email=None,
                    recipient_list=destinataires,
                    fail_silently=False,
                )
                emails_envoyes += len(destinataires)
                self.stdout.write(f"Email envoyé aux tuteurs de {inscription.eleve}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erreur d'envoi pour {inscription.eleve}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Opération terminée. {emails_envoyes} email(s) envoyé(s)."))
