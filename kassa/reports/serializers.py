"""Есеп жауаптарының құрылымы — OpenAPI құжаттамасы үшін (есептердің өзі reports/selectors.py-да dict қайтарады)."""

from django.utils import timezone
from rest_framework import serializers

from kassa.common.utils import period_bounds
from kassa.inventory.models import Document

from .selectors import SALES_GROUPS


def quantity(**kwargs):
    return serializers.DecimalField(max_digits=16, decimal_places=3, **kwargs)


def amount(**kwargs):
    return serializers.DecimalField(max_digits=18, decimal_places=2, **kwargs)


class PeriodMixin(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()


# --- Қалдықтар ---


class StockRowSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    sku = serializers.CharField()
    barcode = serializers.CharField(allow_null=True)
    unit = serializers.CharField(help_text='Өлшем бірлігі (дана, кг, …)')
    warehouse_id = serializers.IntegerField()
    warehouse = serializers.CharField()
    quantity = quantity()
    sale_price = amount()
    value = amount(help_text='quantity × sale_price')


class StockTotalsSerializer(serializers.Serializer):
    positions = serializers.IntegerField()
    value = amount()


class StockReportSerializer(serializers.Serializer):
    rows = StockRowSerializer(many=True)
    totals = StockTotalsSerializer()


# --- Қозғалыс журналы ---


class MovementRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    date = serializers.DateTimeField()
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    warehouse = serializers.CharField()
    quantity = quantity(help_text='Оң — кіріс, теріс — шығыс')
    doc_type = serializers.ChoiceField(choices=Document.Type.choices)
    doc_type_display = serializers.CharField()
    document_number = serializers.CharField()
    comment = serializers.CharField(help_text='Құжаттың себебі/түсініктемесі (бос болуы мүмкін)')
    is_reversal = serializers.BooleanField(help_text='Күшін жоюдан туған кері жазба')
    cancel_reason = serializers.CharField(help_text='Кері жазбада — күшін жою себебі, әйтпесе бос')
    user = serializers.CharField()


class MovementPageSerializer(PeriodMixin):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = MovementRowSerializer(many=True)


# --- Айналым ведомосі ---


class TurnoverRowSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    sku = serializers.CharField()
    warehouse_id = serializers.IntegerField()
    warehouse = serializers.CharField()
    opening = quantity(help_text='Кезең басындағы қалдық')
    incoming = quantity()
    outgoing = quantity()
    closing = quantity(help_text='opening + incoming − outgoing')


class TurnoverTotalsSerializer(serializers.Serializer):
    opening = quantity()
    incoming = quantity()
    outgoing = quantity()
    closing = quantity()


class TurnoverReportSerializer(PeriodMixin):
    rows = TurnoverRowSerializer(many=True)
    totals = TurnoverTotalsSerializer()


# --- Сату есебі ---


class SalesRowSerializer(serializers.Serializer):
    day = serializers.DateField(required=False, help_text='group_by=day болғанда')
    product_id = serializers.IntegerField(required=False, help_text='group_by=product болғанда')
    product_name = serializers.CharField(required=False, help_text='group_by=product болғанда')
    sku = serializers.CharField(required=False, help_text='group_by=product болғанда')
    cashier = serializers.CharField(required=False, help_text='group_by=cashier болғанда')
    receipts = serializers.IntegerField(help_text='Чектер саны')
    sold_qty = quantity()
    sold_amount = amount()
    returns = serializers.IntegerField(help_text='Қайтарулар саны')
    returned_qty = quantity()
    returned_amount = amount()
    net_amount = amount(help_text='sold_amount − returned_amount')


class SalesTotalsSerializer(serializers.Serializer):
    receipts = serializers.IntegerField()
    returns = serializers.IntegerField()
    sold_amount = amount()
    returned_amount = amount()
    net_amount = amount()


class SalesReportSerializer(PeriodMixin):
    group_by = serializers.ChoiceField(choices=['day', 'product', 'cashier'])
    rows = SalesRowSerializer(many=True)
    totals = SalesTotalsSerializer()


# --- Түгендеу нәтижелері ---


class AuditLineSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    sku = serializers.CharField()
    difference = quantity(help_text='Теріс — кемшілік, оң — артық')
    price = amount()
    amount = amount()


class ShortageSurplusSerializer(serializers.Serializer):
    shortage_qty = quantity()
    shortage_amount = amount()
    surplus_qty = quantity()
    surplus_amount = amount()


class AuditResultSerializer(ShortageSurplusSerializer):
    id = serializers.IntegerField()
    number = serializers.CharField()
    posted_at = serializers.DateTimeField()
    warehouse = serializers.CharField()
    comment = serializers.CharField(help_text='Түгендеу себебі / айырманың түсіндірмесі')
    positions = serializers.IntegerField(help_text='Түгенделген тауарлар саны')
    lines = AuditLineSerializer(many=True, help_text='Тек айырмасы бар тауарлар')


class InventoryTotalsSerializer(ShortageSurplusSerializer):
    audits = serializers.IntegerField()


class WriteOffRowSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    sku = serializers.CharField()
    documents = serializers.IntegerField()
    quantity = quantity()
    amount = amount()


class WriteOffDocumentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    number = serializers.CharField()
    posted_at = serializers.DateTimeField()
    warehouse = serializers.CharField()
    reason = serializers.CharField(help_text='Есептен шығару себебі')
    quantity = quantity()
    amount = amount()


class WriteOffsSerializer(serializers.Serializer):
    rows = WriteOffRowSerializer(many=True, help_text='Тауар бойынша жиынтық')
    documents = WriteOffDocumentSerializer(many=True, help_text='Құжат бойынша, себебімен')
    total_quantity = quantity()
    total_amount = amount()


class InventoryReportSerializer(PeriodMixin):
    audits = AuditResultSerializer(many=True)
    totals = InventoryTotalsSerializer()
    write_offs = WriteOffsSerializer()


# --- Кіріс: query параметрлері ---


class PeriodSerializer(serializers.Serializer):
    """Кезең: date_from..date_to (екеуі де қоса). Әдепкі — ағымдағы айдың басынан бүгінге дейін."""

    date_from = serializers.DateField(required=False, help_text='Әдепкі — ағымдағы айдың 1-күні')
    date_to = serializers.DateField(required=False, help_text='Әдепкі — бүгін')
    warehouse = serializers.IntegerField(
        required=False, help_text='Қойма id. Басқарушы үшін — көрсетілмесе барлық қойма; Қоймашы — тек өз қоймасы'
    )
    product = serializers.IntegerField(required=False, help_text='Тауар id')

    def validate(self, attrs):
        today = timezone.localdate()
        attrs.setdefault('date_to', today)
        attrs.setdefault('date_from', attrs['date_to'].replace(day=1))
        if attrs['date_from'] > attrs['date_to']:
            raise serializers.ValidationError('date_from date_to-дан кейін болмауы тиіс.')
        attrs['start'], attrs['end'] = period_bounds(attrs['date_from'], attrs['date_to'])
        return attrs


class StockParamsSerializer(serializers.Serializer):
    warehouse = serializers.IntegerField(required=False, help_text='Қойма id (Қоймашы — тек өз қоймасы)')
    search = serializers.CharField(required=False, help_text='Атауы, артикулы немесе штрихкоды')
    low = serializers.DecimalField(
        max_digits=12, decimal_places=3, required=False, help_text='Осы саннан аз немесе тең қалдықтар ғана'
    )


class MovementParamsSerializer(PeriodSerializer):
    doc_type = serializers.ChoiceField(choices=Document.Type.choices, required=False, help_text='Құжат түрі')
    page = serializers.IntegerField(required=False, help_text='Бет нөмірі (бетте 50 жазба)')


class SalesParamsSerializer(PeriodSerializer):
    group_by = serializers.ChoiceField(choices=list(SALES_GROUPS), required=False, default='day', help_text='Топтау')
