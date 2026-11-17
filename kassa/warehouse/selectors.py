from kassa.common.filters import search_filter
from kassa.documents.selectors import ITEMS, RETURNS, documents_of_user_warehouse
from kassa.inventory.models import Document


def write_off_list(*, user):
    """Есептен шығарулар: Қоймашы — өз қоймасы, Басқарушы — барлығы."""
    write_offs = (
        Document.objects.filter(doc_type=Document.Type.WRITE_OFF)
        .select_related('warehouse', 'responsible', 'canceled_by')
        .prefetch_related(ITEMS)
        .order_by('-date')
    )
    return documents_of_user_warehouse(write_offs, user=user)


def receipt_list(*, user, search=None):
    """Жеткізушіден қабылдаулар қайтаруларымен. search — нөмірі (дәл)."""
    receipts = (
        Document.objects.filter(doc_type=Document.Type.RECEIPT)
        .select_related('warehouse', 'supplier', 'responsible', 'canceled_by')
        .prefetch_related(ITEMS, RETURNS)
        .order_by('-date')
    )
    return search_filter(documents_of_user_warehouse(receipts, user=user), search, ('=number',))
