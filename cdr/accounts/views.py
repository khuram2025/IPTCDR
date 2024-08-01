from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse_lazy
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.contrib.auth import logout as auth_logout

from .forms import CustomUserCreationForm, CustomAuthenticationForm, CustomPasswordResetForm
from .models import CustomUser

import datetime

def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            # Send activation email
            send_activation_email(request, user)
            return redirect('account_activation_sent')
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/signup.html', {'form': form})

def logout_view(request):
    auth_logout(request)
    return redirect('accounts:login')

def send_activation_email(request, user):
    token = default_token_generator.make_token(user)
    uidb64 = urlsafe_base64_encode(str(user.pk).encode('utf-8'))
    current_site = get_current_site(request)
    subject = 'Activate Your Account'
    message = render_to_string('accounts/activation_email.html', {
        'user': user,
        'domain': current_site.domain,
        'uid': uidb64,
        'token': token,
    })
    send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email])

def account_activation_sent(request):
    return render(request, 'accounts/account_activation_sent.html')

def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode('utf-8')
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        return redirect('home')
    else:
        return render(request, 'accounts/account_activation_invalid.html')

def login_view(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('cdr3cx:dashboard')
    else:
        form = CustomAuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

def reset_password(request):
    if request.method == 'POST':
        form = CustomPasswordResetForm(request.POST)
        if form.is_valid():
            user = CustomUser.objects.get(email=form.cleaned_data['email'])
            if user:
                otp = get_random_string(length=6, allowed_chars='1234567890')
                user.otp = otp
                user.otp_created_at = timezone.now()
                user.save()
                # Send OTP via email
                send_otp_email(user)
                return redirect('verify_otp', user_id=user.id)
    else:
        form = CustomPasswordResetForm()
    return render(request, 'accounts/reset_password.html', {'form': form})

def send_otp_email(user):
    subject = 'Password Reset OTP'
    message = f'Your OTP for password reset is {user.otp}'
    send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email])

def verify_otp(request, user_id):
    user = CustomUser.objects.get(id=user_id)
    if request.method == 'POST':
        otp = request.POST.get('otp')
        if otp == user.otp and (timezone.now() - user.otp_created_at).seconds < settings.OTP_VALIDITY_DURATION:
            return redirect('set_new_password', user_id=user.id)
    return render(request, 'accounts/verify_otp.html', {'user': user})

def set_new_password(request, user_id):
    user = CustomUser.objects.get(id=user_id)
    if request.method == 'POST':
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        if password == password_confirm:
            user.set_password(password)
            user.save()
            return redirect('login')
    return render(request, 'accounts/set_new_password.html', {'user': user})
