from django.db import models
from django.utils import timezone

class Notification(models.Model):
    recipient = models.EmailField()  # Recipient email address
    subject = models.CharField(max_length=255)
    message = models.TextField()
    sent_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Notification to {self.recipient}"
