from decimal import Decimal

from django.db import transaction

from kassa.documents.services import document_create, document_post, lines_merge, user_warehouse_get
from kassa.inventory.models import Document


@transaction.atomic
def sale_create(*, user, lines):
    """Кассалық сату: құжатты жасап, бірден өткізеді. Қате болса, ештеңе сақталмайды (жоба да қалмайды).

    lines — [(product, quantity), ...]; баға әрқашан тауардың ағымдағы сату бағасынан алынады.
    """
    warehouse = user_warehouse_get(user=user)
    document = document_create(
        doc_type=Document.Type.SALE,
        user=user,
        warehouse=warehouse,
        items={
            product: {'quantity': quantity, 'price': product.sale_price}
            for product, quantity in lines_merge(lines).items()
        },
    )
    return document_post(document=document, user=user)


@transaction.atomic
def sale_return_create(*, user, sale, lines, comment=''):
    """Сатудан қайтару: құжатты жасап, бірден өткізеді. Баға сатудағы бағадан алынады. comment — қайтару себебі."""
    warehouse = user_warehouse_get(user=user)
    sale_prices = dict(sale.items.values_list('product_id', 'price'))
    document = document_create(
        doc_type=Document.Type.SALE_RETURN,
        user=user,
        warehouse=warehouse,
        # Сатуда жоқ тауардың бағасы 0 — оны бәрібір document_post қабылдамайды
        items={
            product: {'quantity': quantity, 'price': sale_prices.get(product.pk, Decimal(0))}
            for product, quantity in lines_merge(lines).items()
        },
        base=sale,
        comment=comment,
    )
    return document_post(document=document, user=user)
