from rest_framework import serializers

from kassa.documents.serializers import WithReturnsSerializer


class SaleSerializer(WithReturnsSerializer):
    cashier = serializers.CharField(source='responsible.username', read_only=True)

    class Meta(WithReturnsSerializer.Meta):
        fields = (*WithReturnsSerializer.Meta.fields, 'cashier')
