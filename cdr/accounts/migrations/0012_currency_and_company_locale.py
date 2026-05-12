# Phase 1 — multi-currency foundation.
# Adds Currency model, seeds major MENA + global currencies, and attaches
# country_code / currency / vat_number to every Company (default SAR).
from django.db import migrations, models


def seed_currencies(apps, schema_editor):
    Currency = apps.get_model('accounts', 'Currency')
    rows = [
        ('SAR', 'Saudi Riyal',          'ر.س', 2),
        ('AED', 'UAE Dirham',           'د.إ', 2),
        ('EGP', 'Egyptian Pound',       'ج.م', 2),
        ('QAR', 'Qatari Riyal',         'ر.ق', 2),
        ('KWD', 'Kuwaiti Dinar',        'د.ك', 3),
        ('BHD', 'Bahraini Dinar',       'د.ب', 3),
        ('OMR', 'Omani Rial',           'ر.ع', 3),
        ('JOD', 'Jordanian Dinar',      'د.أ', 3),
        ('USD', 'US Dollar',            '$',   2),
        ('EUR', 'Euro',                 '€',   2),
        ('GBP', 'British Pound',        '£',   2),
        ('PKR', 'Pakistani Rupee',      '₨',   2),
        ('INR', 'Indian Rupee',         '₹',   2),
    ]
    for code, name, symbol, decimals in rows:
        Currency.objects.update_or_create(
            code=code,
            defaults={'name': name, 'symbol': symbol, 'decimals': decimals, 'is_active': True},
        )


def backfill_company_currency(apps, schema_editor):
    Company = apps.get_model('accounts', 'Company')
    Currency = apps.get_model('accounts', 'Currency')
    sar = Currency.objects.get(code='SAR')
    Company.objects.filter(currency__isnull=True).update(currency=sar)


def reverse_seed(apps, schema_editor):
    Currency = apps.get_model('accounts', 'Currency')
    Currency.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_add_custom_roles'),
    ]

    operations = [
        migrations.CreateModel(
            name='Currency',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(help_text='ISO 4217 code (SAR, AED, USD)', max_length=3, unique=True)),
                ('name', models.CharField(max_length=64)),
                ('symbol', models.CharField(help_text='Display symbol (ر.س, د.إ, $)', max_length=8)),
                ('decimals', models.PositiveSmallIntegerField(default=2)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={'ordering': ['code'], 'verbose_name_plural': 'Currencies'},
        ),
        migrations.AddField(
            model_name='company',
            name='country_code',
            field=models.CharField(
                default='SA',
                help_text='ISO 3166-1 alpha-2 (SA, AE, EG, QA, KW, BH, OM, JO, US, GB, PK, IN)',
                max_length=2,
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='vat_number',
            field=models.CharField(
                blank=True, help_text='VAT/Tax registration number for invoices',
                max_length=32, null=True,
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='currency',
            field=models.ForeignKey(
                blank=True,
                help_text='Tenant billing currency. Defaults to SAR via data migration.',
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name='companies',
                to='accounts.currency',
            ),
        ),
        migrations.RunPython(seed_currencies, reverse_seed),
        migrations.RunPython(backfill_company_currency, migrations.RunPython.noop),
    ]
