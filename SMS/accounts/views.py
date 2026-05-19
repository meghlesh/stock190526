from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
import json
from company.views import client
from django.utils import timezone
from company.models import Payment
from .models import EmailVerification
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.http import HttpResponseBadRequest
from django.contrib.auth.hashers import make_password
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import logout
import re
from company.models import Company
from .models import UserProfile
email_regex = r'^[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

def delete_company(request, id):
    if request.method == "POST":
        company = get_object_or_404(Company, id=id)
        company.delete()
        messages.error(request, "Company deleted successfully.")
    return redirect('admin_dashboard')

def upgrade_company(request, id):
    if not request.user.is_superuser:
        return redirect("admin_login")
    if request.method == "POST":
        company = get_object_or_404(Company, id=id)
        plan_name = request.POST.get("plan_name", "STARTER")
        
        company.plan_type = plan_name
        company.is_subscription_active = True
        
        if company.subscription_end and company.subscription_end > timezone.now():
            company.subscription_end = company.subscription_end + timezone.timedelta(days=30)
        else:
            company.subscription_start = timezone.now()
            company.subscription_end = timezone.now() + timezone.timedelta(days=30)
            
        company.save()
        messages.success(request, f"Company '{company.name}' has been successfully upgraded to {plan_name} plan!")

    return redirect(request.META.get('HTTP_REFERER', 'admin_dashboard'))

def edit_company(request, id):
    if not request.user.is_superuser:
        return redirect("admin_login")

    company = get_object_or_404(Company, id=id)

    if request.method == "POST":
        # 16-4-26: added default "" to prevent None error + safe strip
        name = request.POST.get("company_name", "").strip()
        email = request.POST.get("company_email", "").strip()

        
        # 16-4-26: START - NAME VALIDATION (FIX FOR 500 ERROR)
        
        if not name:
            messages.error(request, "Company name cannot be empty.")
            company.name = name
            company.email = email
            return render(request, "accounts/edit_company.html", {"company": company})

        if len(name) > 50:  
            messages.error(request, "Company name cannot exceed 50 characters.")
            company.name = name
            company.email = email
            return render(request, "accounts/edit_company.html", {"company": company})
        
        # 16-4-26: END - NAME VALIDATION
        

        #  Email validation (existing logic kept)
        pattern = r'^[a-zA-Z0-9._-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            messages.error(request, "Invalid email format.")
            company.name = name
            company.email = email
            return render(request, "accounts/edit_company.html", {"company": company})

        #  Duplicate name check
        if Company.objects.filter(name__iexact=name).exclude(id=company.id).exists():
            messages.error(request, "Company name already exists.")
            company.name = name
            company.email = email
            return render(request, "accounts/edit_company.html", {"company": company})

        # 16-4-26: OPTIONAL BUT IMPORTANT - email uniqueness check
        if Company.objects.filter(email__iexact=email).exclude(id=company.id).exists():
            messages.error(request, "Company email already exists.")
            company.name = name
            company.email = email
            return render(request, "accounts/edit_company.html", {"company": company})

        #  Safe save (no more DB crash)
        company.name = name
        company.email = email
        company.save()

        messages.success(request, "Company updated successfully.")
        return redirect("admin_dashboard")

    return render(request, "accounts/edit_company.html", {"company": company})




def company_list(request):
    if not request.user.is_superuser:
        return redirect("admin_login")

    company_qs = Company.objects.select_related("owner").order_by('-id')
    total_companies = company_qs.count()
    
    paginator = Paginator(company_qs, 10) # Show 10 companies per page
    page_number = request.GET.get('page')
    companies = paginator.get_page(page_number)

    return render(
        request,
        "accounts/company_list.html",
        {"companies": companies, "total_companies": total_companies}
    )

@login_required
def admin_company_plans(request):
    if not request.user.is_superuser:
        return redirect("admin_login")

    company_qs = Company.objects.select_related("owner").order_by('-id')
    
    # Calculate remaining days for each company
    for c in company_qs:
        if c.plan_type == 'TRIAL':
            trial_end = c.created_at + timezone.timedelta(days=7)
            c.remaining_days = (trial_end.date() - timezone.now().date()).days
        elif c.is_subscription_active and c.subscription_end:
            c.remaining_days = (c.subscription_end.date() - timezone.now().date()).days
        else:
            c.remaining_days = 0
            
        if c.remaining_days < 0:
            c.remaining_days = 0
            
    total_companies = company_qs.count()
    
    paginator = Paginator(company_qs, 10)
    page_number = request.GET.get('page')
    companies = paginator.get_page(page_number)

    return render(
        request,
        "accounts/admin_company_plans.html",
        {"companies": companies, "total_companies": total_companies}
    )





# ADMIN LOGIN
def admin_login(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_superuser:
                login(request, user)

                #  SUCCESS MESSAGE (THIS WAS MISSING)
                messages.success(request, "Login successful")

                return redirect("admin_dashboard")
            else:
                messages.error(request, "You are not authorized to access admin panel.")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "accounts/admin_login.html")

# ADMIN DASHBOARD (COMPANY MANAGEMENT ONLY)

@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect("admin_login")

    # CREATE COMPANY + OWNER
    if request.method == "POST":
        # Get inputs and strip whitespace
        company_name = request.POST.get("company_name", "").strip()
        company_email = request.POST.get("company_email", "").strip()
        owner_username = request.POST.get("owner_username", "").strip()
        owner_password = request.POST.get("owner_password", "").strip()
        
        form_data = {
            "company_name": company_name,
            "company_email": company_email,
            "owner_username": owner_username,
        }
        company_qs = Company.objects.select_related("owner").order_by('-id')

        paginator = Paginator(company_qs, 10)
        page_number = request.GET.get('page')
        companies = paginator.get_page(page_number)

        base_context = {
            "companies": companies,
            "total_companies": company_qs.count(),
            "total_users": User.objects.count(),
            "form_data": form_data,
        }

        # VALIDATIONS
        def return_with_error(msg):
            messages.error(request, msg)
            request.session['form_data'] = request.POST
            return redirect("admin_dashboard")

        if not company_name:
            return return_with_error("Company Name cannot be empty or whitespace.")
        
        if len(company_name) > 50:
            return return_with_error("Company Name should not exceed 50 characters.")
        
        if not company_email:
            return return_with_error("Company Email cannot be empty.")
        
        if " " in company_email:
            return return_with_error("Please enter a valid email address.")
        
        if not re.match(email_regex, company_email):
            return return_with_error("Email must start with a letter/number and follow a valid format.")
        
        try:
            validate_email(company_email)
        except ValidationError:
            return return_with_error("Please enter a valid email address.")
        
        if Company.objects.filter(name__iexact=company_name).exists():
            return return_with_error("Company with this name already exists.")

        if Company.objects.filter(email__iexact=company_email).exists():
            return return_with_error("Company with this email already exists.")

        if not owner_username:
            return return_with_error("Owner Username cannot be empty.")
        
        if len(owner_username) > 30:
            return return_with_error("Owner Username should not exceed 30 characters.")
        if " " in owner_username:
            return return_with_error("Owner Username cannot contain spaces.")      

        if not owner_password:
            return return_with_error("Owner Password cannot be empty.")
        
        if len(owner_password) < 8 or len(owner_password) > 16:

            company_qs = Company.objects.select_related("owner").order_by('-id')

            paginator = Paginator(company_qs, 10)
            page_number = request.GET.get('page')
            companies = paginator.get_page(page_number)

            context = {
                "companies": companies,
                "total_companies": company_qs.count(),
                "total_users": User.objects.count(),
                "form_data": form_data,
                "password_error": "Owner Password must be between 8 and 16 characters.",
            }

            return render(request, "accounts/admin_dashboard.html", context)
        
        if " " in owner_password:
            return return_with_error("Owner Password cannot contain spaces.")      

        if User.objects.filter(username=owner_username).exists():
            return return_with_error(f"Username '{owner_username}' already exists.")

        # Create owner
        owner = User.objects.create_user(
            username=owner_username,
            password=owner_password
        )

        # Create company
        company = Company.objects.create(
            name=company_name,
            email=company_email,
            owner=owner
        )

        # Create user profile
        UserProfile.objects.create(
            user=owner,
            role="COMPANY_OWNER",
            company=company
        )

        messages.success(request, f"Company '{company_name}' created successfully.")
        return redirect("admin_dashboard")

    # This handles the GET request for the dashboard including pagination
    # This handles the GET request for the dashboard including pagination
    company_qs = Company.objects.select_related("owner").order_by('-id')
    total_companies = company_qs.count()
    total_users = User.objects.count()

    # Calculate pending tasks from unread Demo Requests and Contact Inquiries
    from .models import Lead, EnterpriseLead
    unread_demos = Lead.objects.filter(status='New').count()
    unread_inquiries = EnterpriseLead.objects.filter(status='New').count()
    pending_tasks = unread_demos + unread_inquiries

    paginator = Paginator(company_qs, 10)
    page_number = request.GET.get('page')
    companies = paginator.get_page(page_number)

    form_data = request.session.pop('form_data', {})

    return render(
        request,
        "accounts/admin_dashboard.html",
        {
            "companies": companies,
            "total_companies": total_companies,
            "total_users": total_users,
            "pending_tasks": pending_tasks, # Passes the dynamic count to the template
            "form_data": form_data,
        }
    )


@login_required
def notifications(request):
    return render(request, "accounts/notifications.html")


@login_required
def admin_logout(request):
    logout(request)
    return redirect("admin_login")

# --- Marketing / Landing Page Flows ---

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from email.mime.image import MIMEImage #9-5-26
from django.contrib.staticfiles import finders #9-5-26

def start_free_trial(request):
    # Smart Redirect Layer
    return redirect('/signup/?plan=starter&source=landing&utm_campaign=free_trial')

def signup_view(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        business_name = request.POST.get("business_name", "").strip()
        password = request.POST.get("password", "").strip()

        # Validation
        # Email Validation
        if User.objects.filter(email__iexact=email).exists():

            messages.error(
                request,
                "Email already exists."
            )

            return render(
                request,
                "accounts/signup.html",
            {
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "business_name": business_name,
            }
        )


# Mobile Validation
        if phone and Company.objects.filter(phone=phone).exists():

            messages.error(
                request,
                "Mobile number already registered."
            )

            return render(
               request,
               "accounts/signup.html",
            {
                  "full_name": full_name,
                  "email": email,
                  "phone": phone,
                  "business_name": business_name,
            }
        )
            
        if Company.objects.filter(name__iexact=business_name).exists():
            messages.error(
                request,
                "Company with this name already exists."
            )
            return render(
                request,
                "accounts/signup.html"
            )
        
        # Create user (inactive until verified) - Use EMAIL as username
        user = User.objects.create_user(username=email, email=email, password=password, is_active=False)
        user.first_name = full_name
        user.save()

        # Create Company (Save phone here)
        company = Company.objects.create(name=business_name, email=email, phone=phone, owner=user, plan_type='TRIAL')
        
        # Create UserProfile
        UserProfile.objects.create(user=user, role='COMPANY_OWNER', company=company)

        # Create EmailVerification
        from .models import EmailVerification
        verification = EmailVerification.objects.create(user=user)

        # 9-5-26 Send HTML Verification Email
        subject = "Verify your CWS Inventory account"
        verification_link = request.build_absolute_uri(f'/verify-email/{verification.token}/')
        html_message = render_to_string('accounts/emails/signup_email.html', {
            'name': full_name,
            'verification_link': verification_link,
        })
        plain_message = strip_tags(html_message)
        
        email_msg = EmailMultiAlternatives(subject, plain_message, settings.EMAIL_HOST_USER, [email])
        email_msg.attach_alternative(html_message, "text/html")
        logo_path = finders.find('accounts/images/logo.png')
        if logo_path:
            with open(logo_path, 'rb') as f:
                mime_image = MIMEImage(f.read())
                mime_image.add_header('Content-ID', '<logo>')
                email_msg.attach(mime_image)
        email_msg.send(fail_silently=True)

        return render(request, "accounts/check_email.html", {"email": email})

    return render(request, "accounts/signup.html")

def verify_email(request, token):
    from .models import EmailVerification
    verification = get_object_or_404(EmailVerification, token=token)
    if not verification.is_verified:
        verification.is_verified = True
        verification.save()
        user = verification.user
        user.is_active = True
        user.save()
        messages.success(request, "Email verified successfully! You can now log in.")
        return redirect('company_login')
    
    messages.info(request, "Email is already verified. Please log in.")
    return redirect('company_login')

@login_required
def onboarding_view(request):
    if request.method == "POST":
        # Mark onboarding complete
        profile = request.user.userprofile
        profile.onboarding_completed = True
        profile.save()
        return redirect('company_dashboard')
    
    return render(request, "accounts/onboarding.html")

def book_demo(request):
    from .models import Lead
    if request.method == "POST":
        name = request.POST.get("name", "")
        email = request.POST.get("email", "")
        phone = request.POST.get("phone", "")
        company_name = request.POST.get("company_name", "")
        business_type = request.POST.get("business_type", "Other")
        company_size = request.POST.get("company_size", "")
        message = request.POST.get("message", "")

        if Lead.objects.filter(email__iexact=email).exists():
            messages.error(request, "A demo request with this email already exists.")
            return render(request, "accounts/book_demo.html")
            
        if Lead.objects.filter(phone=phone).exists():
            messages.error(request, "A demo request with this phone number already exists.")
            return render(request, "accounts/book_demo.html")

        Lead.objects.create(
            name=name, email=email, phone=phone, company_name=company_name,
            business_type=business_type, company_size=company_size, message=message
        )

        # Send HTML Demo Confirmation Email
        subject = "Demo Request Confirmed - CWS Inventory"
        html_message = render_to_string('accounts/emails/demo_email.html', {
            'name': name, 'company_name': company_name, 'business_type': business_type,
        })
        plain_message = strip_tags(html_message)
        email_msg = EmailMultiAlternatives(subject, plain_message, settings.EMAIL_HOST_USER, [email])
        email_msg.attach_alternative(html_message, "text/html")
        logo_path = finders.find('accounts/images/logo.png')
        if logo_path:
            with open(logo_path, 'rb') as f:
                mime_image = MIMEImage(f.read())
                mime_image.add_header('Content-ID', '<logo>')
                email_msg.attach(mime_image)
        email_msg.send(fail_silently=True)

        return redirect('demo_confirmation')
        
    return render(request, "accounts/book_demo.html")

def demo_confirmation(request):
    return render(request, "accounts/demo_confirmation.html")

def contact_us(request):
    from .models import EnterpriseLead
    if request.method == "POST":
        name = request.POST.get("name", "")
        email = request.POST.get("email", "")
        phone = request.POST.get("phone", "")
        company_name = request.POST.get("company_name", "")
        industry = request.POST.get("industry", "")
        number_of_users = request.POST.get("number_of_users", "")
        message = request.POST.get("message", "")
        # Duplicate Email Validation
        if EnterpriseLead.objects.filter(email__iexact=email).exists():

            return JsonResponse({
                "status": "failed",
                "field": "email"
            }, status=400)

# Duplicate Phone Validation
        if EnterpriseLead.objects.filter(phone=phone).exists():

             return JsonResponse({
                 "status": "failed",
                 "field": "phone"
            }, status=400)
        
        EnterpriseLead.objects.create(
            name=name, email=email, phone=phone, company_name=company_name,
            industry=industry, number_of_users=number_of_users, message=message
        )

        # Send HTML Contact Acknowledgment Email
        subject = "Inquiry Received - CWS Inventory Enterprise"
        html_message = render_to_string('accounts/emails/contact_email.html', {
            'name': name, 'company_name': company_name, 'industry': industry,
        })
        plain_message = strip_tags(html_message)
        email_msg = EmailMultiAlternatives(subject, plain_message, settings.EMAIL_HOST_USER, [email])
        email_msg.attach_alternative(html_message, "text/html")
        logo_path = finders.find('accounts/images/logo.png')
        if logo_path:
            with open(logo_path, 'rb') as f:
                mime_image = MIMEImage(f.read())
                mime_image.add_header('Content-ID', '<logo>')
                email_msg.attach(mime_image)
        email_msg.send(fail_silently=True)

        return redirect('thank_you_sales')

    return render(request, "accounts/contact_us.html")

def thank_you_sales(request):
    return render(request, "accounts/thank_you_sales.html")

# --- Lead & Inquiry Management (Admin Dashboard) ---

@login_required
def admin_demo_requests(request):
    if not request.user.is_superuser:
        return redirect("admin_login")
    
    from .models import Lead
    demos_qs = Lead.objects.all().order_by('-created_at')
    total_demos = demos_qs.count()
    
    paginator = Paginator(demos_qs, 10)
    page_number = request.GET.get('page')
    demos = paginator.get_page(page_number)
    
    return render(request, "accounts/admin_demo_requests.html", {"demos": demos, "total_demos": total_demos})

@login_required
def mark_demo_read(request, id):
    if not request.user.is_superuser:
        return redirect("admin_login")
    if request.method == "POST":
        from .models import Lead
        demo = get_object_or_404(Lead, id=id)
        demo.status = 'Read'
        demo.save()
        messages.success(request, "Demo request marked as read.")
    return redirect(request.META.get('HTTP_REFERER', 'admin_demo_requests'))

@login_required
def delete_demo(request, id):
    if not request.user.is_superuser:
        return redirect("admin_login")
    if request.method == "POST":
        from .models import Lead
        demo = get_object_or_404(Lead, id=id)
        demo.delete()
        messages.error(request, "Demo request deleted.")
    return redirect(request.META.get('HTTP_REFERER', 'admin_demo_requests'))

@login_required
def admin_contact_inquiries(request):
    if not request.user.is_superuser:
        return redirect("admin_login")
    
    from .models import EnterpriseLead
    inquiries_qs = EnterpriseLead.objects.all().order_by('-created_at')
    total_inquiries = inquiries_qs.count()
    
    paginator = Paginator(inquiries_qs, 10)
    page_number = request.GET.get('page')
    inquiries = paginator.get_page(page_number)
    
    return render(request, "accounts/admin_contact_inquiries.html", {"inquiries": inquiries, "total_inquiries": total_inquiries})

@login_required
def mark_contact_read(request, id):
    if not request.user.is_superuser:
        return redirect("admin_login")
    if request.method == "POST":
        from .models import EnterpriseLead
        inquiry = get_object_or_404(EnterpriseLead, id=id)
        inquiry.status = 'Read'
        inquiry.save()
        messages.success(request, "Inquiry marked as read.")
    return redirect(request.META.get('HTTP_REFERER', 'admin_contact_inquiries'))

@login_required
def delete_contact(request, id):
    if not request.user.is_superuser:
        return redirect("admin_login")
    if request.method == "POST":
        from .models import EnterpriseLead
        inquiry = get_object_or_404(EnterpriseLead, id=id)
        inquiry.delete()
        messages.error(request, "Inquiry deleted.")
    return redirect(request.META.get('HTTP_REFERER', 'admin_contact_inquiries'))


def privacy_policy(request):
    return render(request, 'accounts/privacy_policy.html')

def terms_of_use(request):
    return render(request, 'accounts/terms_of_use.html')

from django.http import JsonResponse

def check_demo_duplicate(request):
    from .models import Lead
    email = request.GET.get('email', '').strip()
    phone = request.GET.get('phone', '').strip()
    
    if email and Lead.objects.filter(email__iexact=email).exists():
        return JsonResponse({'duplicate': 'email', 'message': 'A demo request with this email already exists.'})
    if phone and Lead.objects.filter(phone=phone).exists():
        return JsonResponse({'duplicate': 'phone', 'message': 'A demo request with this phone number already exists.'})
        
    return JsonResponse({'duplicate': False})




def start_plan(request, plan_name):
    VALID_PLANS = ['starter', 'business']

    if plan_name.lower() not in VALID_PLANS:
        return redirect('landing_page')
    
    return redirect(f'/paid-signup/?plan={plan_name.upper()}&source=landing&utm_campaign=paid_plan')


def paid_signup_view(request):
    plan = request.GET.get("plan", "").upper()
    VALID_PLANS = ['STARTER', 'BUSINESS']

    if plan not in VALID_PLANS:
        messages.error(request, "Invalid plan selected.")
        return redirect('index')

    if request.method == "POST":
        full_name = request.POST.get("full_name","").strip()
        email = request.POST.get("email","").strip().lower()
        phone = request.POST.get("phone","").strip()
        business_name = request.POST.get("business_name","").strip()
        password = request.POST.get("password","").strip()
        confirm_password = request.POST.get("confirm_password","").strip()

        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            return JsonResponse({"status": "failed", "field": "email", "message": "Email already exists"})

        if Company.objects.filter(name__iexact=business_name).exists():
            return JsonResponse({"status": "failed","field": "business_name","message": "Business name already exists."})
            
        if phone and Company.objects.filter(phone=phone).exists():
            return JsonResponse({"status": "failed","field": "phone","message": "Mobile number already exists."})

        hashed_password = make_password(password)

        VALID_PLANS = {"STARTER": 499,"BUSINESS": 1299}

        amount = VALID_PLANS[plan] * 100

        order_data = {
            "amount": amount,
            "currency": "INR",
            "payment_capture": 1,

            "notes": {
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "business_name": business_name,
                "password": hashed_password,
                "plan_name": plan
            }
        }

        payment_order = client.order.create(order_data)

        return JsonResponse({
            "status": "success",
            "order_id": payment_order["id"],
            "amount": payment_order["amount"],
            "razorpay_key": settings.RAZORPAY_KEY_ID,
            "plan": plan
        })
    
    return render(request,"accounts/paid_signup.html",{"plan": plan})



@csrf_exempt
def signup_payment_success(request):

    if request.method != "POST":
        return HttpResponseBadRequest("Invalid Request Method")

    try:
        payment_id = request.POST.get('razorpay_payment_id')
        order_id = request.POST.get('razorpay_order_id')
        signature = request.POST.get('razorpay_signature')

        if Payment.objects.filter(payment_id=payment_id).exists():
            return HttpResponseBadRequest("Payment already processed")

        params_dict = {
            'razorpay_payment_id': payment_id,
            'razorpay_order_id': order_id,
            'razorpay_signature': signature
        }

        client.utility.verify_payment_signature(params_dict)

        payment_data = client.payment.fetch(payment_id)

        notes = payment_data.get("notes", {})
        full_name = notes.get("full_name")
        email = notes.get("email")
        phone = notes.get("phone")
        business_name = notes.get("business_name")
        hashed_password = notes.get("password")
        plan = notes.get("plan_name")

        if payment_data['status'] != "captured":
            return redirect( 'payment-failed-index' )

        user = User.objects.create(username=email,email=email,is_active=False)

        user.first_name = full_name
        user.password = hashed_password
        user.save()

        company = Company.objects.create(
            name=business_name,
            email=email,
            phone=phone,
            owner=user,
            plan_type=plan,
            is_subscription_active=True,
            subscription_start=timezone.now(),
            subscription_end=timezone.now() + timezone.timedelta(days=30)
        )

        Payment.objects.create(
            company=company,
            plan_name=plan,
            order_id=order_id,
            payment_id=payment_id,
            razorpay_signature=signature,
            payment_status=payment_data['status'],
            amount=payment_data['amount'] / 100,
            currency=payment_data['currency'],
            is_verified=True
        )

        UserProfile.objects.create(user=user,role='COMPANY_OWNER',company=company)

        verification = EmailVerification.objects.create(user=user)

        subject = "Verify your CWS Inventory account"
        verification_link = request.build_absolute_uri(f'/verify-email/{verification.token}/')
        html_message = render_to_string('accounts/emails/signup_email.html', {
                'name': full_name,'verification_link': verification_link,
            })

        plain_message = strip_tags(html_message)
        email_msg = EmailMultiAlternatives( subject, plain_message, settings.EMAIL_HOST_USER, [email])
        email_msg.attach_alternative(html_message, "text/html")
        logo_path = finders.find('accounts/images/logo.png')

        if logo_path:
            with open(logo_path, 'rb') as f:
                mime_image = MIMEImage(f.read())
                mime_image.add_header('Content-ID', '<logo>')
                mime_image.add_header('Content-Disposition', 'inline', filename='logo.png')
                email_msg.attach(mime_image)

        email_msg.send(fail_silently=True)
        
        return render(request,"accounts/check_email.html",{"email": email})

    except Exception as e:
        print(e)
        return redirect( 'payment-failed-index' )

# def admin_dashboard(request):
#     company_qs = Company.objects.all().order_by('-id')
#     paginator = Paginator(company_qs, 10)
#     page_number = request.GET.get('page')
#     companies = paginator.get_page(page_number)
#     total_companies = company_qs.count()

#     context = {
#         'companies': companies,
#         'total_companies': total_companies,
#         # ... rest of your context
#     }
#     return render(request, 'accounts/admin_dashboard.html', context)



def refund_policy(request):
    return render(request, 'accounts/refund_policy.html')