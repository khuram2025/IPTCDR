import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cdr.settings')  # Replace 'cdr' with your project name if different
django.setup()

# Now you can import your models
from cdr3cx.models import Company, CallPattern, CallRecord

def test_categorization():
    # Get the company
    try:
        company = Company.objects.get(name="Channab")
    except Company.DoesNotExist:
        print("Company 'Channab' not found. Please ensure it exists in the database.")
        return

    # Print all existing patterns
    print("Existing patterns:")
    for pattern in CallPattern.objects.filter(company=company):
        print(f"Pattern: {pattern.pattern}, Type: {pattern.call_type}")
    print()

    # Test numbers
    test_numbers = [
        "0502510679",  # Should match 05xxxxxxxxxx (mobile)
        "+96123456789",  # Should match +96xxxxxxxxx (international)
        "+97123456789",  # Should match +97xxxxxxxxx (international)
        "0501234567",  # Should match 05xxxxxxxxxx (mobile)
        "+1234567890",  # Should match +xxxxxxxxxxx (international)
        "0512345678",  # Should match 05XXXXXXXX (mobile)
        "96123456789",  # Should match +96xxxxxxxxx (international, without '+')
    ]

    for number in test_numbers:
        test_record = CallRecord(company=company, callee=number)
        test_record.categorize_call()
        print(f"Number: {number}, Categorized as: {test_record.call_category}")
    
    print("\nTesting with a non-matching number:")
    non_matching = CallRecord(company=company, callee="1234567890")
    non_matching.categorize_call()
    print(f"Number: 1234567890, Categorized as: {non_matching.call_category}")

if __name__ == '__main__':
    test_categorization()