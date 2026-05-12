from django.apps import AppConfig


class RealtimeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'realtime'
    verbose_name = 'Real-time wallboard'

    def ready(self):
        from . import signals  # noqa: F401
