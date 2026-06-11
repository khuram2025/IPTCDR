from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('acd', '0007_alter_scheduledreport_report_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scheduledreport',
            name='report_type',
            field=models.CharField(
                choices=[
                    ('callcenter_summary', 'Call Center Summary'),
                    ('queue_performance', 'Queue Performance (real ACD)'),
                    ('agent_productivity', 'Agent Productivity'),
                    ('sla_breaches', 'SLA Breach Alerts'),
                    ('daily_volume', 'Daily Call Volume'),
                    ('cost_by_extension', 'Cost by Extension'),
                    ('missed_calls_detail', 'Missed Calls Detail'),
                    ('survey_summary', 'Survey Summary (CSAT)'),
                ],
                max_length=32,
            ),
        ),
    ]
