from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0014_synctrack_target_video_id_max_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="syncjob",
            name="direction",
            field=models.CharField(default="one_way", max_length=20),
        ),
        migrations.AddField(
            model_name="syncjob",
            name="name",
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AlterField(
            model_name="syncjob",
            name="playlist_id",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name="syncjob",
            name="playlist_name",
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AlterField(
            model_name="syncjob",
            name="source_from",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sync_jobs_from",
                to="api.sourceconnection",
            ),
        ),
        migrations.AlterField(
            model_name="syncjob",
            name="source_to",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sync_jobs_to",
                to="api.sourceconnection",
            ),
        ),
        migrations.CreateModel(
            name="SyncJobPlaylist",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("playlist_id", models.CharField(blank=True, max_length=200)),
                ("playlist_name", models.CharField(blank=True, max_length=300)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("source", "Source"),
                            ("destination", "Destination"),
                            ("both", "Source and Destination"),
                        ],
                        default="source",
                        max_length=20,
                    ),
                ),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sync_playlists",
                        to="api.syncjob",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sync_playlists",
                        to="api.sourceconnection",
                    ),
                ),
            ],
            options={
                "db_table": "sync_job_playlists",
            },
        ),
        migrations.AddField(
            model_name="synctrack",
            name="dedupe_key",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="synctrack",
            name="source_playlist",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tracks",
                to="api.syncjobplaylist",
            ),
        ),
        migrations.CreateModel(
            name="SyncTrackMatch",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("target_video_id", models.CharField(blank=True, max_length=500)),
                ("target_title", models.CharField(blank=True, max_length=400)),
                ("match_confidence", models.FloatField(blank=True, null=True)),
                ("status", models.CharField(blank=True, max_length=20)),
                ("error", models.TextField(blank=True)),
                ("user_feedback", models.CharField(blank=True, max_length=10)),
                ("rejected_target_ids", models.JSONField(default=list)),
                ("alternatives", models.JSONField(default=list)),
                ("pushed_to_playlist", models.BooleanField(default=False)),
                (
                    "destination",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="matches",
                        to="api.syncjobplaylist",
                    ),
                ),
                (
                    "track",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="destination_matches",
                        to="api.synctrack",
                    ),
                ),
            ],
            options={
                "db_table": "sync_track_matches",
            },
        ),
    ]

