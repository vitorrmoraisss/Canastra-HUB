from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_merge_20260610_2009"),
    ]

    operations = [
        migrations.AddField(
            model_name="hub",
            name="area_foco_hub",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="hub",
            name="tecnologias_hub",
            field=models.TextField(blank=True, default=""),
        ),
    ]
