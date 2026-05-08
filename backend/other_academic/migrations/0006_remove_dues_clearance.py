# Generated migration to remove StudentDues and DepartmentClearance models

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('other_academic', '0005_departmentclearance_studentdues'),
    ]

    operations = [
        migrations.DeleteModel(
            name='StudentDues',
        ),
        migrations.DeleteModel(
            name='DepartmentClearance',
        ),
    ]
