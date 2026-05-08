from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("other_academic", "0028_leave_review_tracking"),
    ]

    operations = [
        migrations.AddField(
            model_name="noduesrequest",
            name="domain_approvals",
            field=models.JSONField(blank=True, default=dict),
        ),
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
                    ("lab_incharge", "Lab Incharge"),
                    ("mess_warden", "Mess Warden"),
                ],
                default="student",
                max_length=20,
            ),
        ),
    ]
