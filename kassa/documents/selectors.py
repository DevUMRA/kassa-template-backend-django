from django.db.models import Prefetch

from kassa.common.filters import search_filter
from kassa.common.utils import period_bounds
from kassa.inventory.models import Document, DocumentItem
from kassa.users.selectors import user_is_manager

# Құжат жолдары тауарымен бірге (N+1 сұраныссыз)
ITEMS = Prefetch('items', queryset=DocumentItem.objects.select_related('product'))
RETURNS = Prefetch('returns', queryset=Document.objects.select_related('canceled_by').prefetch_related(ITEMS))


def documents_of_user_warehouse(queryset, *, user):
    """Басқарушы — барлық қойма; қалған рөлдер — тек өз қоймасының құжаттары."""
    return queryset if user_is_manager(user) else queryset.filter(warehouse_id=user.warehouse_id)


def document_list(*, filters=None):
    """Құжаттар журналы (Басқарушы): кез келген түр, сүзгілер — DocumentFilterSerializer нәтижесі."""
    filters = filters or {}
    queryset = (
        Document.objects.select_related('warehouse', 'supplier', 'responsible', 'canceled_by', 'base_document')
        .prefetch_related(ITEMS, 'returns')
        .order_by('-date', '-id')
    )
    for field, lookup in (('doc_type', 'doc_type'), ('status', 'status'), ('warehouse', 'warehouse_id')):
        if filters.get(field):
            queryset = queryset.filter(**{lookup: filters[field]})
    # Күн шекаралары есептердегідей — жергілікті уақыт белдеуі бойынша, екі шеті де қоса
    if filters.get('date_from'):
        queryset = queryset.filter(date__gte=period_bounds(filters['date_from'], filters['date_from'])[0])
    if filters.get('date_to'):
        queryset = queryset.filter(date__lt=period_bounds(filters['date_to'], filters['date_to'])[1])
    return search_filter(queryset, filters.get('search'), ('number',))


def document_return_get(*, document_id):
    """Жаңа жасалған қайтару құжаты — API жауабы үшін жолдарымен."""
    return Document.objects.prefetch_related(ITEMS).get(pk=document_id)
