# other_academic/migrations/0001_leave.py
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Leave',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('student_name', models.CharField(max_length=255)),
                ('roll_no', models.CharField(max_length=20)),
                ('date_from', models.DateField()),
                ('date_to', models.DateField()),
                ('leave_type', models.CharField(choices=[('medical', 'Medical Leave'), ('casual', 'Casual Leave'), ('earned', 'Earned Leave'), ('emergency', 'Emergency Leave'), ('other', 'Other')], max_length=50)),
                ('related_document', models.FileField(blank=True, null=True, upload_to='leave_documents/')),
                ('address', models.TextField(blank=True)),
                ('purpose', models.TextField()),
                ('hod_credential', models.CharField(blank=True, max_length=255)),
                ('date_of_application', models.DateField(auto_now_add=True)),
                ('mobile_number', models.CharField(max_length=15)),
                ('parents_mobile', models.CharField(blank=True, max_length=15)),
                ('mobile_during_leave', models.CharField(max_length=15)),
                ('semester', models.IntegerField(blank=True, null=True)),
                ('academic_year', models.CharField(blank=True, max_length=10)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('hod_remarks', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
