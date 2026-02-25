from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_sourceconnection_delete_youtubecredential'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrackFingerprint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform', models.CharField(max_length=20)),
                ('track_id', models.CharField(max_length=200)),
                ('mbid', models.CharField(blank=True, max_length=36)),
                ('isrcs', models.JSONField(default=list)),
                ('bpm', models.FloatField(blank=True, null=True)),
                ('key', models.CharField(blank=True, max_length=5)),
                ('mode', models.CharField(blank=True, max_length=10)),
                ('source', models.CharField(default='acoustid', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'track_fingerprints',
                'unique_together': {('platform', 'track_id')},
            },
        ),
    ]
