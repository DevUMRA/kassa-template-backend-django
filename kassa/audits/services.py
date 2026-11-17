"""Түгендеу: бастау → нақты санды енгізу (Қоймашы) → бекіту немесе күшін жою (Басқарушы)."""

from decimal import Decimal

from django.db import transaction

from kassa.common.exceptions import AccessDeniedError, BusinessRuleError
from kassa.documents.services import (
    document_cancel,
    document_create,
    document_post,
    stocks_lock,
    user_warehouse_get,
)
from kassa.inventory.models import Document, DocumentItem, User
from kassa.users.selectors import user_is_manager

INVENTORY_ROLES = {User.Role.WAREHOUSEMAN, User.Role.MANAGER}


def _check_inventory_staff(user, document=None):
    """Түгендеуді бастау және санау: Қоймашы мен Басқарушы. Қоймашы тек өз қоймасында."""
    if not (user.is_superuser or user.role in INVENTORY_ROLES):
        raise AccessDeniedError('Түгендеумен тек Қоймашы мен Басқарушы жұмыс істей алады.')
    if document is not None and not user_is_manager(user) and document.warehouse_id != user.warehouse_id:
        raise AccessDeniedError('Түгендеу басқа қоймада жүріп жатыр.')


@transaction.atomic
def inventory_start(*, user, products, comment=''):
    """Түгендеуді бастайды: DRAFT INVENTORY құжаты жасалады, сол сәттен тауарлар бойынша қозғалыс бұғатталады.

    Әр жолға есептік қалдық (expected_quantity) жазылады, нақты сан кейін inventory_counts_record арқылы енгізіледі.
    """
    _check_inventory_staff(user)
    warehouse = user_warehouse_get(user=user)
    products = sorted(set(products), key=lambda product: product.pk)
    if not products:
        raise BusinessRuleError('Түгенделетін тауарлар көрсетілмеген.')

    # Қалдықты бұғаттаймыз: қатар өтіп жатқан операциялар аяқталғанша күтеміз, кейінгілері бұғатты көреді
    stocks = stocks_lock(warehouse=warehouse, product_ids=[product.pk for product in products])
    busy = DocumentItem.objects.filter(
        document__doc_type=Document.Type.INVENTORY,
        document__status=Document.Status.DRAFT,
        document__warehouse=warehouse,
        product__in=products,
    ).select_related('product', 'document')
    errors = [f'«{item.product}» тауары №{item.document.number} түгендеуінде тұр.' for item in busy]
    if errors:
        raise BusinessRuleError(errors)

    return document_create(
        doc_type=Document.Type.INVENTORY,
        user=user,
        warehouse=warehouse,
        items={
            product: {
                'quantity': Decimal(0),
                'price': product.sale_price,
                'expected_quantity': stocks[product.pk].quantity,
                'is_counted': False,
            }
            for product in products
        },
        comment=comment,
    )


@transaction.atomic
def inventory_counts_record(*, user, document, lines):
    """Түгендеуге нақты саналған санды енгізеді. Қайта енгізілсе — соңғысы сақталады."""
    document = Document.objects.select_for_update(of=('self',)).get(pk=document.pk)
    _check_inventory_staff(user, document)
    if document.doc_type != Document.Type.INVENTORY or document.status != Document.Status.DRAFT:
        raise BusinessRuleError(f'№{document.number} — жүріп жатқан түгендеу емес.')

    items = {item.product_id: item for item in document.items.select_related('product')}
    errors = []
    for product, quantity in lines:
        item = items.get(product.pk)
        if item is None:
            errors.append(f'«{product}» тауары №{document.number} түгендеуінде жоқ.')
            continue
        item.quantity = quantity
        item.is_counted = True
    if errors:
        raise BusinessRuleError(errors)
    DocumentItem.objects.bulk_update(items.values(), ['quantity', 'is_counted'])
    return document


def inventory_approve(*, user, document, comment=None):
    """Бекіту: қалдықты нақты санға теңестіреді (тек Басқарушы — document_post тексереді)."""
    return document_post(document=document, user=user, comment=comment)


def inventory_cancel(*, user, document, reason=''):
    """DRAFT — бұғат алынады; POSTED — кері қозғалыстар жазылады (себеп міндетті)."""
    return document_cancel(document=document, user=user, reason=reason)
