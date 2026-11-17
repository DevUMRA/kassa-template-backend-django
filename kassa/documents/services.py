"""Құжаттарды өткізу және күшін жою — қалдықты өзгертетін жалғыз орын.

Ережелер (CLAUDE.md): әр функция `@transaction.atomic`; қалдық `select_for_update()` арқылы бұғатталады;
теріс қалдыққа жол берілмейді; әр өзгеріс StockMovement журналына жазылады; түгендеудегі тауарлар бұғатталған.
"""

import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from kassa.common.exceptions import AccessDeniedError, BusinessRuleError
from kassa.inventory.models import Document, DocumentItem, Stock, StockMovement
from kassa.users.selectors import user_is_manager

from .rules import DIRECTION, NUMBER_PREFIXES, RETURN_BASE_TYPES, ROLE_DOC_TYPES, SUPPLIER_DOC_TYPES

# --- Басқа домендер де қолданатын көмекші функциялар ---


def document_check_access(*, user, doc_type):
    """Рөл осы түрдегі құжатпен жұмыс істей ала ма (ROLE_DOC_TYPES)."""
    if user_is_manager(user):
        return
    if doc_type not in ROLE_DOC_TYPES.get(user.role, set()):
        raise AccessDeniedError(
            f'«{user.get_role_display()}» рөлі «{Document.Type(doc_type).label}» құжатымен жұмыс істей алмайды.'
        )


def user_warehouse_get(*, user):
    """Қызметкердің қоймасы: API арқылы жасалған құжаттар тек сонда жасалады."""
    if user.warehouse_id is None:
        raise BusinessRuleError('Қызметкерге қойма бекітілмеген — операция мүмкін емес.')
    return user.warehouse


def lines_merge(lines):
    """[(product, quantity), ...] → {product: жалпы саны}; бір тауардың қайталанған жолдары қосылады."""
    merged = {}
    for product, quantity in lines:
        merged[product] = merged.get(product, Decimal(0)) + quantity
    return merged


def priced_lines_merge(lines):
    """[(product, quantity, price), ...] → {product: {quantity, price}}. Бір тауар әртүрлі бағамен келсе — қате."""
    merged = {}
    for product, quantity, price in lines:
        line = merged.setdefault(product, {'quantity': Decimal(0), 'price': price})
        if line['price'] != price:
            raise BusinessRuleError(
                f'«{product}» тауары әртүрлі бағамен екі рет көрсетілген ({line["price"]} және {price}).'
            )
        line['quantity'] += quantity
    return merged


def stocks_lock(*, warehouse, product_ids):
    """Қалдық жолдарын product_id ретімен бұғаттайды (тұрақты рет deadlock-тың алдын алады)."""
    product_ids = sorted(set(product_ids))
    for product_id in product_ids:
        Stock.objects.get_or_create(product_id=product_id, warehouse=warehouse)
    stocks = (
        Stock.objects.select_for_update()
        .select_related('product')
        .filter(warehouse=warehouse, product_id__in=product_ids)
        .order_by('product_id')
    )
    return {stock.product_id: stock for stock in stocks}


def document_create(*, doc_type, user, warehouse, items, base=None, comment='', supplier=None):
    """DRAFT құжат жасайды. items — {product: {DocumentItem өрістері}}. Нөмірі: <префикс>-<id>."""
    document = Document.objects.create(
        # Уақытша бірегей нөмір, pk белгілі болған соң ауыстырылады
        number=f'TMP-{uuid.uuid4().hex[:24]}',
        doc_type=doc_type,
        warehouse=warehouse,
        supplier=supplier,
        responsible=user,
        base_document=base,
        comment=comment.strip(),
    )
    document.number = f'{NUMBER_PREFIXES[doc_type]}-{document.pk:06d}'
    document.save(update_fields=['number'])
    DocumentItem.objects.bulk_create(
        DocumentItem(document=document, product=product, **fields) for product, fields in items.items()
    )
    return document


# --- Өткізу мен күшін жоюдың ішкі қадамдары ---


def _document_lock(document):
    """Құжатты қайта оқып, жолын бұғаттайды — бір құжатты қатар екі рет өткізуден қорғайды."""
    # of=('self',): PostgreSQL nullable supplier (LEFT JOIN) жолын FOR UPDATE-пен бұғаттай алмайды
    return Document.objects.select_for_update(of=('self',)).select_related('warehouse', 'supplier').get(pk=document.pk)


def _check_inventory_lock(document, product_ids):
    """Түгендеу жүріп жатқан (DRAFT) тауарлар бойынша қозғалысқа тыйым салады."""
    locked = (
        DocumentItem.objects.filter(
            document__doc_type=Document.Type.INVENTORY,
            document__status=Document.Status.DRAFT,
            document__warehouse=document.warehouse,
            product_id__in=product_ids,
        )
        .exclude(document=document)
        .select_related('product', 'document')
    )
    errors = [f'«{item.product}» тауары №{item.document.number} түгендеуінде бұғатталған.' for item in locked]
    if errors:
        raise BusinessRuleError(errors)


def _validate_for_posting(document, items):
    errors = []
    if not items:
        errors.append('Құжатта бірде-бір тауар жоқ.')
    if not document.warehouse.is_active:
        errors.append(f'«{document.warehouse}» қоймасы белсенді емес.')
    if document.doc_type in SUPPLIER_DOC_TYPES and document.supplier_id is None:
        errors.append('Бұл құжат түрі үшін жеткізуші көрсетілуі тиіс.')
    for item in items:
        if not item.product.is_active:
            errors.append(f'«{item.product}» тауары белсенді емес.')
        # Түгендеуде нақты сан 0 болуы мүмкін, басқа құжаттарда — тек оң сан
        if document.doc_type != Document.Type.INVENTORY and item.quantity <= 0:
            errors.append(f'«{item.product}» тауарының саны нөлден үлкен болуы тиіс.')
        if document.doc_type == Document.Type.INVENTORY and not item.is_counted:
            errors.append(f'«{item.product}» тауары әлі саналмаған — нақты санын енгізіңіз.')
    if document.doc_type == Document.Type.WRITE_OFF and not document.comment.strip():
        errors.append('Есептен шығару себебі көрсетілуі тиіс (бүлінген, мерзімі өткен, …).')
    if document.base_document_id is not None and document.doc_type not in RETURN_BASE_TYPES:
        errors.append('Негіз құжат тек қайтару құжаттарында көрсетіледі.')
    if errors:
        raise BusinessRuleError(errors)


def _validate_return(document, items):
    """Қайтару өткізілген негіз құжатқа (сату/қабылдау) байлануы және ондағы саннан аспауы тиіс."""
    base_type = RETURN_BASE_TYPES[document.doc_type]
    if document.base_document_id is None:
        raise BusinessRuleError(f'Қайтаруда негіз құжат («{base_type.label}») көрсетілуі тиіс.')

    # Негіз құжатты бұғаттаймыз: оған қатар екі қайтару өткізілсе де, ондағы саннан асып кетпейді
    base = Document.objects.select_for_update(of=('self',)).get(pk=document.base_document_id)

    if base.doc_type != base_type:
        raise BusinessRuleError(f'№{base.number} құжаты «{base_type.label}» емес.')

    errors = []
    if base.status != Document.Status.POSTED:
        errors.append(
            f'№{base.number} құжаты «{base.get_status_display()}» мәртебесінде — '
            'тек өткізілген құжаттан қайтаруға болады.'
        )
    if base.warehouse_id != document.warehouse_id:
        errors.append(f'Қайтару №{base.number} құжатының «{base.warehouse}» қоймасынан жасалуы тиіс.')
    if base.supplier_id != document.supplier_id:
        errors.append(f'Қайтару №{base.number} құжатының жеткізушісіне («{base.supplier}») жасалуы тиіс.')
    if errors:
        raise BusinessRuleError(errors)

    based = {item.product_id: item.quantity for item in base.items.all()}
    returned = {}
    for item in DocumentItem.objects.filter(
        document__base_document=base,
        document__doc_type=document.doc_type,
        document__status=Document.Status.POSTED,
    ):
        returned[item.product_id] = returned.get(item.product_id, Decimal(0)) + item.quantity

    for item in items:
        if item.product_id not in based:
            errors.append(f'«{item.product}» тауары №{base.number} құжатында жоқ.')
            continue
        available = based[item.product_id] - returned.get(item.product_id, Decimal(0))
        if item.quantity > available:
            errors.append(
                f'«{item.product}»: №{base.number} құжатында {based[item.product_id]}, '
                f'бұрын қайтарылғаны {returned.get(item.product_id, Decimal(0))}, '
                f'қайтаруға болатыны {available}, сұралғаны {item.quantity}.'
            )
    if errors:
        raise BusinessRuleError(errors)


def _movements_apply(document, stocks, deltas, user, is_reversal):
    """Қалдықты өзгертіп, әр өзгерісті StockMovement журналына жазады. Теріс қалдыққа жол бермейді."""
    shortages = [
        f'«{stocks[product_id].product}»: қолжетімді {stocks[product_id].quantity}, қажет {-delta}.'
        for product_id, delta in deltas.items()
        if stocks[product_id].quantity + delta < 0
    ]
    if shortages:
        raise BusinessRuleError(['Қалдық жеткіліксіз:', *shortages])

    movements = []
    for product_id, delta in deltas.items():
        if delta == 0:
            continue
        stock = stocks[product_id]
        stock.quantity += delta
        stock.save(update_fields=['quantity', 'updated_at'])
        movements.append(
            StockMovement(
                product_id=product_id,
                warehouse=document.warehouse,
                quantity=delta,
                document=document,
                doc_type=document.doc_type,
                is_reversal=is_reversal,
                user=user,
            )
        )
    StockMovement.objects.bulk_create(movements)


# --- Негізгі сервистер ---


@transaction.atomic
def document_post(*, document, user, comment=None):
    """DRAFT құжатты өткізеді: қалдықты бір-ақ рет өзгертеді және журналға жазады.

    comment берілсе — өткізумен бірге сақталады (мысалы, түгендеуді бекіткенде айырманың түсіндірмесі).
    """
    document = _document_lock(document)
    document_check_access(user=user, doc_type=document.doc_type)

    if document.status != Document.Status.DRAFT:
        raise BusinessRuleError(
            f'№{document.number} құжаты «{document.get_status_display()}» мәртебесінде — тек жобаны өткізуге болады.'
        )
    if comment is not None:
        document.comment = comment.strip()

    items = list(document.items.select_related('product'))
    _validate_for_posting(document, items)
    if document.doc_type in RETURN_BASE_TYPES:
        _validate_return(document, items)

    product_ids = [item.product_id for item in items]
    stocks = stocks_lock(warehouse=document.warehouse, product_ids=product_ids)
    # Бұғат қалдық бұғатталғаннан КЕЙІН тексеріледі: inventory_start де сол жолдарды бұғаттайды,
    # сондықтан қатар басталған түгендеу міндетті түрде көрінеді (READ COMMITTED)
    if document.doc_type != Document.Type.INVENTORY:
        _check_inventory_lock(document, product_ids)

    if document.doc_type == Document.Type.INVENTORY:
        # Түгендеу: құжаттағы сан — нақты саналған қалдық, қозғалыс — айырма
        deltas = {item.product_id: item.quantity - stocks[item.product_id].quantity for item in items}
    else:
        direction = DIRECTION[document.doc_type]
        deltas = {item.product_id: direction * item.quantity for item in items}

    _movements_apply(document, stocks, deltas, user, is_reversal=False)

    document.status = Document.Status.POSTED
    document.posted_at = timezone.now()
    document.save(update_fields=['status', 'posted_at', 'comment'])
    return document


@transaction.atomic
def document_cancel(*, document, user, reason=''):
    """Құжаттың күшін жояды. POSTED құжат ізсіз жойылмайды — кері қозғалыстар (reversal) жазылады.

    Кім жойғаны және себебі сақталады; өткізілген құжат үшін себеп міндетті.
    """
    document = _document_lock(document)
    reason = (reason or '').strip()

    if document.status == Document.Status.CANCELED:
        raise BusinessRuleError(f'№{document.number} құжатының күші бұрын жойылған.')

    if document.status == Document.Status.POSTED:
        # Өткізілген құжатты кері қайтару — бақылау операциясы, тек Басқарушыға рұқсат
        if not user_is_manager(user):
            raise AccessDeniedError('Өткізілген құжаттың күшін тек Басқарушы жоя алады.')
        if not reason:
            raise BusinessRuleError(f'№{document.number}: өткізілген құжаттың күшін жою себебі көрсетілуі тиіс.')

        # Өткізілген қайтаруы бар сатудың/қабылдаудың күшін жойсақ, қайтару негізсіз қалады
        active_returns = document.returns.filter(status=Document.Status.POSTED)
        if active_returns.exists():
            numbers = ', '.join(f'№{r.number}' for r in active_returns)
            raise BusinessRuleError(
                f'№{document.number} құжатының өткізілген қайтарулары бар ({numbers}) — алдымен солардың күшін жойыңыз.'
            )

        deltas = {}
        for movement in document.movements.filter(is_reversal=False):
            deltas[movement.product_id] = deltas.get(movement.product_id, Decimal(0)) - movement.quantity

        stocks = stocks_lock(warehouse=document.warehouse, product_ids=deltas.keys())
        # Түгендеу жүріп жатқан тауарлардың қалдығын кері операция да өзгертпеуі тиіс
        _check_inventory_lock(document, list(deltas))
        _movements_apply(document, stocks, deltas, user, is_reversal=True)
    else:
        # DRAFT қалдыққа әсер етпеген — тек мәртебесі өзгереді
        document_check_access(user=user, doc_type=document.doc_type)

    document.status = Document.Status.CANCELED
    document.canceled_at = timezone.now()
    document.canceled_by = user
    document.cancel_reason = reason
    document.save(update_fields=['status', 'canceled_at', 'canceled_by', 'cancel_reason'])
    return document
