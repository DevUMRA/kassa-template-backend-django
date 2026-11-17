import logging

from django.db import DatabaseError, connection

logger = logging.getLogger(__name__)


def database_is_available():
    """PostgreSQL жауап бере ме (healthcheck үшін)."""
    try:
        connection.ensure_connection()
    except DatabaseError:
        logger.exception('Health check: дерекқорға қосылу мүмкін емес')
        return False
    return True
