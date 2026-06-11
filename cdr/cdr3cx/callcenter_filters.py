"""Shared, case-insensitive filters for call-center analytics."""
from django.db.models import Q


def call_center_call_filter():
    """IVR / call-center calls regardless of 3CX casing drift."""
    return (
        Q(to_type__iexact='ivr')
        | Q(final_type__iexact='ivr')
        | Q(to_dispname__icontains='Call Center')
    )


def answered_call_filter():
    """Calls that reached an extension agent."""
    return Q(final_type__iexact='extension') & Q(time_answered__isnull=False)


def missed_call_filter():
    """Unanswered call-center calls (NoAnswer is absent in live data)."""
    return Q(time_answered__isnull=True)
