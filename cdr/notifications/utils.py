from django.core.mail import send_mail
from django.conf import settings

def send_notification_email(recipient, subject, message):
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [recipient],
        fail_silently=False,
    )
