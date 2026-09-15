import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create and verify a consistent SQLite backup. The output contains private household data.'

    def add_arguments(self, parser):
        parser.add_argument('--output', help='New destination file; existing files are never overwritten.')

    def handle(self, *args, **options):
        source = Path(settings.DATABASES['default']['NAME']).resolve()
        target = Path(options['output']) if options['output'] else settings.DATA_DIR / 'backups' / f'flatscreen-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.sqlite3'
        target = target.resolve()
        if not source.exists() or target.exists():
            raise CommandError('Source must exist and backup destination must be new.')
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src, sqlite3.connect(target) as dst:
                src.backup(dst)
                if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise CommandError('Backup integrity check failed.')
        except sqlite3.Error as exc:
            raise CommandError(f'Backup failed: {exc}') from exc
        self.stdout.write(self.style.SUCCESS(f'Verified backup: {target}'))

