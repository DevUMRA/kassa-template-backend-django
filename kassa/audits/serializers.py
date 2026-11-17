from decimal import Decimal

from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers

from kassa.catalog.selectors import product_list_active
from kassa.documents.serializers import (
    QUANTITY_OR_NULL,
    LineSerializer,
    LinesSerializer,
    canceled_by_field,
    comment_field,
)
from kassa.inventory.models import Document, DocumentItem

# --- Кіріс ---


class StartInventorySerializer(serializers.Serializer):
    """Түгенделетін тауарлар: product_ids тізімі немесе all=true (барлық белсенді тауарлар)."""

    product_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=False)
    all = serializers.BooleanField(required=False, default=False)
    comment = comment_field('Түгендеу себебі (жоспарлы, ауысым тапсыру, …)')

    def validate(self, attrs):
        if bool(attrs.get('product_ids')) == attrs['all']:
            raise serializers.ValidationError('product_ids немесе all=true — тек біреуі көрсетілуі тиіс.')
        if attrs['all']:
            return {'products': list(product_list_active()), 'comment': attrs['comment']}
        ids = set(attrs['product_ids'])
        products = list(product_list_active(product_ids=ids))
        missing = ids - {product.pk for product in products}
        if missing:
            raise serializers.ValidationError(f'Белсенді тауар табылмады: {sorted(missing)}.')
        return {'products': products, 'comment': attrs['comment']}


class CountLineSerializer(LineSerializer):
    # Түгендеуде нақты сан 0 болуы мүмкін (тауар мүлде табылмады)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal(0))


class CountsSerializer(LinesSerializer):
    items = CountLineSerializer(many=True, allow_empty=False)


class ApproveSerializer(serializers.Serializer):
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text='Айырманың түсіндірмесі. Берілмесе — бастағандағы түсініктеме сақталады.',
    )


class InventoryFilterSerializer(serializers.Serializer):
    status = serializers.CharField(required=False, allow_blank=True)


# --- Шығыс ---


class InventoryItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    sku = serializers.CharField(source='product.sku', read_only=True)
    barcode = serializers.CharField(source='product.barcode', read_only=True)
    counted_quantity = serializers.SerializerMethodField()
    difference = serializers.SerializerMethodField()

    class Meta:
        model = DocumentItem
        fields = (
            'product_id',
            'product_name',
            'sku',
            'barcode',
            'expected_quantity',
            'counted_quantity',
            'is_counted',
            'difference',
        )

    @extend_schema_field(QUANTITY_OR_NULL)
    def get_counted_quantity(self, item):
        return str(item.quantity) if item.is_counted else None

    @extend_schema_field(QUANTITY_OR_NULL)
    def get_difference(self, item):
        """Нақты − есептік: теріс — кем шықты, оң — артық шықты. Саналмаса — null."""
        if not item.is_counted or item.expected_quantity is None:
            return None
        return str(item.quantity - item.expected_quantity)


class InventorySerializer(serializers.ModelSerializer):
    warehouse = serializers.CharField(source='warehouse.name', read_only=True)
    responsible = serializers.CharField(source='responsible.username', read_only=True)
    canceled_by = canceled_by_field()
    items = InventoryItemSerializer(many=True, read_only=True)
    progress = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = (
            'id',
            'number',
            'status',
            'warehouse',
            'responsible',
            'date',
            'posted_at',
            'canceled_at',
            'canceled_by',
            'cancel_reason',
            'comment',
            'progress',
            'items',
        )

    @extend_schema_field(
        inline_serializer(
            'InventoryProgress', {'total': serializers.IntegerField(), 'counted': serializers.IntegerField()}
        )
    )
    def get_progress(self, document):
        items = document.items.all()
        return {'total': len(items), 'counted': sum(1 for item in items if item.is_counted)}
