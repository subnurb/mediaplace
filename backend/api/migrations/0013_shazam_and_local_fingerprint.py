import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0012_userprofile"),
    ]

    operations = [
        # ── Shazam fields on AudioFingerprint ─────────────────────────────────
        migrations.AddField(
            model_name="audiofingerprint",
            name="shazam_id",
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
        migrations.AddField(
            model_name="audiofingerprint",
            name="shazam_title",
            field=models.CharField(blank=True, max_length=400),
        ),
        migrations.AddField(
            model_name="audiofingerprint",
            name="shazam_artist",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="audiofingerprint",
            name="shazam_album",
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name="audiofingerprint",
            name="shazam_genre",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="audiofingerprint",
            name="shazam_spotify_uri",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="audiofingerprint",
            name="shazam_cover_url",
            field=models.URLField(blank=True, max_length=500),
        ),
        # ── LocalFingerprint table (Dejavu-style) ──────────────────────────────
        migrations.CreateModel(
            name="LocalFingerprint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "track_source",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="local_fingerprint",
                        to="api.tracksource",
                    ),
                ),
                ("fingerprint_hash", models.CharField(blank=True, db_index=True, max_length=64)),
                ("fingerprint_data", models.JSONField(default=list)),
                ("duration_s", models.FloatField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "local_fingerprints"},
        ),
    ]
