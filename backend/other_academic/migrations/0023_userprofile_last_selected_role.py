from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("other_academic", "0022_alter_userprofile_role_mess_warden"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="last_selected_role",
            field=models.CharField(
                blank=True,
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
                max_length=20,
            ),
        ),
    ]
