from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
    verbose_name = 'Public REST API'

    def ready(self):
        # Connect webhook fan-out signals
        from . import signals  # noqa: F401
