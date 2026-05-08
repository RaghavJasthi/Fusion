from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('other_academic', '0007_course_courseregistration_dropcourserequest'),
    ]

    operations = [
        migrations.CreateModel(
            name='BranchChangeRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('current_branch', models.CharField(max_length=100)),
                ('requested_branch', models.CharField(max_length=100)),
                ('reason', models.TextField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('requested_date', models.DateTimeField(auto_now_add=True)),
                ('reviewed_date', models.DateTimeField(blank=True, null=True)),
                ('admin_remarks', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='branch_change_requests_reviewed', to=settings.AUTH_USER_MODEL)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='branch_change_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-requested_date'],
            },
        ),
    ]
