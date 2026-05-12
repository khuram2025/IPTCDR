from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'billing'
    verbose_name = 'Billing & Fraud'

    def ready(self):
        # Connect post_save fraud evaluation
        from . import signals  # noqa: F401
