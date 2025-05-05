from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_extension_email'),
    ]

    operations = [
        migrations.CreateModel(
            name='SMTPSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('host', models.CharField(max_length=255)),
                ('port', models.PositiveIntegerField(default=587)),
                ('use_tls', models.BooleanField(default=True)),
                ('use_ssl', models.BooleanField(default=False)),
                ('username', models.CharField(max_length=255)),
                ('password', models.CharField(max_length=255)),
                ('from_email', models.EmailField(max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
