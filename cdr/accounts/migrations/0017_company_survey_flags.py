from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0016_company_logo'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='survey_cfd_verified',
            field=models.BooleanField(
                default=False,
                help_text='Tenant confirmed 3CX Call Flow Designer / Call Flow Apps license.',
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='survey_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Enable post-call IVR survey features for this tenant.',
            ),
        ),
    ]
