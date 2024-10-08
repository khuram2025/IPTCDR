# Generated by Django 5.0.7 on 2024-07-31 19:42

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CallRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('caller', models.CharField(blank=True, max_length=20, null=True)),
                ('callee', models.CharField(max_length=20)),
                ('call_time', models.DateTimeField(null=True)),
                ('external_number', models.CharField(default='Unknown', max_length=20)),
                ('country', models.CharField(blank=True, default='Unknown', max_length=50)),
                ('duration', models.IntegerField(blank=True, null=True)),
                ('time_answered', models.DateTimeField(blank=True, null=True)),
                ('time_end', models.DateTimeField(blank=True, null=True)),
                ('reason_terminated', models.CharField(blank=True, max_length=50, null=True)),
                ('reason_changed', models.CharField(blank=True, max_length=50, null=True)),
                ('missed_queue_calls', models.CharField(blank=True, max_length=50, null=True)),
                ('from_no', models.CharField(blank=True, max_length=20, null=True)),
                ('to_no', models.CharField(blank=True, max_length=20, null=True)),
                ('to_dn', models.CharField(blank=True, max_length=20, null=True)),
                ('final_number', models.CharField(blank=True, max_length=20, null=True)),
                ('final_dn', models.CharField(blank=True, max_length=20, null=True)),
                ('from_type', models.CharField(blank=True, max_length=20, null=True)),
                ('to_type', models.CharField(blank=True, max_length=20, null=True)),
                ('final_type', models.CharField(blank=True, max_length=20, null=True)),
                ('from_dispname', models.CharField(blank=True, max_length=50, null=True)),
                ('to_dispname', models.CharField(blank=True, max_length=50, null=True)),
                ('final_dispname', models.CharField(blank=True, max_length=50, null=True)),
            ],
            options={
                'ordering': ['-call_time'],
            },
        ),
        migrations.CreateModel(
            name='RoutingRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('external_number', models.CharField(max_length=20)),
                ('original_caller', models.CharField(max_length=20)),
                ('route_to', models.CharField(max_length=20)),
            ],
        ),
    ]
