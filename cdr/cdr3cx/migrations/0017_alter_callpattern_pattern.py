from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cdr3cx', '0016_userquota_is_blocked'),
    ]

    operations = [
        migrations.AlterField(
            model_name='callpattern',
            name='pattern',
            field=models.CharField(
                help_text='Prefix or regex for matching callee numbers',
                max_length=128,
            ),
        ),
    ]
