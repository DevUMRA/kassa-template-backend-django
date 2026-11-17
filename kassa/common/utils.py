from datetime import datetime, time, timedelta

from django.utils import timezone


def period_bounds(date_from, date_to):
    """[date_from 00:00, date_to+1 00:00) — ағымдағы уақыт белдеуінде, екі шеті де күн бойы қамтылады."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(date_from, time.min), tz)
    end = timezone.make_aware(datetime.combine(date_to + timedelta(days=1), time.min), tz)
    return start, end
