from django.db import models
from django.contrib.auth.models import User
from company.models import Company


class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('COMPANY_OWNER', 'Company Owner'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    onboarding_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

import uuid

class EmailVerification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {'Verified' if self.is_verified else 'Pending'}"

class Lead(models.Model):
    BUSINESS_TYPE_CHOICES = (
        ('Retail', 'Retail'),
        ('Pharma', 'Pharma'),
        ('Warehouse', 'Warehouse'),
        ('Other', 'Other'),
    )
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    company_name = models.CharField(max_length=200)
    business_type = models.CharField(max_length=50, choices=BUSINESS_TYPE_CHOICES)
    company_size = models.CharField(max_length=50)
    message = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, default='New')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.company_name}"

class EnterpriseLead(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    company_name = models.CharField(max_length=200)
    industry = models.CharField(max_length=100)
    number_of_users = models.CharField(max_length=50)
    required_modules = models.JSONField(default=list, blank=True)
    message = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, default='New')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.company_name} (Enterprise)"
