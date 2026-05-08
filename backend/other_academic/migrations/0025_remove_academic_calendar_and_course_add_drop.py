from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("other_academic", "0024_alter_userprofile_last_selected_role"),
    ]

    operations = [
        migrations.DeleteModel(
            name="AcademicCalendar",
        ),
        migrations.DeleteModel(
            name="DropCourseRequest",
        ),
        migrations.DeleteModel(
            name="CourseRegistration",
        ),
    ]
