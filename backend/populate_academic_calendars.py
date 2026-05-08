#!/usr/bin/env python
"""
Script to populate sample academic calendars for testing
Run: python populate_academic_calendars.py
"""

import os
import django
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fusion.settings')
django.setup()

from django.contrib.auth.models import User
from other_academic.models import AcademicCalendar


def create_sample_calendars():
    """Create sample academic calendars for testing"""
    
    # Get or create admin user
    admin_user, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'admin@fusion.local',
            'is_staff': True,
            'is_superuser': True
        }
    )
    
    # Sample calendar data for Spring 2024
    calendars_data = [
        {
            'title': 'Spring 2024 Registration',
            'window_type': 'registration',
            'description': 'Course registration for Spring 2024 semester',
            'start_date': '2024-01-15',
            'end_date': '2024-01-25',
            'semester': 1,
            'academic_year': '2023-24',
            'status': 'active',
        },
        {
            'title': 'Spring 2024 Add/Drop Period',
            'window_type': 'add_drop',
            'description': 'Students can add or drop courses during this period',
            'start_date': '2024-01-26',
            'end_date': '2024-02-05',
            'semester': 1,
            'academic_year': '2023-24',
            'status': 'upcoming',
        },
        {
            'title': 'Spring 2024 Midterm Exams',
            'window_type': 'midterm',
            'description': 'Midterm examination period',
            'start_date': '2024-02-10',
            'end_date': '2024-02-20',
            'semester': 1,
            'academic_year': '2023-24',
            'status': 'upcoming',
        },
        {
            'title': 'Spring 2024 Final Exams',
            'window_type': 'finals',
            'description': 'Final examination period',
            'start_date': '2024-04-25',
            'end_date': '2024-05-15',
            'semester': 1,
            'academic_year': '2023-24',
            'status': 'upcoming',
        },
        {
            'title': 'Spring 2024 Grade Submission',
            'window_type': 'grade_submission',
            'description': 'Faculty must submit grades by this date',
            'start_date': '2024-05-16',
            'end_date': '2024-05-30',
            'semester': 1,
            'academic_year': '2023-24',
            'status': 'upcoming',
        },
        # Semester 2 calendars
        {
            'title': 'Fall 2024 Registration',
            'window_type': 'registration',
            'description': 'Course registration for Fall 2024 semester',
            'start_date': '2024-07-15',
            'end_date': '2024-07-25',
            'semester': 2,
            'academic_year': '2024-25',
            'status': 'upcoming',
        },
        {
            'title': 'Fall 2024 Add/Drop Period',
            'window_type': 'add_drop',
            'description': 'Students can add or drop courses during this period',
            'start_date': '2024-07-26',
            'end_date': '2024-08-05',
            'semester': 2,
            'academic_year': '2024-25',
            'status': 'upcoming',
        },
        {
            'title': 'Fall 2024 Midterm Exams',
            'window_type': 'midterm',
            'description': 'Midterm examination period',
            'start_date': '2024-08-25',
            'end_date': '2024-09-05',
            'semester': 2,
            'academic_year': '2024-25',
            'status': 'upcoming',
        },
        {
            'title': 'Fall 2024 Final Exams',
            'window_type': 'finals',
            'description': 'Final examination period',
            'start_date': '2024-10-20',
            'end_date': '2024-11-10',
            'semester': 2,
            'academic_year': '2024-25',
            'status': 'upcoming',
        },
    ]
    
    created_count = 0
    updated_count = 0
    
    for data in calendars_data:
        # Prepare dates
        data_copy = data.copy()
        data_copy['start_date'] = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        data_copy['end_date'] = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        data_copy['created_by'] = admin_user
        
        # Get or create calendar
        try:
            calendar, created = AcademicCalendar.objects.get_or_create(
                window_type=data['window_type'],
                semester=data['semester'],
                academic_year=data['academic_year'],
                defaults=data_copy
            )
            
            if created:
                print(f"✓ Created: {calendar.title} ({calendar.academic_year}, Sem {calendar.semester})")
                created_count += 1
            else:
                print(f"→ Already exists: {calendar.title}")
                updated_count += 1
                
        except Exception as e:
            print(f"✗ Error creating {data['title']}: {str(e)}")
    
    print(f"\n Summary: {created_count} created, {updated_count} already exist")
    return created_count, updated_count


if __name__ == '__main__':
    print("=" * 60)
    print("Academic Calendar Population Script")
    print("=" * 60)
    print()
    
    created, updated = create_sample_calendars()
    
    print()
    print("=" * 60)
    print("Sample calendars have been populated successfully!")
    print("=" * 60)
    print("\nYou can now:")
    print("1. View calendars at: http://127.0.0.1:8000/admin/other_academic/academiccalendar/")
    print("2. Test API endpoints:")
    print("   - List: GET /api/other-academic/calendars/")
    print("   - Validate: POST /api/other-academic/calendars/validate-action/")
    print("   - Active: GET /api/other-academic/calendars/active/?window_type=registration")
    print("3. Use the Academic Calendar Management component in the frontend")
