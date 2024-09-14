from django.urls import reverse_lazy
from django.views import generic
from django.views import View
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .models import Notification

class NotificationListView(generic.ListView):
    model = Notification
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'

class NotificationDetailView(generic.DetailView):
    model = Notification
    template_name = 'notifications/notification_detail.html'

class NotificationCreateView(generic.CreateView):
    model = Notification
    fields = ['recipient', 'subject', 'message']
    template_name = 'notifications/notification_form.html'
    success_url = reverse_lazy('notifications:notification_list')

class NotificationUpdateView(generic.UpdateView):
    model = Notification
    fields = ['recipient', 'subject', 'message']
    template_name = 'notifications/notification_form.html'
    success_url = reverse_lazy('notifications:notification_list')

class NotificationDeleteView(generic.DeleteView):
    model = Notification
    template_name = 'notifications/notification_confirm_delete.html'
    success_url = reverse_lazy('notifications:notification_list')

class NotificationSendEmailView(View):
    def get(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk)
        return render(request, 'notifications/notification_send_email_confirm.html', {'notification': notification})

    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk)
        try:
            send_mail(
                notification.subject,
                notification.message,
                settings.DEFAULT_FROM_EMAIL,
                [notification.recipient],
                fail_silently=False,
            )
            messages.success(request, 'Email sent successfully.')
        except Exception as e:
            messages.error(request, f'Error sending email: {str(e)}')
        return redirect('notifications:notification_list')