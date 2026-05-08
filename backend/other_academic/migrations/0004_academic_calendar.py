# Generated migration file for AcademicCalendar model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('other_academic', '0003_leave_name_leave_roll_number'),
    ]

    operations = [
        migrations.CreateModel(
            name='AcademicCalendar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('window_type', models.CharField(choices=[('registration', 'Registration Window'), ('add_drop', 'Add/Drop Period'), ('midterm', 'Midterm Exam'), ('finals', 'Final Exam'), ('grade_submission', 'Grade Submission'), ('other', 'Other')], max_length=50)),
                ('description', models.TextField(blank=True)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('semester', models.IntegerField()),
                ('academic_year', models.CharField(max_length=10)),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive'), ('upcoming', 'Upcoming'), ('closed', 'Closed')], default='upcoming', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='academic_calendars_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-academic_year', 'start_date'],
                'unique_together': {('window_type', 'semester', 'academic_year')},
            },
        ),
    ]
