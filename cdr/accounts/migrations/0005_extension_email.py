# Generated by Django 5.0.7 on 2024-08-07 06:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_alter_extension_options_alter_extension_company_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='extension',
            name='email',
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
    ]
