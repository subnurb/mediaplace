"""Management command to wipe all transient test data while keeping users and accounts.

Usage:
    python manage.py flush_test_data            # asks for confirmation
    python manage.py flush_test_data --yes      # skip confirmation
    python manage.py flush_test_data --dry-run  # show counts without deleting
"""

import os

from django.core.management.base import BaseCommand

from api.models import (
    AudioFingerprint,
    CachedAudio,
    LibraryEntry,
    LibraryPlaylist,
    PendingJob,
    SyncJob,
    SyncTrack,
    TrackSource,
)


class Command(BaseCommand):
    help = (
        "Delete all tracks, sync jobs, library data, audio cache and fingerprints. "
        "Users and SourceConnections (platform accounts) are kept intact."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip the confirmation prompt.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print record counts without deleting anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        counts = {
            "LibraryEntry":     LibraryEntry.objects.count(),
            "LibraryPlaylist":  LibraryPlaylist.objects.count(),
            "SyncTrack":        SyncTrack.objects.count(),
            "SyncJob":          SyncJob.objects.count(),
            "CachedAudio":      CachedAudio.objects.count(),
            "AudioFingerprint": AudioFingerprint.objects.count(),
            "TrackSource":      TrackSource.objects.count(),
            "PendingJob":       PendingJob.objects.count(),
        }

        self.stdout.write("\nRecords that will be deleted:")
        for model, count in counts.items():
            color = self.style.WARNING if count else self.style.SUCCESS
            self.stdout.write(f"  {model:<20} {color(str(count))}")

        if dry_run:
            self.stdout.write(self.style.NOTICE("\nDry run — nothing deleted."))
            return

        if not options["yes"]:
            confirm = input(
                "\nThis will permanently delete all the rows above. "
                "Users and platform accounts are NOT affected.\n"
                "Type 'yes' to continue: "
            )
            if confirm.strip().lower() != "yes":
                self.stdout.write(self.style.ERROR("Aborted."))
                return

        # Collect cached audio file paths before deleting rows
        audio_paths = list(
            CachedAudio.objects.values_list("file_path", flat=True)
        )

        # Delete in dependency order (children first)
        LibraryEntry.objects.all().delete()
        LibraryPlaylist.objects.all().delete()
        SyncTrack.objects.all().delete()
        SyncJob.objects.all().delete()
        CachedAudio.objects.all().delete()
        AudioFingerprint.objects.all().delete()
        TrackSource.objects.all().delete()
        PendingJob.objects.all().delete()

        # Remove cached audio files from disk
        removed = 0
        missing = 0
        for path in audio_paths:
            if path and os.path.isfile(path):
                try:
                    os.remove(path)
                    removed += 1
                except OSError:
                    pass
            else:
                missing += 1

        self.stdout.write(self.style.SUCCESS("\nDone."))
        self.stdout.write(f"  Audio files deleted from disk : {removed}")
        if missing:
            self.stdout.write(f"  Audio files already gone     : {missing}")
        self.stdout.write(
            self.style.NOTICE(
                "\nUsers and SourceConnections (platform accounts) were NOT touched."
            )
        )
