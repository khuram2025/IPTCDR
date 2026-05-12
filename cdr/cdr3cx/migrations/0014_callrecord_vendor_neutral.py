# Generated for Phase 1 — vendor-neutral CDR schema.
# Adds source_pbx, external_id, correlation_id, raw_data, and QoS fields to CallRecord.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cdr3cx', '0013_populate_callpattern_names'),
    ]

    operations = [
        migrations.AddField(
            model_name='callrecord',
            name='source_pbx',
            field=models.CharField(
                choices=[
                    ('3cx', '3CX'),
                    ('cisco_cucm', 'Cisco CUCM'),
                    ('ms_teams', 'Microsoft Teams'),
                    ('webex_calling', 'Webex Calling'),
                    ('zoom_phone', 'Zoom Phone'),
                    ('asterisk', 'Asterisk / FreePBX'),
                    ('yeastar', 'Yeastar'),
                    ('grandstream', 'Grandstream'),
                    ('generic_sip', 'Generic SIP'),
                    ('avaya', 'Avaya'),
                    ('mitel', 'Mitel'),
                ],
                db_index=True,
                default='3cx',
                help_text='Originating PBX platform — set by ingestion adapter',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='callrecord',
            name='external_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='PBX-side unique ID (CUCM pkid, Teams callRecord.id, Zoom call_id, etc.)',
                max_length=128,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='callrecord',
            name='correlation_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Multi-leg correlation (Webex Correlation ID, Zoom call_uuid)',
                max_length=128,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='callrecord',
            name='raw_data',
            field=models.JSONField(
                blank=True,
                help_text='Original vendor payload preserved for re-processing',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='callrecord',
            name='mos',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Mean Opinion Score 1.0-5.0',
                max_digits=4,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='callrecord',
            name='jitter_ms',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='callrecord',
            name='packet_loss_pct',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='callrecord',
            name='latency_ms',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='callrecord',
            name='codec',
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
    ]
