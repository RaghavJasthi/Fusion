from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("other_academic", "0019_noduesrequest_clearance_file_and_more"),
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
                ],
                default="student",
                max_length=20,
            ),
        ),
    ]
