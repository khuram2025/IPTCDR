import os
import logging
from django.db.models.functions import Length
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.db.models import Count
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from datetime import timedelta
from collections import Counter
from .project_numbers import COUNTRY_CODES
from .models import CallRecord
from django.shortcuts import render
from django.db.models.functions import Length
from django.db.models import Q,Sum, Count
from django.shortcuts import redirect
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
logger = logging.getLogger(__name__)
from django.contrib.auth.decorators import login_required
@csrf_exempt
def receive_cdr(request):
    # Path to the file where records will be saved
    records_file_path = os.path.join(os.path.dirname(__file__), 'records.txt')

    # Log the request method, URL, and headers
    logger.info(f"Received request: {request.method} {request.build_absolute_uri()}")
    logger.info(f"Request headers: {request.headers}")

    if request.method == 'POST':
        # Log the full POST data
        raw_data = request.body.decode('utf-8')
        logger.info(f"Received raw data: {raw_data}")

        # Save raw data to records.txt for debugging
        with open(records_file_path, 'a') as f:
            f.write(f"{raw_data}\n")

        # Remove 'Call ' prefix if present
        if raw_data.startswith('Call '):
            raw_data = raw_data[5:]

        # Split the data
        cdr_data = raw_data.split(',')
        logger.info(f"Parsed CDR data: {cdr_data}")

        if len(cdr_data) < 3:
            logger.error("Insufficient data fields")
            return HttpResponse("Error: Insufficient data", status=400)

        # Extract and parse the data
        call_time_str, callee, caller = cdr_data[0], cdr_data[1], cdr_data[2]
        call_time_str = f"2024-07-26 {call_time_str}"  # Prepend the date for parsing

        # Parse the date and time
        try:
            call_time = parse_datetime(call_time_str)
            if call_time is None:
                raise ValueError(f"Failed to parse datetime from string: {call_time_str}")
        except Exception as e:
            logger.error(f"Error parsing call time: {e}")
            return HttpResponse(f"Error parsing call time: {e}", status=400)

        # Save to database
        try:
            call_record = CallRecord.objects.create(
                caller=caller.strip(),
                callee=callee.strip(),
                call_time=call_time,
                external_number=callee.strip()  # Assuming external_number is the same as callee
            )
            logger.info(f"Saved call record: {call_record}")
            return HttpResponse("CDR received and processed", status=200)
        except Exception as e:
            logger.error(f"Error saving call record: {e}")
            return HttpResponse("Error processing CDR", status=500)
    else:
        logger.error("Invalid request method")
        return HttpResponse("Error: Invalid request method", status=405)
    
def get_country_from_number(number):
    # Remove any leading '+' or '00' from the number
    if number.startswith('+'):
        number = number[1:]
    elif number.startswith('00'):
        number = number[2:]
    
    # Special case for Saudi Arabia mobile numbers
    if number.startswith('05') and len(number) == 10:
        return 'Saudi Arabia'
    
    # Special case for internal company calls
    if len(number) == 4:
        return 'Internal Company Call'
    
    # General case for country codes
    for code, country in COUNTRY_CODES.items():
        if number.startswith(code):
            return country
            
    return 'Unknown'

def get_call_stats(queryset, time_period):
    now = timezone.now()
    
    if time_period == '1M':
        start_date = now - timedelta(days=30)
        date_trunc = TruncWeek
    elif time_period == '6M':
        start_date = now - timedelta(days=182)
        date_trunc = TruncMonth
    elif time_period == '1Y':
        start_date = now - timedelta(days=365)
        date_trunc = TruncMonth
    else:
        start_date = now - timedelta(days=30)
        date_trunc = TruncWeek

    call_stats = queryset.filter(call_time__range=[start_date, now]).annotate(
        date=TruncDate('call_time'),
        period=date_trunc('call_time')
    ).values('period').annotate(
        total_calls=Count('id'),
        local_calls=Count('id', filter=Q(callee__regex=r'^\d{4}$')),
        international_calls=Count('id', filter=Q(callee__startswith='00'))
    ).order_by('period')

    result = list(call_stats)
    logging.info(f"Call stats result: {result}")
    return result


from collections import Counter

@login_required
def dashboard(request):
    now = timezone.now()
    time_period = request.GET.get('time_period', 'today')
    custom_date_range = request.GET.get('custom_date', '')

    if time_period == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    elif time_period == '7d':
        start_date = now - timedelta(days=7)
        end_date = now
    elif time_period == '1m':
        start_date = now - timedelta(days=30)
        end_date = now
    elif time_period == '6m':
        start_date = now - timedelta(days=182)
        end_date = now
    elif time_period == '1y':
        start_date = now - timedelta(days=365)
        end_date = now
    elif time_period == 'custom' and custom_date_range:
        start_date_str, end_date_str = custom_date_range.split(" to ")
        start_date = timezone.datetime.strptime(start_date_str, "%d %b, %Y").replace(tzinfo=timezone.utc)
        end_date = timezone.datetime.strptime(end_date_str, "%d %b, %Y").replace(tzinfo=timezone.utc)
    else:
        start_date = now
        end_date = now

    call_records = CallRecord.objects.filter(call_time__range=[start_date, end_date])

    # Update country field if it is 'Unknown'
    for record in call_records:
        if record.country == 'Unknown':
            record.country = get_country_from_number(record.callee)
            record.save()

    # Existing statistics
    total_calls = call_records.count()
    total_external_calls = call_records.filter(
        Q(callee__regex=r'^\d{10}$') |
        Q(callee__regex=r'^\+966\d{9}$') |
        Q(callee__regex=r'^00966\d{9}$')
    ).count()
    total_international_calls = call_records.filter(callee__startswith='00').count()
    total_national_mobile_calls = call_records.annotate(callee_length=Length('callee')).filter(callee__startswith='05', callee_length=10).count()
    total_national_calls = call_records.annotate(callee_length=Length('callee')).filter(callee__startswith='0', callee_length=9).count()
    total_local_calls = call_records.annotate(callee_length=Length('callee')).filter(callee_length=4).count()

    # Calculate top talking countries
    countries = [record.country for record in call_records if record.country not in ('Unknown', 'Internal Company Call')]
    top_talking_countries = Counter(countries).most_common(10)

    # New statistics for each caller
    caller_stats = call_records.filter(from_type='Extension').values('caller', 'from_dispname').annotate(
        total_calls=Count('id'),
        total_duration=Sum('duration'),
        external_calls=Count('id', filter=Q(to_type__in=['LineSet', 'Line'])),
        external_duration=Sum('duration', filter=Q(to_type__in=['LineSet', 'Line'])),
        company_calls=Count('id', filter=Q(to_type='Extension')),
        company_duration=Sum('duration', filter=Q(to_type='Extension'))
    ).order_by('-total_calls')

    chart_time_period = request.GET.get('chart_time_period', '1M')
    call_stats = get_call_stats(CallRecord.objects, chart_time_period)

    context = {
        'call_records': call_records,
        'total_calls': total_calls,
        'total_external_calls': total_external_calls,
        'total_international_calls': total_international_calls,
        'total_national_mobile_calls': total_national_mobile_calls,
        'total_national_calls': total_national_calls,
        'total_local_calls': total_local_calls,
        'top_talking_countries': top_talking_countries,
        'time_period': time_period,
        'caller_stats': caller_stats,
        'call_stats': call_stats,
        'chart_time_period': chart_time_period,
    }
    return render(request, 'cdr/dashboard.html', context)



def update_call_stats(request):
    chart_time_period = request.GET.get('chart_time_period', '1M')
    logging.info(f"Updating call stats for period: {chart_time_period}")
    
    call_stats = get_call_stats(CallRecord.objects, chart_time_period)
    logging.info(f"Call stats result: {call_stats}")
    
    return JsonResponse(call_stats, safe=False)

def get_call_stats(queryset, time_period):
    now = timezone.now()
    
    if time_period == '1M':
        start_date = now - timedelta(days=30)
    elif time_period == '6M':
        start_date = now - timedelta(days=182)
    elif time_period == '1Y':
        start_date = now - timedelta(days=365)
    else:
        raise ValueError(f"Invalid time period: {time_period}. Must be one of '1M', '6M', '1Y'")

    call_stats = queryset.filter(call_time__range=[start_date, now]).annotate(
        date=TruncDate('call_time'),
        period=TruncMonth('call_time')  # Using TruncMonth for all periods for simplicity
    ).values('period').annotate(
        total_calls=Count('id'),
        local_calls=Count('id', filter=Q(callee__regex=r'^\d{4}$')),
        international_calls=Count('id', filter=Q(callee__startswith='00'))
    ).order_by('period')

    result = list(call_stats)
    logging.info(f"Call stats result: {result}")
    return result


def update_country(request, record_id):
    if request.method == 'POST':
        country = request.POST.get('country')
        record = CallRecord.objects.get(id=record_id)
        record.country = country
        record.save()
    return redirect('dashboard')

def all_calls_view(request):
    search_query = request.GET.get('search', '')
    per_page = request.GET.get('per_page', 100)

    # Ensure per_page is an integer, defaulting to 100 if not a valid integer
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 100

    call_records = CallRecord.objects.all()

    if search_query:
        call_records = call_records.filter(caller__icontains=search_query) | call_records.filter(callee__icontains=search_query)

    paginator = Paginator(call_records, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'cdr/all_calls1.html', {'page_obj': page_obj, 'paginator': paginator, 'search_query': search_query, 'per_page': per_page})



def outgoingExtCalls(request):
    search_query = request.GET.get('search', '')
    per_page = request.GET.get('per_page', 100)

    # Ensure per_page is an integer, defaulting to 100 if not a valid integer
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 100

    call_records = CallRecord.objects.filter(Q(to_type="LineSet") | Q(to_type="Line"))

    if search_query:
        call_records = call_records.filter(caller__icontains=search_query) | call_records.filter(callee__icontains=search_query)

    paginator = Paginator(call_records, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'cdr/outgoingExtCalls.html', {'page_obj': page_obj, 'paginator': paginator, 'search_query': search_query, 'per_page': per_page})

def incomingCalls(request):
    search_query = request.GET.get('search', '')
    per_page = request.GET.get('per_page', 100)

    # Ensure per_page is an integer, defaulting to 100 if not a valid integer
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 100

    call_records = CallRecord.objects.filter(from_type="Line")

    if search_query:
        call_records = call_records.filter(Q(caller__icontains=search_query) | Q(callee__icontains=search_query))

    paginator = Paginator(call_records, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'cdr/incomingCalls.html', {'page_obj': page_obj, 'paginator': paginator, 'search_query': search_query, 'per_page': per_page})

def outgoingInternationalCalls(request):
    search_query = request.GET.get('search', '')
    per_page = request.GET.get('per_page', 100)

    # Ensure per_page is an integer, defaulting to 100 if not a valid integer
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 100

    # Define the filtering logic
    call_records = CallRecord.objects.filter(
        Q(callee__regex=r'^\+[^9]') | 
        Q(callee__regex=r'^\+9[0-8]') | 
        Q(callee__regex=r'^00[^9]') | 
        Q(callee__regex=r'^009[0-8]')
    ).exclude(
        Q(callee__startswith='+966') | Q(callee__startswith='00966')
    )

    if search_query:
        call_records = call_records.filter(Q(caller__icontains=search_query) | Q(callee__icontains=search_query))

    paginator = Paginator(call_records, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'cdr/outgoingInternationalCalls.html', {'page_obj': page_obj, 'paginator': paginator, 'search_query': search_query, 'per_page': per_page})

def local_calls_view(request):
    call_records = CallRecord.objects.annotate(callee_length=Length('callee')).filter(callee_length=4)
    return render(request, 'cdr/local_calls.html', {'call_records': call_records})

def national_calls_view(request):
    call_records = CallRecord.objects.filter(callee__startswith='0').exclude(callee__startswith='00')
    return render(request, 'cdr/national_calls.html', {'call_records': call_records})

def international_calls_view(request):
    call_records = CallRecord.objects.annotate(callee_length=Length('callee')).filter(callee__startswith='00', callee_length__gt=10)
    return render(request, 'cdr/international_calls.html', {'call_records': call_records})

def home(request):
    return render(request, 'home/home.html')

from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET
from .models import CallRecord

from django.db.models.functions import Substr


from django.db.models.functions import Substr, Length
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

@require_GET
def get_caller_record(request):
    caller_number = request.GET.get('caller_number')
    if caller_number:
        try:
            # Using slicing to match the last 9 digits of from_no with caller_number
            caller_last_9 = caller_number[-9:]
            print(f"Caller last 9 digits: {caller_last_9}")
            
            # Annotate and filter the records
            record = CallRecord.objects.annotate(
                last_9_from_no=Substr('callee', Length('callee') - 8, 9)
            ).filter(last_9_from_no=caller_last_9).order_by('-call_time').first()
            
            if record:
               
                return HttpResponse(record.caller, status=200)
                
            else:
                print("No record found")
                return HttpResponse("", status=404)
        except Exception as e:
            print(f"Error: {e}")
            return JsonResponse({'error': str(e)}, status=500)
    else:
        print("caller_number parameter is required")
        return JsonResponse({'error': 'caller_number parameter is required'}, status=400)
    
from django.utils.text import slugify

def country_specific_calls_view(request, country_slug):
    search_query = request.GET.get('search', '')
    per_page = request.GET.get('per_page', 100)

    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 100

    # Convert slug back to country name
    country = country_slug.replace('-', ' ').title()

    call_records = CallRecord.objects.filter(country=country)

    if search_query:
        call_records = call_records.filter(Q(caller__icontains=search_query) | Q(callee__icontains=search_query))

    paginator = Paginator(call_records, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'paginator': paginator,
        'search_query': search_query,
        'per_page': per_page,
        'country': country,
    }

    return render(request, 'cdr/country_specific_calls.html', context)

from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q
from .models import CallRecord

def caller_calls_view(request, caller_number):
    search_query = request.GET.get('search', '')
    per_page = request.GET.get('per_page', 100)

    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 100

    call_records = CallRecord.objects.filter(caller=caller_number)

    if search_query:
        call_records = call_records.filter(
            Q(callee__icontains=search_query) | 
            Q(call_time__icontains=search_query)
        )

    paginator = Paginator(call_records, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'paginator': paginator,
        'search_query': search_query,
        'per_page': per_page,
        'caller_number': caller_number,
    }

    return render(request, 'cdr/caller_calls.html', context)
  