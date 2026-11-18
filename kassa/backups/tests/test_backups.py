import io
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest import mock, skipUnless

from django.conf import settings
from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase

from kassa.backups import services as backup


class BackupTests(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def touch(self, name):
        path = self.dir / name
        path.write_bytes(b'x')
        return path

    def test_prune_removes_only_old_backups(self):
        now = datetime(2026, 10, 28, 12, 0)
        old = self.touch('store_20261001_020000.dump')
        recent = self.touch('store_20261027_020000.dump')
        foreign = self.touch('store_manual.dump')

        removed = backup.backup_prune(14, self.dir, now=now)

        self.assertEqual(removed, [old])
        self.assertTrue(recent.exists())
        self.assertTrue(foreign.exists())

    def test_prune_keeps_newest_even_if_old(self):
        # Көшірме ұзақ жасалмай қалса да, соңғысы өшірілмеуі тиіс
        newest = self.touch('store_20260101_020000.dump')
        older = self.touch('store_20251201_020000.dump')

        removed = backup.backup_prune(14, self.dir, now=datetime(2026, 10, 28))

        self.assertEqual(removed, [older])
        self.assertTrue(newest.exists())

    def test_prune_disabled_with_zero(self):
        self.touch('store_20200101_020000.dump')
        self.touch('store_20200102_020000.dump')

        self.assertEqual(backup.backup_prune(0, self.dir), [])
        self.assertEqual(len(backup.backup_list(self.dir)), 2)

    def test_failed_dump_leaves_no_file(self):
        def fail(args):
            Path(args[args.index('--file') + 1]).write_bytes(b'half')  # pg_dump жартылай жазып үлгерді
            raise backup.BackupError('pg_dump қатемен аяқталды')

        with mock.patch.object(backup, '_run', side_effect=fail), mock.patch.object(backup, '_tool', return_value='pg'):
            with self.assertRaises(backup.BackupError):
                backup.backup_create(self.dir)

        self.assertEqual(list(self.dir.iterdir()), [])

    def test_password_not_in_command_line(self):
        with mock.patch.object(backup.subprocess, 'run') as run, mock.patch.object(backup, '_tool', return_value='pg'):
            run.return_value.returncode = 0
            backup.backup_restore(self.touch('store_20261028_020000.dump'))

        args, kwargs = run.call_args
        password = connection.settings_dict['PASSWORD']
        self.assertNotIn(password, ' '.join(args[0]))
        self.assertEqual(kwargs['env']['PGPASSWORD'], password)
        self.assertIn('--single-transaction', args[0])

    def test_restore_requires_confirmation(self):
        path = self.touch('store_20261028_020000.dump')
        with (
            mock.patch('kassa.backups.management.commands.restore_db.backup_restore') as restore,
            mock.patch('kassa.backups.management.commands.restore_db.backup_create') as safety,
        ):
            with self.assertRaisesMessage(CommandError, '--yes'):
                call_command('restore_db', str(path), stdout=io.StringIO())
        restore.assert_not_called()
        safety.assert_not_called()

    def test_restore_makes_safety_backup_first(self):
        path = self.touch('store_20261028_020000.dump')
        calls = mock.Mock()
        with (
            mock.patch('kassa.backups.management.commands.restore_db.backup_create', calls.backup),
            mock.patch('kassa.backups.management.commands.restore_db.backup_restore', calls.restore),
        ):
            call_command('restore_db', str(path), '--yes', stdout=io.StringIO())

        self.assertEqual([c[0] for c in calls.mock_calls], ['backup', 'restore'])

    @skipUnless(shutil.which('pg_dump', path=settings.BACKUP_PG_BIN or None), 'pg_dump табылмады')
    def test_real_backup_is_valid_archive(self):
        out = io.StringIO()

        call_command('backup_db', '--dir', str(self.dir), '--keep-days', '0', stdout=out)

        [dump] = backup.backup_list(self.dir)
        self.assertGreater(dump.stat().st_size, 0)
        self.assertIn('Көшірме жасалды', out.getvalue())
        # Архив ішінде қоймалық кестелер бар
        listing = backup._run([backup._tool('pg_restore'), '--list', str(dump)]).stdout
        self.assertIn('inventory_stockmovement', listing)
