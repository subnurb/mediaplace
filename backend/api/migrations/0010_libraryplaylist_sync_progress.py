from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0009_library_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="libraryplaylist",
            name="sync_progress",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="libraryplaylist",
            name="sync_phase",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
    ]
