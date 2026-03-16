"""Drop all Soundlist-related tables.

Reverses migrations 0016, 0017, 0018.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0018_soundlist_match_candidate"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "DROP TABLE IF EXISTS soundlist_match_candidates CASCADE;",
                "DROP TABLE IF EXISTS soundlist_sync_items CASCADE;",
                "DROP TABLE IF EXISTS soundlist_sync_runs CASCADE;",
                "DROP TABLE IF EXISTS soundlist_members CASCADE;",
                "DROP TABLE IF EXISTS soundlists CASCADE;",
            ],
            reverse_sql=[],
        ),
    ]
