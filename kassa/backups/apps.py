from django.apps import AppConfig


class BackupsConfig(AppConfig):
    """PostgreSQL резервтік көшірмелері: manage.py backup_db / restore_db."""

    name = 'kassa.backups'
    verbose_name = 'Резервтік көшірмелер'
