from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("other_academic", "0026_align_workflow_status_models"),
    ]

    operations = [
        migrations.AlterField(
            model_name="taassignment",
            name="faculty",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="ta_students",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
