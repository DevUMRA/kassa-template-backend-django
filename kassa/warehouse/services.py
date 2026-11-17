from decimal import Decimal

from django.db import transaction

from kassa.documents.services import (
    document_check_access,
    document_create,
    document_post,
    lines_merge,
    priced_lines_merge,
    user_warehouse_get,
)
from kassa.inventory.models import Document


@transaction.atomic
def write_off_create(*, user, lines, comment):
    """Есептен шығару: құжатты қызметкердің қоймасында жасап, бірден өткізеді. Себеп міндетті.

    Баға — тауардың сату бағасы (есептегі шығын сомасы). Қате болса, ештеңе сақталмайды.
    """
    document_check_access(user=user, doc_type=Document.Type.WRITE_OFF)
    warehouse = user_warehouse_get(user=user)
    document = document_create(
        doc_type=Document.Type.WRITE_OFF,
        user=user,
        warehouse=warehouse,
        items={
            product: {'quantity': quantity, 'price': product.sale_price}
            for product, quantity in lines_merge(lines).items()
        },
        comment=comment,
    )
    return document_post(document=document, user=user)


@transaction.atomic
def receipt_create(*, user, supplier, lines, comment=''):
    """Жеткізушіден қабылдау: құжатты қызметкердің қоймасында жасап, бірден өткізеді.

    lines — [(product, quantity, price), ...]; price — сатып алу бағасы (жеткізушінің накладнойы бойынша).
    """
    document_check_access(user=user, doc_type=Document.Type.RECEIPT)
    warehouse = user_warehouse_get(user=user)
    document = document_create(
        doc_type=Document.Type.RECEIPT,
        user=user,
        warehouse=warehouse,
        items=priced_lines_merge(lines),
        comment=comment,
        supplier=supplier,
    )
    return document_post(document=document, user=user)


@transaction.atomic
def supplier_return_create(*, user, receipt, lines, comment=''):
    """Жеткізушіге қайтару: құжатты жасап, бірден өткізеді. Жеткізуші мен баға қабылдау құжатынан алынады."""
    document_check_access(user=user, doc_type=Document.Type.SUPPLIER_RETURN)
    warehouse = user_warehouse_get(user=user)
    receipt_prices = dict(receipt.items.values_list('product_id', 'price'))
    document = document_create(
        doc_type=Document.Type.SUPPLIER_RETURN,
        user=user,
        warehouse=warehouse,
        # Қабылдауда жоқ тауардың бағасы 0 — оны бәрібір document_post қабылдамайды
        items={
            product: {'quantity': quantity, 'price': receipt_prices.get(product.pk, Decimal(0))}
            for product, quantity in lines_merge(lines).items()
        },
        base=receipt,
        comment=comment,
        supplier=receipt.supplier,
    )
    return document_post(document=document, user=user)
