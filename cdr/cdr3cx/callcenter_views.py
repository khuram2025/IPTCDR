from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from .models import CallRecord
from accounts.models import Extension
import logging

logger = logging.getLogger(__name__)

@login_required
def call_center_dashboard(request):
    """
    Call Center Dashboard showing:
    - Top IVR missed calls
    - Top agents who received calls  
    - Call center statistics
    """
    
    if not request.user.company:
        logger.error(f"User {request.user.email} has no company assigned!")
        context = {
            'error': 'No company assigned to user',
            'top_ivr_missed_calls': [],
            'top_agents': [],
            'total_ivr_calls': 0,
            'missed_calls': 0,
            'answered_calls': 0,
            'average_call_duration': 0,
        }
        return render(request, 'cdr/callcenter/dashboard.html', context)

    # Get date range (default to last 30 days)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    # Parse date filters from request
    if request.GET.get('start_date'):
        start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d')
        start_date = timezone.make_aware(start_date)
    
    if request.GET.get('end_date'):
        end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d')
        end_date = timezone.make_aware(end_date) + timedelta(days=1)  # Include full day

    # Base queryset for call center calls (IVR calls)
    call_center_calls = CallRecord.objects.filter(
        company=request.user.company,
        call_time__range=[start_date, end_date]
    ).filter(
        Q(to_type='Ivr') | Q(final_type='Ivr') | Q(to_dispname__icontains='Call Center')
    )

    # 1. Top IVR Missed Calls
    missed_calls_query = call_center_calls.filter(
        Q(final_type__isnull=True) | Q(final_type='') | Q(reason_terminated='NoAnswer')
    )
    
    top_ivr_missed_calls = missed_calls_query.values(
        'from_no', 'to_dn', 'to_dispname'
    ).annotate(
        missed_count=Count('id')
    ).order_by('-missed_count')[:10]

    # 2. Top Agents Who Received Calls
    answered_calls_query = call_center_calls.filter(
        final_type='Extension',
        final_dispname__isnull=False
    ).exclude(final_dispname='')

    top_agents = answered_calls_query.values(
        'final_dispname', 'final_dn'
    ).annotate(
        calls_received=Count('id'),
        total_duration=Sum('duration'),
        avg_duration=Avg('duration')
    ).order_by('-calls_received')[:10]

    # 3. Call Center Statistics
    total_ivr_calls = call_center_calls.count()
    missed_calls = missed_calls_query.count()
    answered_calls = answered_calls_query.count()
    
    # Average call duration for answered calls
    avg_duration_seconds = answered_calls_query.aggregate(
        avg_duration=Avg('duration')
    )['avg_duration'] or 0

    # Convert to minutes:seconds format
    if avg_duration_seconds:
        avg_minutes = int(avg_duration_seconds // 60)
        avg_seconds = int(avg_duration_seconds % 60)
        average_call_duration = f"{avg_minutes}:{avg_seconds:02d}"
    else:
        average_call_duration = "0:00"

    # 4. Recent Call Center Activity
    recent_calls = call_center_calls.order_by('-call_time')[:20]

    # 5. Top IVR Performance
    top_ivr_stats = call_center_calls.values('to_dn', 'to_dispname').annotate(
        total_calls=Count('id'),
        answered_calls=Count('id', filter=Q(final_type='Extension')),
        missed_calls=Count('id', filter=Q(final_type__isnull=True) | Q(final_type='') | Q(reason_terminated='NoAnswer')),
        total_talk_time=Sum('duration', filter=Q(final_type='Extension')),
        avg_talk_time=Avg('duration', filter=Q(final_type='Extension'))
    ).order_by('-total_calls')[:10]

    # Calculate percentages and format data for top IVRs
    for ivr in top_ivr_stats:
        if ivr['total_calls'] > 0:
            ivr['answer_rate'] = round((ivr['answered_calls'] / ivr['total_calls']) * 100, 1)
            ivr['miss_rate'] = round((ivr['missed_calls'] / ivr['total_calls']) * 100, 1)
        else:
            ivr['answer_rate'] = 0
            ivr['miss_rate'] = 0
        
        # Format talk time
        if ivr['total_talk_time']:
            hours = ivr['total_talk_time'] // 3600
            minutes = (ivr['total_talk_time'] % 3600) // 60
            ivr['total_talk_time_formatted'] = f"{hours}h {minutes}m"
        else:
            ivr['total_talk_time_formatted'] = "0h 0m"
            
        # Format average talk time
        if ivr['avg_talk_time']:
            avg_minutes = int(ivr['avg_talk_time'] // 60)
            avg_seconds = int(ivr['avg_talk_time'] % 60)
            ivr['avg_talk_time_formatted'] = f"{avg_minutes}:{avg_seconds:02d}"
        else:
            ivr['avg_talk_time_formatted'] = "0:00"

    # 6. Hourly Distribution
    hourly_calls = []
    for hour in range(24):
        hour_calls = call_center_calls.filter(
            call_time__hour=hour
        ).count()
        hourly_calls.append({
            'hour': f"{hour:02d}:00",
            'calls': hour_calls
        })

    # 6. Daily trends for the last 7 days
    daily_trends = []
    for i in range(7):
        day = (timezone.now() - timedelta(days=i)).date()
        day_start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
        day_end = day_start + timedelta(days=1)
        
        day_calls = call_center_calls.filter(
            call_time__range=[day_start, day_end]
        )
        
        day_missed = day_calls.filter(
            Q(final_type__isnull=True) | Q(final_type='') | Q(reason_terminated='NoAnswer')
        ).count()
        
        day_answered = day_calls.filter(
            final_type='Extension'
        ).count()
        
        daily_trends.append({
            'date': day.strftime('%Y-%m-%d'),
            'total_calls': day_calls.count(),
            'missed_calls': day_missed,
            'answered_calls': day_answered
        })

    daily_trends.reverse()  # Show oldest to newest

    context = {
        'top_ivr_missed_calls': top_ivr_missed_calls,
        'top_agents': top_agents,
        'top_ivr_stats': top_ivr_stats,
        'total_ivr_calls': total_ivr_calls,
        'missed_calls': missed_calls,
        'answered_calls': answered_calls,
        'average_call_duration': average_call_duration,
        'recent_calls': recent_calls,
        'hourly_calls': hourly_calls,
        'daily_trends': daily_trends,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': (end_date - timedelta(days=1)).strftime('%Y-%m-%d'),
        'missed_call_rate': round((missed_calls / total_ivr_calls * 100) if total_ivr_calls > 0 else 0, 1),
        'answer_rate': round((answered_calls / total_ivr_calls * 100) if total_ivr_calls > 0 else 0, 1),
    }

    return render(request, 'cdr/callcenter/dashboard.html', context)


@login_required 
def agent_details(request, agent_extension):
    """
    Detailed view for a specific agent's call center performance
    """
    if not request.user.company:
        return render(request, 'cdr/callcenter/agent_details.html', {'error': 'No company assigned'})

    # Get date range (default to last 30 days)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    if request.GET.get('start_date'):
        start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d')
        start_date = timezone.make_aware(start_date)
    
    if request.GET.get('end_date'):
        end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d')
        end_date = timezone.make_aware(end_date) + timedelta(days=1)

    # Get agent info
    try:
        agent_extension_obj = Extension.objects.get(
            extension=agent_extension,
            company=request.user.company
        )
        agent_name = agent_extension_obj.user.get_full_name() if agent_extension_obj.user else f"Extension {agent_extension}"
    except Extension.DoesNotExist:
        agent_name = f"Extension {agent_extension}"

    # Agent's call center calls
    agent_calls = CallRecord.objects.filter(
        company=request.user.company,
        call_time__range=[start_date, end_date],
        final_dn=agent_extension
    ).filter(
        Q(to_type='Ivr') | Q(final_type='Ivr')
    )

    # Statistics
    total_calls = agent_calls.count()
    total_duration = agent_calls.aggregate(Sum('duration'))['duration__sum'] or 0
    avg_duration = agent_calls.aggregate(Avg('duration'))['duration__avg'] or 0

    # Format durations
    total_hours = total_duration // 3600
    total_minutes = (total_duration % 3600) // 60
    total_duration_formatted = f"{total_hours}h {total_minutes}m"

    avg_minutes = int(avg_duration // 60)
    avg_seconds = int(avg_duration % 60)
    avg_duration_formatted = f"{avg_minutes}:{avg_seconds:02d}"

    # Recent calls
    recent_calls = agent_calls.order_by('-call_time')[:50]

    context = {
        'agent_extension': agent_extension,
        'agent_name': agent_name,
        'total_calls': total_calls,
        'total_duration_formatted': total_duration_formatted,
        'avg_duration_formatted': avg_duration_formatted,
        'recent_calls': recent_calls,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': (end_date - timedelta(days=1)).strftime('%Y-%m-%d'),
    }

    return render(request, 'cdr/callcenter/agent_details.html', context)


@login_required
def missed_calls_details(request):
    """
    Detailed view of missed call center calls
    """
    if not request.user.company:
        return render(request, 'cdr/callcenter/missed_calls.html', {'error': 'No company assigned'})

    # Get date range (default to last 7 days for missed calls)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=7)
    
    if request.GET.get('start_date'):
        start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d')
        start_date = timezone.make_aware(start_date)
    
    if request.GET.get('end_date'):
        end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d')
        end_date = timezone.make_aware(end_date) + timedelta(days=1)

    # Missed call center calls
    missed_calls = CallRecord.objects.filter(
        company=request.user.company,
        call_time__range=[start_date, end_date]
    ).filter(
        Q(to_type='Ivr') | Q(final_type='Ivr') | Q(to_dispname__icontains='Call Center')
    ).filter(
        Q(final_type__isnull=True) | Q(final_type='') | Q(reason_terminated='NoAnswer')
    ).order_by('-call_time')

    # Pagination could be added here if needed
    
    context = {
        'missed_calls': missed_calls,
        'total_missed': missed_calls.count(),
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': (end_date - timedelta(days=1)).strftime('%Y-%m-%d'),
    }

    return render(request, 'cdr/callcenter/missed_calls.html', context)


def format_time_difference(minutes):
    """
    Format time difference in minutes to readable format like "1D 4H 30M"
    """
    if minutes < 0:
        return "0M"

    days = int(minutes // (24 * 60))
    remaining = minutes % (24 * 60)
    hours = int(remaining // 60)
    mins = int(remaining % 60)

    parts = []
    if days > 0:
        parts.append(f"{days}D")
    if hours > 0:
        parts.append(f"{hours}H")
    if mins > 0 or len(parts) == 0:
        parts.append(f"{mins}M")

    return " ".join(parts)


@login_required
def call_back_tracking(request):
    """
    Call Back Tracking Dashboard showing:
    - Missed calls and their callback attempts
    - Callback success rates
    - Agent callback performance
    """

    if not request.user.company:
        return render(request, 'cdr/callcenter/call_back_tracking.html', {'error': 'No company assigned'})

    # Get date range (default to last 7 days for callbacks)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=7)

    if request.GET.get('start_date'):
        start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d')
        start_date = timezone.make_aware(start_date)

    if request.GET.get('end_date'):
        end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d')
        end_date = timezone.make_aware(end_date) + timedelta(days=1)

    # Get selected agent filter
    selected_agent = request.GET.get('agent')

    # 1. Find all missed IVR calls in the date range
    missed_calls = CallRecord.objects.filter(
        company=request.user.company,
        call_time__range=[start_date, end_date]
    ).filter(
        Q(to_type='Ivr') | Q(final_type='Ivr')
    ).filter(
        Q(final_type__isnull=True) | Q(final_type='') | Q(reason_terminated='NoAnswer')
    ).values('from_no').distinct()

    # Extract the phone numbers
    missed_numbers = [call['from_no'] for call in missed_calls]

    # 2. Find callback attempts (outgoing calls from extensions to missed numbers)
    callback_attempts_query = CallRecord.objects.filter(
        company=request.user.company,
        call_time__range=[start_date, end_date],
        from_type='Extension',  # Outgoing from extension
        callee__in=missed_numbers  # To numbers that missed IVR calls
    )

    # Apply agent filter if selected
    if selected_agent:
        callback_attempts_query = callback_attempts_query.filter(caller=selected_agent)

    callback_attempts = callback_attempts_query.order_by('-call_time')

    # 3. Build callback tracking data
    callback_tracking = []

    # If agent is selected, get the numbers this agent called
    if selected_agent:
        agent_called_numbers = list(callback_attempts.values_list('callee', flat=True).distinct())
        # Filter missed_numbers to only those the agent called, and remove duplicates
        relevant_missed_numbers = list(set([num for num in missed_numbers if num in agent_called_numbers]))
    else:
        relevant_missed_numbers = missed_numbers[:50]  # Limit to 50 for performance when no agent filter

    for number in relevant_missed_numbers[:100]:  # Allow more when filtering by agent
        # Get the original missed call info (most recent missed call for this number)
        original_missed = CallRecord.objects.filter(
            company=request.user.company,
            call_time__range=[start_date, end_date],
            from_no=number
        ).filter(
            Q(to_type='Ivr') | Q(final_type='Ivr')
        ).filter(
            Q(final_type__isnull=True) | Q(final_type='') | Q(reason_terminated='NoAnswer')
        ).order_by('-call_time').first()

        if not original_missed:
            continue

        # Find all callback attempts to this number AFTER the missed call
        # We want callbacks that happen AFTER the customer missed the IVR call
        callbacks_query = CallRecord.objects.filter(
            company=request.user.company,
            call_time__range=[start_date, end_date],
            from_type='Extension',
            callee=number,
            call_time__gt=original_missed.call_time  # MUST be after the missed call
        )

        # Apply agent filter if selected
        if selected_agent:
            callbacks_query = callbacks_query.filter(caller=selected_agent)

        callbacks = callbacks_query.order_by('call_time')

        callback_success = callbacks.filter(time_answered__isnull=False).exists()
        total_attempts = callbacks.count()

        if total_attempts > 0:  # Only include numbers that had callback attempts AFTER they missed
            # Get agent info for the latest callback
            latest_callback = callbacks.last()
            agent_name = "Unknown Agent"
            if latest_callback and latest_callback.caller:
                try:
                    from accounts.models import Extension
                    agent_ext = Extension.objects.get(
                        extension=latest_callback.caller,
                        company=request.user.company
                    )
                    agent_name = agent_ext.user.get_full_name() if agent_ext.user else f"Ext. {latest_callback.caller}"
                except Extension.DoesNotExist:
                    agent_name = f"Ext. {latest_callback.caller}"

            # Calculate time to callback (first callback after missed call)
            first_callback_after = callbacks.first()
            time_to_callback = (first_callback_after.call_time - original_missed.call_time).total_seconds() / 60

            # Enhance each callback with calculated time difference
            callbacks_with_time = []
            for cb in callbacks:
                minutes_diff = (cb.call_time - original_missed.call_time).total_seconds() / 60
                cb_dict = {
                    'id': cb.id,
                    'call_time': cb.call_time,
                    'time_answered': cb.time_answered,
                    'duration': cb.duration,
                    'reason_terminated': cb.reason_terminated,
                    'caller': cb.caller,
                    'callee': cb.callee,
                    'from_no': cb.from_no,
                    'to_no': cb.to_no,
                    # Calculate minutes after missed call
                    'minutes_after_missed': round(minutes_diff, 1),
                    'formatted_time_diff': format_time_difference(minutes_diff)
                }
                callbacks_with_time.append(cb_dict)

            callback_tracking.append({
                'missed_number': number,
                'missed_time': original_missed.call_time,
                'missed_ivr': original_missed.to_dn,
                'total_attempts': total_attempts,
                'successful_callback': callback_success,
                'latest_callback_time': latest_callback.call_time if latest_callback else None,
                'agent_name': agent_name,
                'agent_extension': latest_callback.caller if latest_callback else None,
                'callbacks': callbacks_with_time,
                'time_to_callback': time_to_callback,
                'formatted_response_time': format_time_difference(time_to_callback)
            })

    # Sort by latest callback time
    callback_tracking.sort(key=lambda x: x['latest_callback_time'] or timezone.now(), reverse=True)

    # 4. Summary statistics
    total_missed_with_callbacks = len(callback_tracking)
    successful_callbacks = len([ct for ct in callback_tracking if ct['successful_callback']])
    callback_success_rate = round((successful_callbacks / total_missed_with_callbacks * 100) if total_missed_with_callbacks > 0 else 0, 1)

    # 5. Agent callback performance
    agent_performance = {}
    for attempt in callback_attempts:
        agent_ext = attempt.caller
        if agent_ext not in agent_performance:
            agent_performance[agent_ext] = {
                'extension': agent_ext,
                'total_attempts': 0,
                'successful_attempts': 0,
                'total_talk_time': 0
            }

        agent_performance[agent_ext]['total_attempts'] += 1
        if attempt.time_answered:
            agent_performance[agent_ext]['successful_attempts'] += 1
            agent_performance[agent_ext]['total_talk_time'] += attempt.duration or 0

    # Convert to list and calculate success rates
    agent_performance_list = []
    for agent_data in agent_performance.values():
        success_rate = round((agent_data['successful_attempts'] / agent_data['total_attempts'] * 100) if agent_data['total_attempts'] > 0 else 0, 1)

        # Get agent name
        agent_name = f"Ext. {agent_data['extension']}"
        try:
            from accounts.models import Extension
            agent_ext = Extension.objects.get(
                extension=agent_data['extension'],
                company=request.user.company
            )
            agent_name = agent_ext.user.get_full_name() if agent_ext.user else f"Ext. {agent_data['extension']}"
        except Extension.DoesNotExist:
            pass

        agent_performance_list.append({
            'extension': agent_data['extension'],
            'name': agent_name,
            'total_attempts': agent_data['total_attempts'],
            'successful_attempts': agent_data['successful_attempts'],
            'success_rate': success_rate,
            'total_talk_time': agent_data['total_talk_time']
        })

    # Sort by total attempts
    agent_performance_list.sort(key=lambda x: x['total_attempts'], reverse=True)

    context = {
        'callback_tracking': callback_tracking,
        'agent_performance': agent_performance_list,
        'total_missed_with_callbacks': total_missed_with_callbacks,
        'successful_callbacks': successful_callbacks,
        'callback_success_rate': callback_success_rate,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': (end_date - timedelta(days=1)).strftime('%Y-%m-%d'),
        'selected_agent': selected_agent,
    }

    return render(request, 'cdr/callcenter/call_back_tracking.html', context)