from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from company.models import Company
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from email.mime.image import MIMEImage 
from django.contrib.staticfiles import finders 

class Command(BaseCommand):
    help = 'Cleans up expired trial accounts and sends warning emails.'

    def handle(self, *args, **options):
        self.stdout.write('Starting trial management task...')
        
        now = timezone.now()
        
        # 1. SEND 3-DAY WARNING EMAILS
        # We send warnings to users whose trials expire in 3 days (i.e. they signed up 4 days ago)
        # Using a window to catch them on their 4th day
        warning_start = now - timedelta(days=5)
        warning_end = now - timedelta(days=4)
        
        warning_companies = Company.objects.filter(
            plan_type='TRIAL',
            created_at__gte=warning_start,
            created_at__lt=warning_end
        )
        
        warning_count = 0
        for company in warning_companies:
            # We assume the owner is the one who should receive the email
            user = company.owner
            
            # Render Email Template
            context = {
                'name': user.first_name or user.username,
                'upgrade_link': f"{settings.SITE_URL}/contact-us/",
            }
            
            html_content = render_to_string('accounts/emails/trial_warning_email.html', context)
            text_content = strip_tags(html_content)
            
            try:
                msg = EmailMultiAlternatives(
                    subject="Action Required: Your CWS Free Trial is Expiring",
                    body=text_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[user.email]
                )
                msg.attach_alternative(html_content, "text/html")
                logo_path = finders.find('accounts/images/logo.png')
                if logo_path:
                    with open(logo_path, 'rb') as f:
                        mime_image = MIMEImage(f.read())
                        mime_image.add_header('Content-ID', '<logo>')
                        msg.attach(mime_image)
                msg.send(fail_silently=True)
                warning_count += 1
            except Exception as e:
                self.stderr.write(f"Failed to send warning email to {user.email}: {str(e)}")

        self.stdout.write(self.style.SUCCESS(f'Successfully sent {warning_count} trial warning emails.'))
        
        # 2. DELETE EXPIRED TRIAL ACCOUNTS (30 Day Grace Period)
        # 7 days trial + 30 days grace period = 37 days total
        expiration_threshold = now - timedelta(days=37)
        
        expired_companies = Company.objects.filter(
            plan_type='TRIAL',
            created_at__lte=expiration_threshold
        )
        
        deleted_count, _ = expired_companies.delete()
        
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {deleted_count} expired trial companies.'))