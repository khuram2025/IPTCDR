from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)

class CompanyValidationMiddleware:
    """
    Middleware to ensure authenticated users have a company assigned.
    Redirects to profile page if no company is assigned.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # List of URLs that don't require company check
        exempt_urls = [
            '/admin/',
            '/login/',
            '/logout/',
            '/register/',
            '/profile/',
            '/static/',
            '/media/',
            '/api/',
        ]
        
        # Check if current path should be exempt
        path_exempt = any(request.path.startswith(url) for url in exempt_urls)
        
        # If user is authenticated and path is not exempt
        if request.user.is_authenticated and not path_exempt:
            # Check if user has a company
            if not hasattr(request.user, 'company') or request.user.company is None:
                logger.warning(f"User {request.user.email} has no company assigned. Redirecting to profile.")
                messages.error(request, "You must be assigned to a company to access this page. Please contact your administrator.")
                
                # Redirect to profile or admin based on user role
                if hasattr(request.user, 'is_superuser') and request.user.is_superuser:
                    return redirect('/admin/')
                else:
                    return redirect('/profile/')  # Or wherever you want them to go
        
        response = self.get_response(request)
        return response