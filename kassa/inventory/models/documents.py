from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from .catalog import Product, Supplier, Warehouse


class Document(models.Model):
    class Type(models.TextChoices):
        SALE = 'SALE', 'Сату'
        SALE_RETURN = 'SALE_RETURN', 'Сатушылық қайтару'
        RECEIPT = 'RECEIPT', 'Жеткізушіден қабылдау'
        SUPPLIER_RETURN = 'SUPPLIER_RETURN', 'Жеткізушіге қайтару'
        WRITE_OFF = 'WRITE_OFF', 'Есептен шығару'
        INVENTORY = 'INVENTORY', 'Түгендеу'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Жоба'
        POSTED = 'POSTED', 'Өткізілді'
        CANCELED = 'CANCELED', 'Күші жойылды'

    number = models.CharField('Нөмірі', max_length=32, unique=True)
    doc_type = models.CharField('Түрі', max_length=20, choices=Type.choices)
    status = models.CharField('Мәртебесі', max_length=10, choices=Status.choices, default=Status.DRAFT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='documents', verbose_name='Қойма')
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='documents',
        null=True,
        blank=True,
        verbose_name='Жеткізуші',
    )
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='documents',
        verbose_name='Жауапты қызметкер',
    )
    # Қайтару құжаттары үшін — қай құжаттан қайтарылып жатқаны (сату немесе жеткізушіден қабылдау)
    base_document = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        related_name='returns',
        null=True,
        blank=True,
        limit_choices_to={'doc_type__in': ['SALE', 'RECEIPT']},
        verbose_name='Негіз құжат',
    )
    # Есептен шығаруда міндетті (неге шығарылды), басқа құжаттарда — қосымша түсініктеме
    comment = models.CharField('Себебі / түсініктеме', max_length=500, blank=True)
    date = models.DateTimeField('Датасы', auto_now_add=True)
    posted_at = models.DateTimeField('Өткізілген уақыты', null=True, blank=True)
    canceled_at = models.DateTimeField('Күшін жою уақыты', null=True, blank=True)
    canceled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='canceled_documents',
        null=True,
        blank=True,
        verbose_name='Күшін жойған',
    )
    # Өткізілген құжаттың күшін жойғанда міндетті (cancel_document)
    cancel_reason = models.CharField('Күшін жою себебі', max_length=500, blank=True)

    class Meta:
        verbose_name = 'Құжат'
        verbose_name_plural = 'Құжаттар'
        ordering = ['-date']
        indexes = [models.Index(fields=['doc_type', 'status'])]

    def __str__(self):
        return f'{self.get_doc_type_display()} №{self.number} ({self.get_status_display()})'

    def clean(self):
        # Форма (админ) деңгейіндегі ерте тексеру; өткізгенде сервис те тексереді
        if self.doc_type == self.Type.WRITE_OFF and not self.comment.strip():
            raise ValidationError({'comment': 'Есептен шығару себебі көрсетілуі тиіс.'})


class DocumentItem(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='items', verbose_name='Құжат')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='document_items', verbose_name='Тауар')
    quantity = models.DecimalField('Саны', max_digits=12, decimal_places=3, validators=[MinValueValidator(0)])
    price = models.DecimalField('Бағасы', max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    # Түгендеу үшін: басталған сәттегі есептік қалдық және нақты сан енгізілді ме
    expected_quantity = models.DecimalField('Есептік қалдық', max_digits=12, decimal_places=3, null=True, blank=True)
    is_counted = models.BooleanField('Саналды', default=True)

    class Meta:
        verbose_name = 'Құжат жолы'
        verbose_name_plural = 'Құжат жолдары'
        constraints = [
            models.UniqueConstraint(fields=['document', 'product'], name='unique_document_product'),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name='document_item_quantity_gte_0'),
            models.CheckConstraint(condition=models.Q(price__gte=0), name='document_item_price_gte_0'),
        ]

    def __str__(self):
        return f'{self.product} × {self.quantity}'

    @property
    def total(self):
        return self.quantity * self.price
