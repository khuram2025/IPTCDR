# Phase 1 — seed VAT defaults + per-company default toll-fraud rule pack.
from decimal import Decimal

from django.db import migrations


COUNTRY_VAT = [
    # (country_code, name, rate)
    ('SA', 'KSA VAT 15%',    Decimal('15.00')),
    ('AE', 'UAE VAT 5%',     Decimal('5.00')),
    ('EG', 'Egypt VAT 14%',  Decimal('14.00')),
    ('QA', 'Qatar VAT 5%',   Decimal('5.00')),
    ('BH', 'Bahrain VAT 10%', Decimal('10.00')),
    ('OM', 'Oman VAT 5%',    Decimal('5.00')),
    ('KW', 'Kuwait VAT 0%',  Decimal('0.00')),
    ('JO', 'Jordan VAT 16%', Decimal('16.00')),
    ('GB', 'UK VAT 20%',     Decimal('20.00')),
    ('US', 'US Sales Tax 0%', Decimal('0.00')),
    ('PK', 'Pakistan Sales Tax 18%', Decimal('18.00')),
    ('IN', 'India GST 18%',  Decimal('18.00')),
]

DEFAULT_FRAUD_RULES = [
    # (name, rule_type, threshold, time_window_min, severity, action, shadow)
    ('International call spike',  'intl_spike',          Decimal('20'),    60,  'high',     'alert', True),
    ('After-hours international', 'after_hours_intl',    Decimal('5'),     60,  'medium',   'alert', True),
    ('Long international call',   'long_intl',           Decimal('1800'),  1,   'medium',   'alert', True),
    ('Velocity — calls/min',      'velocity_calls',      Decimal('30'),    1,   'high',     'alert', True),
    ('Velocity — cost/hour',      'velocity_cost',       Decimal('500'),   60,  'critical', 'disable_extension', True),
    ('Velocity — duration/day',   'velocity_duration',   Decimal('14400'), 1440, 'medium',  'alert', True),
    ('Concurrent calls',          'concurrent_calls',    Decimal('5'),     1,   'high',     'alert', True),
    ('First call to new country', 'new_destination',     Decimal('1'),     0,   'low',      'alert', True),
]

# Premium-rate / common toll-fraud destinations (extend over time)
PREMIUM_COUNTRIES = ['CU', 'KP', 'SO', 'XK', 'PG', 'AO']  # examples; tenant overrides expected


def seed(apps, schema_editor):
    TaxRule = apps.get_model('billing', 'TaxRule')
    FraudRule = apps.get_model('billing', 'FraudRule')
    Company = apps.get_model('accounts', 'Company')

    # Seed country-level tax rules (no company FK = applies to all in country)
    for code, name, rate in COUNTRY_VAT:
        TaxRule.objects.update_or_create(
            country_code=code, company=None, name=name,
            defaults={
                'rate_percent': rate,
                'applies_to': 'BOTH',
                'is_active': True,
            },
        )

    # Seed default fraud rule pack for every existing company
    for company in Company.objects.all():
        for name, rtype, threshold, window, sev, action, shadow in DEFAULT_FRAUD_RULES:
            FraudRule.objects.update_or_create(
                company=company, name=name, rule_type=rtype,
                defaults={
                    'threshold': threshold,
                    'time_window_minutes': window,
                    'severity': sev,
                    'action': action,
                    'shadow_mode': shadow,
                    'is_active': True,
                },
            )
        # Premium-destination rule with country list
        FraudRule.objects.update_or_create(
            company=company, name='Premium / high-risk destinations', rule_type='premium_destination',
            defaults={
                'threshold': Decimal('1'),
                'time_window_minutes': 1,
                'countries': PREMIUM_COUNTRIES,
                'severity': 'critical',
                'action': 'disable_extension',
                'shadow_mode': True,
                'is_active': True,
            },
        )


def reverse(apps, schema_editor):
    apps.get_model('billing', 'TaxRule').objects.all().delete()
    apps.get_model('billing', 'FraudRule').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0001_initial'),
        ('accounts', '0012_currency_and_company_locale'),
    ]

    operations = [
        migrations.RunPython(seed, reverse),
    ]
