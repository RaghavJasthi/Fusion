from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("other_academic", "0023_userprofile_last_selected_role"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="last_selected_role",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
