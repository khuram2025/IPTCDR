from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

print('Available Permissions in the system:')
print('=' * 50)

# Get permissions by app
permissions = Permission.objects.all().order_by('content_type__app_label', 'codename')
current_app = None

for perm in permissions:
    app_label = perm.content_type.app_label
    if app_label != current_app:
        print(f'\n[{app_label.upper()}]')
        current_app = app_label
    print(f'  {perm.codename} - {perm.name}')