"""Модельдер домен бойынша бөлінген; барлығы бір `inventory` қолданбасына тиесілі.

Модельдер жұқа: тек өрістер, шектеулер (constraints) және `clean()` арқылы өріс деңгейіндегі тексеру.
Қалдықты өзгертетін кез келген әрекет — тек `kassa.documents.services` арқылы.
"""

from .catalog import Product, Supplier, Warehouse
from .documents import Document, DocumentItem
from .stock import Stock, StockMovement
from .users import User

__all__ = ['Document', 'DocumentItem', 'Product', 'Stock', 'StockMovement', 'Supplier', 'User', 'Warehouse']
