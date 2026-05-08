from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from other_academic.models import UserProfile


class Command(BaseCommand):
    help = 'Create test users with different roles'

    def handle(self, *args, **options):
        # Create student user
        if not User.objects.filter(username='student1').exists():
            student = User.objects.create_user(
                username='student1',
                email='student1@example.com',
                password='student123',
                first_name='John',
                last_name='Doe'
            )
            UserProfile.objects.create(
                user=student,
                role='student',
                department='Computer Science',
                roll_no='21BCS001'
            )
            self.stdout.write(self.style.SUCCESS('Created student user: student1'))

        # Create HOD user
        if not User.objects.filter(username='hod1').exists():
            hod = User.objects.create_user(
                username='hod1',
                email='hod1@example.com',
                password='hod123',
                first_name='Dr.',
                last_name='Smith'
            )
            UserProfile.objects.create(
                user=hod,
                role='hod',
                department='Computer Science'
            )
            self.stdout.write(self.style.SUCCESS('Created HOD user: hod1'))

        # Create additional student user
        if not User.objects.filter(username='student2').exists():
            student2 = User.objects.create_user(
                username='student2',
                email='student2@example.com',
                password='student123',
                first_name='Jane',
                last_name='Smith'
            )
            UserProfile.objects.create(
                user=student2,
                role='student',
                department='Computer Science',
                roll_no='21BCS002'
            )
            self.stdout.write(self.style.SUCCESS('Created student user: student2'))

        if not User.objects.filter(username='librarian1').exists():
            librarian = User.objects.create_user(
                username='librarian1',
                email='librarian1@example.com',
                password='librarian123',
                first_name='Lib',
                last_name='Rarian'
            )
            UserProfile.objects.create(
                user=librarian,
                role='librarian',
                department='Library'
            )
            self.stdout.write(self.style.SUCCESS('Created librarian user: librarian1'))

        if not User.objects.filter(username='warden1').exists():
            warden = User.objects.create_user(
                username='warden1',
                email='warden1@example.com',
                password='warden123',
                first_name='Hostel',
                last_name='Warden'
            )
            UserProfile.objects.create(
                user=warden,
                role='hostel_warden',
                department='Hostel'
            )
            self.stdout.write(self.style.SUCCESS('Created hostel warden user: warden1'))

        if not User.objects.filter(username='mess1').exists():
            mess = User.objects.create_user(
                username='mess1',
                email='mess1@example.com',
                password='mess123',
                first_name='Mess',
                last_name='Incharge'
            )
            UserProfile.objects.create(
                user=mess,
                role='mess_incharge',
                department='Mess'
            )
            self.stdout.write(self.style.SUCCESS('Created mess incharge user: mess1'))

        if not User.objects.filter(username='messwarden1').exists():
            mess_warden = User.objects.create_user(
                username='messwarden1',
                email='messwarden1@example.com',
                password='messwarden123',
                first_name='Mess',
                last_name='Warden'
            )
            UserProfile.objects.create(
                user=mess_warden,
                role='mess_warden',
                department='Mess'
            )
            self.stdout.write(self.style.SUCCESS('Created mess warden user: messwarden1'))

        if not User.objects.filter(username='acadadmin1').exists():
            acadadmin = User.objects.create_user(
                username='acadadmin1',
                email='acadadmin1@example.com',
                password='acadadmin123',
                first_name='Academic',
                last_name='Admin'
            )
            UserProfile.objects.create(
                user=acadadmin,
                role='acadadmin',
                department='Academic'
            )
            self.stdout.write(self.style.SUCCESS('Created academic admin user: acadadmin1'))

        if not User.objects.filter(username='ta1').exists():
            ta_supervisor = User.objects.create_user(
                username='ta1',
                email='ta1@example.com',
                password='ta123',
                first_name='TA',
                last_name='Supervisor'
            )
            UserProfile.objects.create(
                user=ta_supervisor,
                role='ta_supervisor',
                department='CSE'
            )
            self.stdout.write(self.style.SUCCESS('Created TA supervisor user: ta1'))

        if not User.objects.filter(username='thesis1').exists():
            thesis_supervisor = User.objects.create_user(
                username='thesis1',
                email='thesis1@example.com',
                password='thesis123',
                first_name='Thesis',
                last_name='Supervisor'
            )
            UserProfile.objects.create(
                user=thesis_supervisor,
                role='thesis_supervisor',
                department='CSE'
            )
            self.stdout.write(self.style.SUCCESS('Created thesis supervisor user: thesis1'))

        if not User.objects.filter(username='dean1').exists():
            dean = User.objects.create_user(
                username='dean1',
                email='dean1@example.com',
                password='dean123',
                first_name='Dean',
                last_name='Academic'
            )
            UserProfile.objects.create(
                user=dean,
                role='dean_academic',
                department='Academic'
            )
            self.stdout.write(self.style.SUCCESS('Created dean academic user: dean1'))

        if not User.objects.filter(username='director1').exists():
            director = User.objects.create_user(
                username='director1',
                email='director1@example.com',
                password='director123',
                first_name='Director',
                last_name='User'
            )
            UserProfile.objects.create(
                user=director,
                role='director',
                department='Administration'
            )
            self.stdout.write(self.style.SUCCESS('Created director user: director1'))

        self.stdout.write(self.style.SUCCESS('Test users created successfully!'))
