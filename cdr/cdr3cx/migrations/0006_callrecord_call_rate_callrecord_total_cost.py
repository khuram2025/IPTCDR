# Generated by Django 5.0.7 on 2024-08-09 07:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cdr3cx', '0005_callpattern_rate_per_min'),
    ]

    operations = [
        migrations.AddField(
            model_name='callrecord',
            name='call_rate',
            field=models.DecimalField(decimal_places=2, default=0.0, help_text='Rate per minute in SAR', max_digits=5),
        ),
        migrations.AddField(
            model_name='callrecord',
            name='total_cost',
            field=models.DecimalField(decimal_places=2, default=0.0, help_text='Total cost of the call', max_digits=10),
        ),
    ]
