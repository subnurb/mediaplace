from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0007_synctrack_user_feedback'),
    ]

    operations = [
        migrations.AddField(
            model_name='syncjob',
            name='target_playlist_id',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='syncjob',
            name='target_playlist_name',
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name='syncjob',
            name='pushed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='synctrack',
            name='pushed_to_playlist',
            field=models.BooleanField(default=False),
        ),
    ]
