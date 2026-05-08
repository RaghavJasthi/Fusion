from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("other_academic", "0021_alter_userprofile_role_nodues_reviewers"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="role",
            field=models.CharField(
                choices=[
                    ("student", "Student"),
                    ("hod", "Head of Department"),
                    ("admin", "Admin"),
                    ("acadadmin", "Academic Admin"),
                    ("ta_supervisor", "TA Supervisor"),
                    ("thesis_supervisor", "Thesis Supervisor"),
                    ("dean_academic", "Dean Academic"),
                    ("director", "Director"),
                    ("librarian", "Librarian"),
                    ("hostel_warden", "Hostel Warden"),
                    ("mess_incharge", "Mess Incharge"),
                    ("mess_warden", "Mess Warden"),
                ],
                default="student",
                max_length=20,
            ),
        ),
    ]
