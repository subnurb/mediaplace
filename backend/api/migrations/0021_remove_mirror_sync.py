"""Drop all Mirror Sync tables.
Reverses migration 0020_mirror_sync.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0020_mirror_sync"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "DROP TABLE IF EXISTS mirror_match_candidates CASCADE;",
                "DROP TABLE IF EXISTS mirror_sync_items CASCADE;",
                "DROP TABLE IF EXISTS mirror_sync_runs CASCADE;",
                "DROP TABLE IF EXISTS mirror_sync_members CASCADE;",
                "DROP TABLE IF EXISTS mirror_syncs CASCADE;",
            ],
            reverse_sql=[],
        ),
    ]
