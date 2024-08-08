from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager, Group, Permission

class Company(models.Model):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)  # Ensure this field is defined
    listening_port = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name

class CustomUserManager(BaseUserManager):
    def create_user(self, email, company=None, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)

        # Create a new company if provided, otherwise use "Channab"
        if company is None:
            company = Company.objects.get_or_create(name="Channab")[0]
        else:
            company, created = Company.objects.get_or_create(name=company)

        user = self.model(email=email, company=company, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, company=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, company, password, **extra_fields)

class CustomUser(AbstractUser):
    username = None  # Remove the username field
    email = models.EmailField(unique=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='users', null=True, blank=True)

    groups = models.ManyToManyField(Group, related_name='custom_user_set')
    user_permissions = models.ManyToManyField(Permission, related_name='custom_user_set')

    objects = CustomUserManager()

    REQUIRED_FIELDS = []
    USERNAME_FIELD = 'email'

    def __str__(self):
        return self.email


from django.db import models
from django.utils import timezone

class Extension(models.Model):
    extension = models.CharField(max_length=20)
    first_name = models.CharField(max_length=30, blank=True, null=True)
    last_name = models.CharField(max_length=30, blank=True, null=True)
    full_name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    company = models.ForeignKey('Company', on_delete=models.SET_NULL, null=True, blank=True, related_name='extensions')

    class Meta:
        unique_together = ('extension', 'company')
        ordering = ['company', 'extension']

    def __str__(self):
        return f"{self.extension} - {self.full_name or 'Unnamed'} ({self.company.name if self.company else 'No Company'})"

    def save(self, *args, **kwargs):
        if not self.full_name and (self.first_name or self.last_name):
            self.full_name = f"{self.first_name} {self.last_name}".strip()
        super().save(*args, **kwargs)

        # Ensure a UserQuota is created for this extension
        from billing.models import UserQuota
        if not UserQuota.objects.filter(extension=self).exists():
            UserQuota.objects.create(extension=self)

