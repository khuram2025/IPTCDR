from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager, Group, Permission
from django.db.models.signals import post_save
from django.dispatch import receiver

class SMTPSettings(models.Model):
    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField(default=587)
    use_tls = models.BooleanField(default=True)
    use_ssl = models.BooleanField(default=False)
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    from_email = models.EmailField(max_length=255)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SMTP ({self.host}:{self.port}) - {self.from_email}"

class PasswordResetOTP(models.Model):
    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.created_at + timezone.timedelta(minutes=10)

    def __str__(self):
        return f"OTP for {self.user.email} ({self.otp_code})"
class Currency(models.Model):
    code = models.CharField(max_length=3, unique=True, help_text="ISO 4217 code (SAR, AED, USD)")
    name = models.CharField(max_length=64)
    symbol = models.CharField(max_length=8, help_text="Display symbol (ر.س, د.إ, $)")
    decimals = models.PositiveSmallIntegerField(default=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "Currencies"

    def __str__(self):
        return f"{self.code} ({self.symbol})"


class Company(models.Model):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)  # Ensure this field is defined
    listening_port = models.IntegerField(null=True, blank=True)
    country_code = models.CharField(
        max_length=2, default='SA',
        help_text="ISO 3166-1 alpha-2 (SA, AE, EG, QA, KW, BH, OM, JO, US, GB, PK, IN)",
    )
    currency = models.ForeignKey(
        'Currency', on_delete=models.PROTECT, null=True, blank=True,
        related_name='companies',
        help_text="Tenant billing currency. Defaults to SAR via data migration.",
    )
    vat_number = models.CharField(max_length=32, null=True, blank=True,
                                  help_text="VAT/Tax registration number for invoices")

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

        return self.create_user(email, company, password, role='superadmin', **extra_fields)

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('superadmin', 'Super Admin'),
        ('company_admin', 'Company Admin'),
        ('user', 'User (Readonly)')
    ]
    username = None  # Remove the username field
    email = models.EmailField(unique=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='users', null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    groups = models.ManyToManyField(Group, related_name='custom_user_set')
    user_permissions = models.ManyToManyField(Permission, related_name='custom_user_set')

    objects = CustomUserManager()

    REQUIRED_FIELDS = []
    USERNAME_FIELD = 'email'

    def __str__(self):
        return self.email

    def is_superadmin(self):
        return self.role == 'superadmin'

    def is_company_admin(self):
        return self.role == 'company_admin'

    def is_readonly(self):
        return self.role == 'user'


from django.db import models
from django.utils import timezone

class Extension(models.Model):
    extension = models.CharField(max_length=20)
    first_name = models.CharField(max_length=30, blank=True, null=True)
    last_name = models.CharField(max_length=30, blank=True, null=True)
    full_name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    company = models.ForeignKey('Company', on_delete=models.SET_NULL, null=True, blank=True, related_name='extensions')
    disable_external_call = models.BooleanField(default=False, help_text="If checked, external calls are disabled for this extension.")

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
        from cdr3cx.models import UserQuota
        if not UserQuota.objects.filter(extension=self).exists():
            UserQuota.objects.create(extension=self)


class Role(models.Model):
    """Custom roles with specific permissions for company-based access control"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='custom_roles')
    name = models.CharField(max_length=100, help_text="Role name (e.g., 'Sales Manager', 'Call Center Agent')")
    description = models.TextField(blank=True, help_text="Description of what this role can do")
    permissions = models.ManyToManyField(Permission, blank=True, help_text="Specific permissions for this role")
    is_active = models.BooleanField(default=True, help_text="Whether this role is currently active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('company', 'name')
        ordering = ['company', 'name']

    def __str__(self):
        return f"{self.company.name} - {self.name}"

    def get_permission_names(self):
        """Get a list of permission names for display"""
        return [perm.name for perm in self.permissions.all()]

    @property
    def permission_count(self):
        """Get the number of permissions assigned to this role"""
        return self.permissions.count()


# Update CustomUser to include custom role
class UserRole(models.Model):
    """Junction table for users and their custom roles"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='custom_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='users')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'role')

    def __str__(self):
        return f"{self.user.email} - {self.role.name}"

