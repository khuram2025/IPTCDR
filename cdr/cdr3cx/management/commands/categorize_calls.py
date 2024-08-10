from django.core.management.base import BaseCommand
from cdr3cx.models import CallRecord

class Command(BaseCommand):
    help = 'Categorize existing call records and update country information based on the new rules'

    def handle(self, *args, **kwargs):
        call_records = CallRecord.objects.all()
        total_records = call_records.count()
        updated_records = 0

        for record in call_records:
            previous_category = record.call_category
            previous_country = record.country
            new_category = record.categorize_call()

            # If the category or country has changed, save the record
            if previous_category != new_category or previous_country != record.country:
                record.call_category = new_category
                record.save()
                updated_records += 1

        self.stdout.write(self.style.SUCCESS(
            f'Updated {updated_records} out of {total_records} call records with new categories and country information.'
        ))
