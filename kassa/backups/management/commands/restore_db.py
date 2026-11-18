from django.core.management.base import BaseCommand, CommandError

from kassa.backups.services import BackupError, backup_create, backup_list, backup_restore


class Command(BaseCommand):
    help = (
        'Резервтік көшірмеден дерекқорды қалпына келтіреді. АҒЫМДАҒЫ ДЕРЕКТЕР АУЫСТЫРЫЛАДЫ. '
        'Алдымен қолданбаны (serve.py) тоқтатыңыз.'
    )

    def add_arguments(self, parser):
        parser.add_argument('file', nargs='?', help='.dump файлы; көрсетілмесе — бар көшірмелер тізімі шығады')
        parser.add_argument('--yes', action='store_true', help='Қалпына келтіруді растау (онсыз ештеңе өзгермейді)')
        parser.add_argument(
            '--no-safety-backup',
            action='store_true',
            help='Қалпына келтіру алдында ағымдағы дерекқордың көшірмесін жасамау',
        )

    def handle(self, *args, file=None, yes=False, no_safety_backup=False, **options):
        if not file:
            backups = backup_list()
            if not backups:
                self.stdout.write('Көшірмелер жоқ.')
            for path in backups:
                self.stdout.write(str(path))
            return

        if not yes:
            raise CommandError(f'{file} көшірмесі ағымдағы деректердің орнына жазылады. Растау үшін --yes қосыңыз.')
        try:
            if not no_safety_backup:
                # Қате файл таңдалса, қазіргі күйге қайта оралуға болады
                safety = backup_create()
                self.stdout.write(f'Ағымдағы дерекқордың көшірмесі: {safety}')
            backup_restore(file)
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f'Дерекқор қалпына келтірілді: {file}'))
