"""OpenAPI (drf-spectacular) үшін ортақ бөліктер."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, inline_serializer
from rest_framework import filters, serializers

# Сервис қателерінің пішіні (kassa.common.exceptions)
ERROR_RESPONSES = {
    400: OpenApiResponse(
        inline_serializer('BusinessError', {'detail': serializers.ListField(child=serializers.CharField())}),
        description='Бизнес-ереже бұзылды (қалдық жетпейді, түгендеу бұғаты, …) немесе параметр қате',
    ),
    403: OpenApiResponse(
        inline_serializer('Forbidden', {'detail': serializers.CharField()}),
        description='Рөлге рұқсат жоқ',
    ),
}

ID = OpenApiParameter('id', OpenApiTypes.INT, OpenApiParameter.PATH)

# Тізімдердегі `?search=` (kassa.common.filters.search_filter)
SEARCH = OpenApiParameter(
    'search', OpenApiTypes.STR, required=False, description=filters.SearchFilter.search_description
)
