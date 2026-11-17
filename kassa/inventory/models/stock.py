from django.conf import settings
from django.db import models

from .catalog import Product, Warehouse
from .documents import Document


class StockMovement(models.Model):
    """Тауар қозғалысының журналы. quantity оң — кіріс, теріс — шығыс."""

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='movements', verbose_name='Тауар')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='movements', verbose_name='Қойма')
    quantity = models.DecimalField('Саны', max_digits=12, decimal_places=3)
    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name='movements', verbose_name='Құжат')
    doc_type = models.CharField('Құжат типі', max_length=20, choices=Document.Type.choices)
    is_reversal = models.BooleanField('Кері операция', default=False)
    date = models.DateTimeField('Датасы', auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='stock_movements',
        verbose_name='Қызметкер',
    )

    class Meta:
        verbose_name = 'Тауар қозғалысы'
        verbose_name_plural = 'Тауар қозғалыстары'
        ordering = ['-date']
        indexes = [models.Index(fields=['product', 'warehouse'])]

    def __str__(self):
        sign = '+' if self.quantity > 0 else ''
        return f'{self.product} @ {self.warehouse}: {sign}{self.quantity} ({self.get_doc_type_display()})'


class Stock(models.Model):
    """Тауардың қоймадағы ағымдағы қалдығы. Өзгерткенде select_for_update() арқылы бұғатталады."""

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='stocks', verbose_name='Тауар')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='stocks', verbose_name='Қойма')
    quantity = models.DecimalField('Қалдық', max_digits=12, decimal_places=3, default=0)
    updated_at = models.DateTimeField('Жаңартылған уақыты', auto_now=True)

    class Meta:
        verbose_name = 'Қалдық'
        verbose_name_plural = 'Қалдықтар'
        ordering = ['product__name']
        constraints = [
            models.UniqueConstraint(fields=['product', 'warehouse'], name='unique_stock_product_warehouse'),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name='stock_quantity_gte_0'),
        ]

    def __str__(self):
        return f'{self.product} @ {self.warehouse}: {self.quantity}'
