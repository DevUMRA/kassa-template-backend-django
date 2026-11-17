from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from kassa.common.pagination import PageNumberPagination, get_paginated_response
from kassa.common.schema import ERROR_RESPONSES, ID, SEARCH
from kassa.common.serializers import SearchSerializer
from kassa.documents.selectors import document_return_get
from kassa.documents.serializers import LinesSerializer, ReturnLinesSerializer, ReturnSerializer
from kassa.users.permissions import IsCashier

from .selectors import sale_list
from .serializers import SaleSerializer
from .services import sale_create, sale_return_create

TAGS = ['POS: сату']


class SaleListCreateApi(APIView):
    """Кассалық сатулар: Сатушы, Басқарушы. Сатушы өз қоймасының сатуларын көреді, Басқарушы — барлығын.

    `search` — чек нөмірі бойынша дәл іздеу.
    """

    permission_classes = (IsCashier,)
    pagination_class = PageNumberPagination

    @extend_schema(
        tags=TAGS, summary='Сатулар (чектер) тізімі', parameters=[SEARCH], responses=SaleSerializer(many=True)
    )
    def get(self, request):
        params = SearchSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        return get_paginated_response(
            pagination_class=self.pagination_class,
            serializer_class=SaleSerializer,
            queryset=sale_list(user=request.user, search=params.validated_data.get('search')),
            request=request,
            view=self,
        )

    @extend_schema(
        tags=TAGS,
        summary='Сату (чек)',
        description=(
            'Сату құжатын жасап, бірден өткізеді — бір транзакцияда. Баға тауардың сату бағасынан алынады '
            '(клиент жібермейді), бір тауардың қайталанған жолдары қосылады. Қате болса ештеңе сақталмайды. '
            'Кассирге қойма бекітілген болуы тиіс.'
        ),
        request=LinesSerializer,
        responses={201: SaleSerializer, **ERROR_RESPONSES},
    )
    def post(self, request):
        lines = LinesSerializer(data=request.data)
        lines.is_valid(raise_exception=True)
        sale = sale_create(user=request.user, lines=lines.lines())
        sale = sale_list(user=request.user).get(pk=sale.pk)
        return Response(SaleSerializer(sale).data, status=status.HTTP_201_CREATED)


class SaleDetailApi(APIView):
    """Кассалық сатулар: Сатушы, Басқарушы. Сатушы өз қоймасының сатуларын көреді, Басқарушы — барлығын.

    `search` — чек нөмірі бойынша дәл іздеу.
    """

    permission_classes = (IsCashier,)

    @extend_schema(tags=TAGS, summary='Чек', parameters=[ID], responses=SaleSerializer)
    def get(self, request, id):
        return Response(SaleSerializer(get_object_or_404(sale_list(user=request.user), pk=id)).data)


class SaleReturnCreateApi(APIView):
    permission_classes = (IsCashier,)

    @extend_schema(
        tags=TAGS,
        summary='Сатудан қайтару',
        description=(
            'Сатушылық қайтару құжатын жасап, бірден өткізеді. Баға сатудағы бағадан алынады. '
            'Сатылған саннан (бұрынғы қайтаруларды шегергенде) артық қайтаруға болмайды.'
        ),
        parameters=[ID],
        request=ReturnLinesSerializer,
        responses={201: ReturnSerializer, **ERROR_RESPONSES},
    )
    def post(self, request, id):
        sale = get_object_or_404(sale_list(user=request.user), pk=id)
        lines = ReturnLinesSerializer(data=request.data)
        lines.is_valid(raise_exception=True)
        sale_return = sale_return_create(
            user=request.user, sale=sale, lines=lines.lines(), comment=lines.validated_data['comment']
        )
        return Response(
            ReturnSerializer(document_return_get(document_id=sale_return.pk)).data, status=status.HTTP_201_CREATED
        )
