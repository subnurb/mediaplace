from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0006_audio_fingerprint_track_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='synctrack',
            name='user_feedback',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name='synctrack',
            name='rejected_target_ids',
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name='synctrack',
            name='alternatives',
            field=models.JSONField(default=list),
        ),
    ]
