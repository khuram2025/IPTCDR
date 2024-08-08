from django.shortcuts import render, redirect
from .models import CallRate
from .forms import CallRateForm
from django.http import JsonResponse
import phonenumbers
from phonenumbers import geocoder, carrier, PhoneNumberType

def call_rate_list(request):
    call_rates = CallRate.objects.all()
    return render(request, 'billing/call_rate_list.html', {'call_rates': call_rates})

def call_rate_add(request):
    if request.method == 'POST':
        form = CallRateForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('call_rate_list')
    else:
        form = CallRateForm()
    return render(request, 'billing/call_rate_form.html', {'form': form})

from django.http import JsonResponse
from .forms import CallRateForm
import logging

logger = logging.getLogger(__name__)

def get_example_number(request):
    criteria = request.GET.get('criteria')
    logger.debug(f"Received request for example number with criteria: {criteria}")
    
    if criteria:
        form = CallRateForm()
        example_number = form.get_example_number(criteria)
        logger.debug(f"Found example number: {example_number}")
        return JsonResponse({'example_number': example_number})
    
    logger.debug("No criteria provided")
    return JsonResponse({'example_number': 'No example available'})

from django.shortcuts import render
from .models import UserQuota

def user_quota_list(request):
    user_quotas = UserQuota.objects.all()
    return render(request, 'billing/user_quota_list.html', {'user_quotas': user_quotas})
