from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0008_syncjob_push_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LibraryPlaylist",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("playlist_id", models.CharField(max_length=200)),
                ("playlist_name", models.CharField(max_length=300)),
                ("track_count", models.IntegerField(default=0)),
                ("syncing", models.BooleanField(default=False)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="library_playlists",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="library_playlists",
                        to="api.sourceconnection",
                    ),
                ),
            ],
            options={
                "db_table": "library_playlists",
                "unique_together": {("user", "source", "playlist_id")},
            },
        ),
        migrations.CreateModel(
            name="LibraryEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.IntegerField(default=0)),
                (
                    "library_playlist",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="entries",
                        to="api.libraryplaylist",
                    ),
                ),
                (
                    "track_source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="library_entries",
                        to="api.tracksource",
                    ),
                ),
            ],
            options={
                "db_table": "library_entries",
                "ordering": ["position"],
                "unique_together": {("library_playlist", "track_source")},
            },
        ),
    ]
