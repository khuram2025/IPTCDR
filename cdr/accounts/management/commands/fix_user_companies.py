from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import CustomUser, Company
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Fix users without company assignments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-name',
            type=str,
            help='Name of the company to assign to users without companies',
        )
        parser.add_argument(
            '--list-only',
            action='store_true',
            help='Only list users without companies, do not fix',
        )

    def handle(self, *args, **options):
        # Find all users without a company
        users_without_company = CustomUser.objects.filter(company__isnull=True)
        
        if options['list_only']:
            self.stdout.write(self.style.WARNING(f"Found {users_without_company.count()} users without companies:"))
            for user in users_without_company:
                self.stdout.write(f"  - {user.email} (Role: {user.role})")
            
            # Also show company distribution
            self.stdout.write("\n" + self.style.SUCCESS("Current company assignments:"))
            companies = Company.objects.all()
            for company in companies:
                user_count = CustomUser.objects.filter(company=company).count()
                self.stdout.write(f"  - {company.name}: {user_count} users (Port: {company.listening_port})")
            return
        
        # Fix users without companies
        if users_without_company.count() == 0:
            self.stdout.write(self.style.SUCCESS("All users have companies assigned!"))
            return
        
        self.stdout.write(self.style.WARNING(f"Found {users_without_company.count()} users without companies"))
        
        # Determine which company to use
        if options['company_name']:
            try:
                default_company = Company.objects.get(name=options['company_name'])
                self.stdout.write(self.style.SUCCESS(f"Using specified company: {default_company.name}"))
            except Company.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Company '{options['company_name']}' not found!"))
                self.stdout.write("Available companies:")
                for company in Company.objects.all():
                    self.stdout.write(f"  - {company.name}")
                return
        else:
            # Try to determine the appropriate company based on email domain
            # or prompt for manual assignment
            self.stdout.write(self.style.WARNING("No default company specified. Users need manual assignment."))
            self.stdout.write("\nAvailable companies:")
            companies = Company.objects.all()
            for idx, company in enumerate(companies, 1):
                self.stdout.write(f"  {idx}. {company.name} (Port: {company.listening_port})")
            
            self.stdout.write("\nUsers without companies:")
            for user in users_without_company:
                self.stdout.write(f"  - {user.email} (Role: {user.role})")
            
            self.stdout.write(self.style.WARNING("\nTo fix, run this command with --company-name parameter:"))
            self.stdout.write(self.style.SUCCESS("  python manage.py fix_user_companies --company-name 'Company Name'"))
            return
        
        # Assign the company to users
        with transaction.atomic():
            updated_count = 0
            for user in users_without_company:
                old_company = user.company
                user.company = default_company
                user.save()
                updated_count += 1
                self.stdout.write(f"  Updated {user.email}: None -> {default_company.name}")
            
            self.stdout.write(self.style.SUCCESS(f"\nSuccessfully updated {updated_count} users!"))