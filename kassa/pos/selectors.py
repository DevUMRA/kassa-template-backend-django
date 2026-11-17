from kassa.common.filters import search_filter
from kassa.documents.selectors import ITEMS, RETURNS, documents_of_user_warehouse
from kassa.inventory.models import Document


def sale_list(*, user, search=None):
    """Сатулар (чектер): Сатушы — өз қоймасы, Басқарушы — барлығы. search — чек нөмірі (дәл)."""
    sales = (
        Document.objects.filter(doc_type=Document.Type.SALE)
        .select_related('warehouse', 'responsible', 'canceled_by')
        .prefetch_related(ITEMS, RETURNS)
        .order_by('-date')
    )
    return search_filter(documents_of_user_warehouse(sales, user=user), search, ('=number',))
