from functools import reduce
from operator import and_, or_

from django.db.models import Q
from rest_framework.filters import search_smart_split

# DRF SearchFilter-дегідей: '=' — дәл сәйкестік, префикссіз — құрамында бар (регистрге қарамай)
LOOKUP_PREFIXES = {'=': 'iexact', '^': 'istartswith'}


def search_filter(queryset, search, fields):
    """`?search=` іздеуі: әр сөз өрістердің кез келгенінде болуы тиіс (DRF SearchFilter-мен бірдей ереже)."""
    terms = search_smart_split(search or '')
    if not terms:
        return queryset
    lookups = []
    for field in fields:
        lookup = LOOKUP_PREFIXES.get(field[0])
        lookups.append(f'{field[1:]}__{lookup}' if lookup else f'{field}__icontains')
    conditions = [reduce(or_, (Q(**{lookup: term}) for lookup in lookups)) for term in terms]
    return queryset.filter(reduce(and_, conditions))
