"""Құжаттардың тұрақты ережелері: қалдыққа әсер ету бағыты, рөлдер, нөмір префикстері."""

from kassa.inventory.models import Document, User

# Құжат түрі бойынша қалдыққа әсер ету бағыты: +1 кіріс, -1 шығыс.
# INVENTORY мұнда жоқ — оның қозғалысы нақты сан мен есептік қалдықтың айырмасынан есептеледі.
DIRECTION = {
    Document.Type.RECEIPT: 1,
    Document.Type.SALE_RETURN: 1,
    Document.Type.SALE: -1,
    Document.Type.SUPPLIER_RETURN: -1,
    Document.Type.WRITE_OFF: -1,
}

# Қай рөл қай құжатты өткізе алады. MANAGER мен суперпайдаланушыға бәрі рұқсат.
ROLE_DOC_TYPES = {
    User.Role.SELLER: {Document.Type.SALE, Document.Type.SALE_RETURN},
    User.Role.WAREHOUSEMAN: {
        Document.Type.RECEIPT,
        Document.Type.SUPPLIER_RETURN,
        Document.Type.WRITE_OFF,
    },
}

SUPPLIER_DOC_TYPES = {Document.Type.RECEIPT, Document.Type.SUPPLIER_RETURN}

# Қайтару құжаты → оның негіз құжатының түрі
RETURN_BASE_TYPES = {
    Document.Type.SALE_RETURN: Document.Type.SALE,
    Document.Type.SUPPLIER_RETURN: Document.Type.RECEIPT,
}

# API арқылы жасалған құжаттардың нөмірі: SAL-000042
NUMBER_PREFIXES = {
    Document.Type.SALE: 'SAL',
    Document.Type.SALE_RETURN: 'SRT',
    Document.Type.INVENTORY: 'INV',
    Document.Type.WRITE_OFF: 'WOF',
    Document.Type.RECEIPT: 'RCV',
    Document.Type.SUPPLIER_RETURN: 'RTS',
}
