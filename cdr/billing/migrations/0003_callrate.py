# Generated by Django 5.0.7 on 2024-08-08 02:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0002_alter_userquota_start_date'),
    ]

    operations = [
        migrations.CreateModel(
            name='CallRate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('call_type', models.CharField(choices=[('off_net', 'Off-Net Calls'), ('mobile', 'Mobile'), ('uan_9200', 'UAN (9200)'), ('uan_calling', 'UAN Calling Party'), ('uan_called', 'UAN Called Party'), ('toll_free_on_net', 'Toll Free (inbound- on Net)'), ('toll_free_off_net', 'Toll Free (inbound- off Net)'), ('inbound_toll_free_mobile', 'Inbound Toll-Free (Mobile)'), ('inbound_toll_free_uan_9200', 'Inbound Toll-Free (UAN-9200)'), ('international', 'International Calls')], max_length=50, unique=True)),
                ('rate_per_min', models.DecimalField(decimal_places=2, default=0.0, max_digits=5)),
                ('matching_criteria', models.CharField(blank=True, help_text='Comma separated list of matching criteria numbers', max_length=255)),
            ],
        ),
    ]
