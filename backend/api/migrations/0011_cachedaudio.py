from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0010_libraryplaylist_sync_progress"),
    ]

    operations = [
        migrations.CreateModel(
            name="CachedAudio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "track_source",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cached_audio",
                        to="api.tracksource",
                    ),
                ),
                ("file_path", models.CharField(max_length=500)),
                ("file_format", models.CharField(blank=True, max_length=20)),
                ("file_size", models.BigIntegerField(blank=True, null=True)),
                ("quality", models.CharField(blank=True, default="best", max_length=50)),
                ("downloaded_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "cached_audio"},
        ),
    ]
