from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_merge_0003_trackfingerprint_0004_syncjob_synctrack'),
    ]

    operations = [
        # Drop the old per-platform fingerprint table
        migrations.DeleteModel(
            name='TrackFingerprint',
        ),

        # Canonical fingerprint record (one per unique recording, keyed by MBID)
        migrations.CreateModel(
            name='AudioFingerprint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mbid', models.CharField(blank=True, db_index=True, max_length=36)),
                ('isrcs', models.JSONField(default=list)),
                ('chromaprint', models.TextField(blank=True)),
                ('bpm', models.FloatField(blank=True, null=True)),
                ('key', models.CharField(blank=True, max_length=5)),
                ('mode', models.CharField(blank=True, max_length=10)),
                ('source', models.CharField(default='acoustid', max_length=20)),
                ('algo_version', models.IntegerField(default=1)),
                ('last_matched_at', models.DateTimeField(blank=True, null=True)),
                ('match_count', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'audio_fingerprints',
            },
        ),

        # Per-platform track record (many → one AudioFingerprint via MBID)
        migrations.CreateModel(
            name='TrackSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fingerprint', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='sources',
                    to='api.audiofingerprint',
                )),
                ('platform', models.CharField(max_length=20)),
                ('track_id', models.CharField(max_length=500)),
                ('url', models.URLField(blank=True, max_length=500)),
                ('title', models.CharField(blank=True, max_length=400)),
                ('artist', models.CharField(blank=True, max_length=200)),
                ('duration_ms', models.IntegerField(blank=True, null=True)),
                ('artwork_url', models.URLField(blank=True, max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'track_sources',
                'unique_together': {('platform', 'track_id')},
            },
        ),
    ]
