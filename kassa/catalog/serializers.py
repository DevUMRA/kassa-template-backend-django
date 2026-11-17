from rest_framework import serializers

from kassa.inventory.models import Product, Supplier


class ProductSerializer(serializers.ModelSerializer):
    unit_display = serializers.CharField(source='get_unit_display', read_only=True)
    # Кассирдің қоймасындағы қолжетімді қалдық (product_list селекторы annotate етеді)
    available = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)

    class Meta:
        model = Product
        fields = ('id', 'name', 'sku', 'barcode', 'category', 'unit', 'unit_display', 'sale_price', 'available')


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ('id', 'name', 'bin', 'phone')
