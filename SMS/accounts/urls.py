from django.urls import path
from .views import admin_login, admin_dashboard, admin_logout
from .import views
from django.views.generic import TemplateView

urlpatterns = [
    path('login/', admin_login, name='admin_login'),
    path('admin/dashboard/', admin_dashboard, name='admin_dashboard'),
    path('logout/', admin_logout, name='admin_logout'),

    path('admin/company/delete/<int:id>/', views.delete_company, name='delete_company'),
    path('admin/company/upgrade/<int:id>/', views.upgrade_company, name='upgrade_company'),
    path('admin/company/edit/<int:id>/', views.edit_company, name='edit_company'),
    path("admin/companies/", views.company_list, name="company_list"),
    path("admin/company-plans/", views.admin_company_plans, name="admin_company_plans"),


    path('notifications/', views.notifications, name='notifications'),

    # Marketing / Landing Page Flows
    path('start-free-trial/', views.start_free_trial, name='start_free_trial'),
    path('signup/', views.signup_view, name='signup'),
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('app/onboarding/', views.onboarding_view, name='onboarding'),
    path('book-demo/', views.book_demo, name='book_demo'),
    path('demo-confirmation/', views.demo_confirmation, name='demo_confirmation'),
    path('contact-us/', views.contact_us, name='contact_us'),
    path('thank-you-sales/', views.thank_you_sales, name='thank_you_sales'),

    # Lead Management (Admin)
    path('admin/demo-requests/', views.admin_demo_requests, name='admin_demo_requests'),
    path('admin/demo-requests/<int:id>/read/', views.mark_demo_read, name='mark_demo_read'),
    path('admin/demo-requests/<int:id>/delete/', views.delete_demo, name='delete_demo'),
    
    path('admin/contact-inquiries/', views.admin_contact_inquiries, name='admin_contact_inquiries'),
    path('admin/contact-inquiries/<int:id>/read/', views.mark_contact_read, name='mark_contact_read'),
    path('admin/contact-inquiries/<int:id>/delete/', views.delete_contact, name='delete_contact'),


    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-use/', views.terms_of_use, name='terms_of_use'),
    path('api/check-demo-duplicate/', views.check_demo_duplicate, name='check_demo_duplicate'),

    path('start-plan/<str:plan_name>/',views.start_plan,name='start_plan'),
    path('paid-signup/',views.paid_signup_view,name='paid_signup'),
	  path('signup-payment-success/',views.signup_payment_success,name='signup_payment_success'),
      
    path('payment-failed/',TemplateView.as_view(template_name='accounts/payment_failed.html'),name='payment-failed-index'),

    path('refund-cancellation-policy/', views.refund_policy, name='refund_policy'),
]