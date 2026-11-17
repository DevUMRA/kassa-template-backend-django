from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from kassa.common.pagination import PageNumberPagination, get_paginated_response
from kassa.common.schema import ID, SEARCH
from kassa.common.serializers import SearchSerializer
from kassa.users.permissions import IsWarehouseStaff

from .selectors import product_list, supplier_list, warehouse_list
from .serializers import ProductSerializer, SupplierSerializer

PRODUCT_TAGS = ['POS: тауарлар']
SUPPLIER_TAGS = ['Қойма: қабылдау']


class ProductListApi(APIView):
    """Белсенді тауарлар және кассир қоймасындағы қолжетімді қалдық (`available`). Барлық рөлдер."""

    pagination_class = PageNumberPagination

    @extend_schema(
        tags=PRODUCT_TAGS, summary='Тауарлар тізімі', parameters=[SEARCH], responses=ProductSerializer(many=True)
    )
    def get(self, request):
        params = SearchSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        return get_paginated_response(
            pagination_class=self.pagination_class,
            serializer_class=ProductSerializer,
            queryset=product_list(warehouse_id=request.user.warehouse_id, search=params.validated_data.get('search')),
            request=request,
            view=self,
        )


class ProductDetailApi(APIView):
    """Белсенді тауарлар және кассир қоймасындағы қолжетімді қалдық (`available`). Барлық рөлдер."""

    @extend_schema(tags=PRODUCT_TAGS, summary='Тауар', parameters=[ID], responses=ProductSerializer)
    def get(self, request, id):
        product = get_object_or_404(product_list(warehouse_id=request.user.warehouse_id), pk=id)
        return Response(ProductSerializer(product).data)


class ProductByBarcodeApi(APIView):
    """Белсенді тауарлар және кассир қоймасындағы қолжетімді қалдық (`available`). Барлық рөлдер."""

    @extend_schema(
        tags=PRODUCT_TAGS,
        summary='Тауарды штрихкод бойынша табу (сканер)',
        parameters=[OpenApiParameter('barcode', OpenApiTypes.STR, OpenApiParameter.PATH)],
        responses={200: ProductSerializer, 404: None},
    )
    def get(self, request, barcode):
        product = get_object_or_404(product_list(warehouse_id=request.user.warehouse_id), barcode=barcode)
        return Response(ProductSerializer(product).data)


class SupplierListApi(APIView):
    """Жеткізушілер (қабылдау формасы үшін). `search` — атауы немесе БСН. Қоймашы, Басқарушы."""

    permission_classes = (IsWarehouseStaff,)
    pagination_class = PageNumberPagination

    @extend_schema(
        tags=SUPPLIER_TAGS,
        summary='Жеткізушілер тізімі',
        parameters=[SEARCH],
        responses=SupplierSerializer(many=True),
    )
    def get(self, request):
        params = SearchSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        return get_paginated_response(
            pagination_class=self.pagination_class,
            serializer_class=SupplierSerializer,
            queryset=supplier_list(search=params.validated_data.get('search')),
            request=request,
            view=self,
        )


class SupplierDetailApi(APIView):
    """Жеткізушілер (қабылдау формасы үшін). `search` — атауы немесе БСН. Қоймашы, Басқарушы."""

    permission_classes = (IsWarehouseStaff,)

    @extend_schema(tags=SUPPLIER_TAGS, summary='Жеткізуші', parameters=[ID], responses=SupplierSerializer)
    def get(self, request, id):
        return Response(SupplierSerializer(get_object_or_404(supplier_list(), pk=id)).data)


class WarehouseListApi(APIView):
    @extend_schema(
        tags=['Қызмет'],
        summary='Қоймалар тізімі',
        responses={
            200: inline_serializer(
                'WarehouseItem', {'id': serializers.IntegerField(), 'name': serializers.CharField()}, many=True
            )
        },
    )
    def get(self, request):
        return Response(warehouse_list())
