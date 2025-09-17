# Project Email Utility Documentation

## Overview
This project uses a centralized, professional SMTP utility for sending emails. SMTP settings are managed securely via the Django admin dashboard, allowing site administrators to update server info, ports, and credentials without code changes. A built-in test email feature lets admins verify configuration instantly.

## SMTP Settings Management
- **Where:** Django Admin → SMTP Settings
- **Who:** Only superusers can view or change SMTP settings.
- **Fields:** Host, Port, TLS/SSL, Username, Password, From Email, Active flag
- **Test Email:** Use the "Send Test Email" button on the change page to send a test message to any address, with customizable subject/body.
- **Security:** Passwords are masked in the admin and not exposed in logs. For debugging, only the last 2 characters are shown.

## How to Send Emails Anywhere in the Project

### 1. Import the Utility
```
from cdr.email_utils import SMTPClient
```

### 2. Send an Email
```
SMTPClient.send_email(
    subject="Your Subject",
    body="Your message body.",
    to=["recipient@example.com"],
    from_email=None,  # Optional: uses the configured default if not provided
    attachments=None,  # Optional: list of (filename, content, mimetype)
)
```
- The utility will use the active SMTPSettings from the database if available, otherwise it falls back to environment variables or settings.py.
- You can use this in views, signals, Celery tasks, management commands, etc.

### 3. Advanced Usage
- **Override SMTP settings for a single send:**
    Pass `smtp_override=<SMTPSettings instance>` to use a specific config.
- **HTML emails:**
    Pass `body` as HTML and set `headers={'Content-Type': 'text/html'}`.
- **Attachments:**
    Pass a list of attachments to the `attachments` argument.

## Example: Sending a Notification Email
```
from cdr.email_utils import SMTPClient

def notify_user(user):
    SMTPClient.send_email(
        subject="Welcome!",
        body="Hello, your account has been created.",
        to=[user.email],
    )
```

## Troubleshooting
- Use the admin test email feature to verify credentials and connectivity.
- Check the server logs for [SMTP DEBUG] output if an email fails to send.
- For authentication errors, double-check credentials, app passwords, and security settings with your SMTP provider.

## Security Best Practices
- Never hardcode SMTP passwords in code.
- Only superusers should have access to SMTP settings in admin.
- Use environment variables for sensitive defaults if not using the admin.

---

For further customization or integration help, contact the development team.
