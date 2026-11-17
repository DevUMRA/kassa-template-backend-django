from decimal import Decimal

from django.db.models import DecimalField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from kassa.common.filters import search_filter
from kassa.inventory.models import Product, Stock, Supplier, Warehouse


def product_list(*, warehouse_id, search=None):
    """Белсенді тауарлар және `available` — берілген қоймадағы қолжетімді қалдық (жоқ болса 0)."""
    available = Stock.objects.filter(product=OuterRef('pk'), warehouse_id=warehouse_id).values('quantity')
    products = (
        Product.objects.filter(is_active=True)
        .annotate(
            available=Coalesce(
                Subquery(available),
                Value(Decimal(0)),
                output_field=DecimalField(max_digits=12, decimal_places=3),
            )
        )
        .order_by('name')
    )
    return search_filter(products, search, ('name', 'sku', '=barcode'))


def product_get_active(*, product_id=None, barcode=None):
    """Белсенді тауар id немесе штрихкод бойынша; табылмаса — None."""
    lookup = {'pk': product_id} if product_id is not None else {'barcode': barcode}
    return Product.objects.filter(is_active=True, **lookup).first()


def product_list_active(*, product_ids=None):
    """Белсенді тауарлар; product_ids берілсе — тек солар."""
    products = Product.objects.filter(is_active=True)
    return products if product_ids is None else products.filter(pk__in=product_ids)


def supplier_list(*, search=None):
    return search_filter(Supplier.objects.order_by('name'), search, ('name', 'bin'))


def warehouse_list():
    """Белсенді қоймалар: [{id, name}, ...]."""
    return list(Warehouse.objects.filter(is_active=True).order_by('name').values('id', 'name'))
