from decimal import Decimal

from rest_framework import serializers

from kassa.documents.serializers import (
    LineSerializer,
    LinesSerializer,
    ReturnSerializer,
    WithReturnsSerializer,
    comment_field,
)
from kassa.inventory.models import Supplier

# --- Кіріс ---


class WriteOffLinesSerializer(LinesSerializer):
    comment = serializers.CharField(
        max_length=500, help_text='Есептен шығару себебі (міндетті): бүлінген, мерзімі өткен, …'
    )


class ReceiptLineSerializer(LineSerializer):
    price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal(0), help_text='Сатып алу бағасы (накладной бойынша)'
    )

    def validate(self, attrs):
        price = attrs['price']
        return {**super().validate(attrs), 'price': price}


class ReceiptRequestSerializer(serializers.Serializer):
    supplier_id = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all(), source='supplier')
    items = ReceiptLineSerializer(many=True, allow_empty=False)
    comment = comment_field('Түсініктеме (накладной нөмірі, …)')

    def lines(self):
        """Сервиске берілетін пішін: [(product, quantity, price), ...]."""
        return [(line['product'], line['quantity'], line['price']) for line in self.validated_data['items']]


# --- Шығыс ---


class WriteOffSerializer(ReturnSerializer):
    warehouse = serializers.CharField(source='warehouse.name', read_only=True)
    responsible = serializers.CharField(source='responsible.username', read_only=True)

    class Meta(ReturnSerializer.Meta):
        fields = (*ReturnSerializer.Meta.fields, 'warehouse', 'responsible')


class ReceiptSerializer(WithReturnsSerializer):
    supplier_id = serializers.IntegerField(read_only=True)
    supplier = serializers.CharField(source='supplier.name', read_only=True)
    responsible = serializers.CharField(source='responsible.username', read_only=True)

    class Meta(WithReturnsSerializer.Meta):
        fields = (*WithReturnsSerializer.Meta.fields, 'supplier_id', 'supplier', 'responsible')
