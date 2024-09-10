from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Notification
from .utils import send_notification_email

@receiver(post_save, sender=Notification)
def send_email_notification(sender, instance, **kwargs):
    send_notification_email(
        instance.recipient,
        instance.subject,
        instance.message
    )
