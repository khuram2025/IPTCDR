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

from .forms import CustomUserCreationForm, CustomAuthenticationForm, CustomPasswordResetForm, ForgotPasswordRequestForm, ForgotPasswordOTPForm, ForgotPasswordNewPasswordForm
from .models import CustomUser, PasswordResetOTP
from cdr.email_utils import SMTPClient

import datetime
import random

# --- Modern OTP-based Password Reset Views ---
def forgot_password_request(request):
    from .forms import ForgotPasswordRequestForm
    from .models import PasswordResetOTP, CustomUser
    from cdr.email_utils import SMTPClient
    if request.method == 'POST':
        form = ForgotPasswordRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = CustomUser.objects.get(email=email, is_active=True)
            except CustomUser.DoesNotExist:
                return render(request, 'accounts/forgot_password_request.html', {'form': form, 'error': 'No active user with that email.'})
            # Generate OTP
            otp_code = f"{random.randint(100000, 999999)}"
            PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)
            otp = PasswordResetOTP.objects.create(user=user, otp_code=otp_code)
            # Send OTP email using HTML template
            from django.template.loader import render_to_string
            import datetime
            html_body = render_to_string(
                'accounts/email_otp.html',
                {
                    'otp_code': otp_code,
                    'year': datetime.datetime.now().year,
                }
            )
            SMTPClient.send_email(
                subject="Your Password Reset OTP",
                body=html_body,
                to=[user.email],
            )
            request.session['reset_user_id'] = user.id
            return redirect('accounts:forgot_password_otp')
    else:
        form = ForgotPasswordRequestForm()
    return render(request, 'accounts/forgot_password_request.html', {'form': form})

def forgot_password_otp(request):
    from .forms import ForgotPasswordOTPForm
    from .models import PasswordResetOTP, CustomUser
    user_id = request.session.get('reset_user_id')
    if not user_id:
        return redirect('accounts:forgot_password_request')
    user = CustomUser.objects.get(id=user_id)
    if request.method == 'POST':
        form = ForgotPasswordOTPForm(request.POST)
        if form.is_valid():
            otp_code = form.cleaned_data['otp_code']
            otp_obj = PasswordResetOTP.objects.filter(user=user, otp_code=otp_code, is_used=False).order_by('-created_at').first()
            if otp_obj and not otp_obj.is_expired():
                otp_obj.is_used = True
                otp_obj.save()
                request.session['otp_verified'] = True
                return redirect('accounts:forgot_password_new_password')
            else:
                return render(request, 'accounts/forgot_password_otp.html', {'form': form, 'error': 'Invalid or expired OTP.', 'email': user.email})
    else:
        form = ForgotPasswordOTPForm()
    return render(request, 'accounts/forgot_password_otp.html', {'form': form, 'email': user.email})

def forgot_password_new_password(request):
    from .forms import ForgotPasswordNewPasswordForm
    from .models import CustomUser
    user_id = request.session.get('reset_user_id')
    otp_verified = request.session.get('otp_verified')
    if not (user_id and otp_verified):
        return redirect('accounts:forgot_password_request')
    user = CustomUser.objects.get(id=user_id)
    if request.method == 'POST':
        form = ForgotPasswordNewPasswordForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data['new_password1'])
            user.save()
            del request.session['reset_user_id']
            del request.session['otp_verified']
            # Render success page, then redirect to login after delay
            response = render(request, 'accounts/forgot_password_success.html')
            response['Refresh'] = '3; url=' + str(reverse_lazy('accounts:login'))
            return response
    else:
        form = ForgotPasswordNewPasswordForm()
    return render(request, 'accounts/forgot_password_new_password.html', {'form': form})

# --- End Modern OTP-based Password Reset Views ---

def change_password(request):
    from .forms import ChangePasswordForm
    from django.contrib.auth import update_session_auth_hash
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    success = False
    error = None
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            current_password = form.cleaned_data['current_password']
            new_password = form.cleaned_data['new_password1']
            if not request.user.check_password(current_password):
                error = 'Current password is incorrect.'
            else:
                request.user.set_password(new_password)
                request.user.save()
                update_session_auth_hash(request, request.user)
                return redirect('accounts:login')
        # No need to set error here; template will display form.non_field_errors and field errors
    else:
        form = ChangePasswordForm()
    return render(request, 'accounts/change_password.html', {'form': form, 'success': success, 'error': error})


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
