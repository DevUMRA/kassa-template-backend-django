from django.db.models import Prefetch

from kassa.documents.selectors import documents_of_user_warehouse
from kassa.inventory.models import Document, DocumentItem


def inventory_list(*, user, status=None):
    """Түгендеулер жолдарымен (тауар атауы бойынша): Қоймашы — өз қоймасы, Басқарушы — барлығы."""
    items = Prefetch('items', queryset=DocumentItem.objects.select_related('product').order_by('product__name'))
    audits = (
        Document.objects.filter(doc_type=Document.Type.INVENTORY)
        .select_related('warehouse', 'responsible', 'canceled_by')
        .prefetch_related(items)
        .order_by('-date')
    )
    audits = documents_of_user_warehouse(audits, user=user)
    return audits.filter(status=status) if status else audits
