from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from accounts.models import UserProfile

class SubscriptionCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            profile = UserProfile.objects.filter(user=request.user).first()
            if profile and profile.role == "COMPANY_OWNER":
                company = profile.company
                
                allowed_paths = [
                    reverse('pricing'),
                    reverse('create_order'),
                    reverse('payment_success'),
                    reverse('company_logout'),
                    reverse('company_settings'),
                    reverse('company_login'),
                ]
                
                if request.path.startswith('/company/') or request.path.startswith('/inventory/'):
                    if request.path not in allowed_paths:
                        is_expired = False
                        
                        if company.plan_type == 'TRIAL':
                            trial_end = company.created_at + timedelta(days=7)
                            # Using 0 days left logic, same as dashboard
                            if (trial_end.date() - timezone.now().date()).days <= 0:
                                messages.error(request, "Your trial period has expired. Upgrade now to continue using our services.")
                                is_expired = True
                        else:
                            if not company.is_subscription_active or not company.subscription_end or (company.subscription_end.date() - timezone.now().date()).days <= 0:
                                messages.error(request, f"Your {company.plan_type} plan has expired. Upgrade it to continue your work.")
                                is_expired = True
                                
                        if is_expired:
                            return redirect('pricing')
                            
        response = self.get_response(request)
        return response
