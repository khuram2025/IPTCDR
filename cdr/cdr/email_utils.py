import os
from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from accounts.models import SMTPSettings

class SMTPClient:
    """
    SMTP Client utility to send emails using project-wide settings.
    Reads from SMTPSettings model if available and active, else falls back to environment variables or Django settings.py.
    """
    @staticmethod
    def get_smtp_settings():
        # Try DB config first
        db_settings = SMTPSettings.objects.filter(is_active=True).order_by('-updated_at').first()
        if db_settings:
            return {
                'EMAIL_BACKEND': os.getenv('EMAIL_BACKEND', getattr(settings, 'EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')),
                'EMAIL_HOST': db_settings.host,
                'EMAIL_PORT': db_settings.port,
                'EMAIL_USE_TLS': db_settings.use_tls,
                'EMAIL_USE_SSL': db_settings.use_ssl,
                'EMAIL_HOST_USER': db_settings.username,
                'EMAIL_HOST_PASSWORD': db_settings.password,
                'FROM_EMAIL': db_settings.from_email,
            }
        # Fallback to env/settings
        return {
            'EMAIL_BACKEND': os.getenv('EMAIL_BACKEND', getattr(settings, 'EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')),
            'EMAIL_HOST': os.getenv('EMAIL_HOST', getattr(settings, 'EMAIL_HOST', 'smtp.example.com')),
            'EMAIL_PORT': int(os.getenv('EMAIL_PORT', getattr(settings, 'EMAIL_PORT', 587))),
            'EMAIL_USE_TLS': os.getenv('EMAIL_USE_TLS', str(getattr(settings, 'EMAIL_USE_TLS', True))).lower() == 'true',
            'EMAIL_USE_SSL': os.getenv('EMAIL_USE_SSL', str(getattr(settings, 'EMAIL_USE_SSL', False))).lower() == 'true',
            'EMAIL_HOST_USER': os.getenv('EMAIL_HOST_USER', getattr(settings, 'EMAIL_HOST_USER', '')),
            'EMAIL_HOST_PASSWORD': os.getenv('EMAIL_HOST_PASSWORD', getattr(settings, 'EMAIL_HOST_PASSWORD', '')),
            'FROM_EMAIL': os.getenv('DEFAULT_FROM_EMAIL', getattr(settings, 'DEFAULT_FROM_EMAIL', '')),
        }

    @staticmethod
    def send_email(subject, body, to, from_email=None, attachments=None, smtp_override=None, **kwargs):
        # If smtp_override (an SMTPSettings instance) is provided, use its values
        if smtp_override:
            smtp_settings = {
                'EMAIL_BACKEND': os.getenv('EMAIL_BACKEND', getattr(settings, 'EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')),
                'EMAIL_HOST': smtp_override.host,
                'EMAIL_PORT': smtp_override.port,
                'EMAIL_USE_TLS': smtp_override.use_tls,
                'EMAIL_USE_SSL': smtp_override.use_ssl,
                'EMAIL_HOST_USER': smtp_override.username,
                'EMAIL_HOST_PASSWORD': smtp_override.password,
                'FROM_EMAIL': smtp_override.from_email,
            }
        else:
            smtp_settings = SMTPClient.get_smtp_settings()
        print("[SMTP DEBUG] Attempting to send email with the following settings:")
        print(f"  Host: {smtp_settings['EMAIL_HOST']}")
        print(f"  Port: {smtp_settings['EMAIL_PORT']}")
        print(f"  Username: {smtp_settings['EMAIL_HOST_USER']}")
        print(f"  Use TLS: {smtp_settings['EMAIL_USE_TLS']}")
        print(f"  Use SSL: {smtp_settings['EMAIL_USE_SSL']}")
        print(f"  Backend: {smtp_settings['EMAIL_BACKEND']}")
        print(f"  From: {from_email or smtp_settings.get('FROM_EMAIL') or smtp_settings['EMAIL_HOST_USER']}")
        # Mask all but last 2 chars for security
        pw = smtp_settings['EMAIL_HOST_PASSWORD']
        if pw:
            masked_pw = '*' * (len(pw)-2) + pw[-2:] if len(pw) > 2 else '*'*len(pw)
            print(f"  Password: {masked_pw} (masked)")
        else:
            print("  Password: (empty)")
        try:
            connection = get_connection(
                backend=smtp_settings['EMAIL_BACKEND'],
                host=smtp_settings['EMAIL_HOST'],
                port=smtp_settings['EMAIL_PORT'],
                username=smtp_settings['EMAIL_HOST_USER'],
                password=smtp_settings['EMAIL_HOST_PASSWORD'],
                use_tls=smtp_settings['EMAIL_USE_TLS'],
                use_ssl=smtp_settings['EMAIL_USE_SSL'],
            )
            # Detect if the body is HTML (simple heuristic)
            if '<html' in body.lower() or '<table' in body.lower() or '<div' in body.lower():
                from django.core.mail import EmailMultiAlternatives
                email = EmailMultiAlternatives(
                    subject=subject,
                    body="This email requires an HTML-compatible email client.",
                    from_email=from_email or smtp_settings.get('FROM_EMAIL') or smtp_settings['EMAIL_HOST_USER'],
                    to=to if isinstance(to, list) else [to],
                    attachments=attachments or [],
                    connection=connection,
                    **kwargs
                )
                email.attach_alternative(body, "text/html")
            else:
                email = EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=from_email or smtp_settings.get('FROM_EMAIL') or smtp_settings['EMAIL_HOST_USER'],
                    to=to if isinstance(to, list) else [to],
                    attachments=attachments or [],
                    connection=connection,
                    **kwargs
                )
            result = email.send()
            print("[SMTP DEBUG] Email sent successfully. Result:", result)
            return result
        except Exception as e:
            import traceback
            print("[SMTP ERROR] Failed to send email:", e)
            traceback.print_exc()
            raise
