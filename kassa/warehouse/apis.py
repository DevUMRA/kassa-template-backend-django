from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from kassa.common.pagination import PageNumberPagination, get_paginated_response
from kassa.common.schema import ERROR_RESPONSES, ID, SEARCH
from kassa.common.serializers import SearchSerializer
from kassa.documents.selectors import document_return_get
from kassa.documents.serializers import ReturnLinesSerializer, ReturnSerializer
from kassa.users.permissions import IsWarehouseStaff

from .selectors import receipt_list, write_off_list
from .serializers import ReceiptRequestSerializer, ReceiptSerializer, WriteOffLinesSerializer, WriteOffSerializer
from .services import receipt_create, supplier_return_create, write_off_create

WRITE_OFF_TAGS = ['Қойма: есептен шығару']
RECEIPT_TAGS = ['Қойма: қабылдау']


class WriteOffListCreateApi(APIView):
    """Есептен шығару: Қоймашы, Басқарушы. Қоймашы өз қоймасының құжаттарын көреді, Басқарушы — барлығын."""

    permission_classes = (IsWarehouseStaff,)
    pagination_class = PageNumberPagination

    @extend_schema(tags=WRITE_OFF_TAGS, summary='Есептен шығарулар тізімі', responses=WriteOffSerializer(many=True))
    def get(self, request):
        return get_paginated_response(
            pagination_class=self.pagination_class,
            serializer_class=WriteOffSerializer,
            queryset=write_off_list(user=request.user),
            request=request,
            view=self,
        )

    @extend_schema(
        tags=WRITE_OFF_TAGS,
        summary='Есептен шығару',
        description=(
            'Есептен шығару құжатын қызметкердің қоймасында жасап, бірден өткізеді — бір транзакцияда. '
            'Себеп (`comment`) міндетті. Баға — тауардың сату бағасы. Қалдық жетпесе немесе тауар '
            'түгендеуде бұғатталса — 400, ештеңе сақталмайды.'
        ),
        request=WriteOffLinesSerializer,
        responses={201: WriteOffSerializer, **ERROR_RESPONSES},
    )
    def post(self, request):
        lines = WriteOffLinesSerializer(data=request.data)
        lines.is_valid(raise_exception=True)
        document = write_off_create(user=request.user, lines=lines.lines(), comment=lines.validated_data['comment'])
        document = write_off_list(user=request.user).get(pk=document.pk)
        return Response(WriteOffSerializer(document).data, status=status.HTTP_201_CREATED)


class WriteOffDetailApi(APIView):
    """Есептен шығару: Қоймашы, Басқарушы. Қоймашы өз қоймасының құжаттарын көреді, Басқарушы — барлығын."""

    permission_classes = (IsWarehouseStaff,)

    @extend_schema(tags=WRITE_OFF_TAGS, summary='Есептен шығару', parameters=[ID], responses=WriteOffSerializer)
    def get(self, request, id):
        return Response(WriteOffSerializer(get_object_or_404(write_off_list(user=request.user), pk=id)).data)


class ReceiptListCreateApi(APIView):
    """Жеткізушіден қабылдау және жеткізушіге қайтару: Қоймашы, Басқарушы.

    Қоймашы өз қоймасының қабылдауларын көреді, Басқарушы — барлығын. `search` — нөмірі бойынша дәл іздеу.
    """

    permission_classes = (IsWarehouseStaff,)
    pagination_class = PageNumberPagination

    @extend_schema(
        tags=RECEIPT_TAGS, summary='Қабылдаулар тізімі', parameters=[SEARCH], responses=ReceiptSerializer(many=True)
    )
    def get(self, request):
        params = SearchSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        return get_paginated_response(
            pagination_class=self.pagination_class,
            serializer_class=ReceiptSerializer,
            queryset=receipt_list(user=request.user, search=params.validated_data.get('search')),
            request=request,
            view=self,
        )

    @extend_schema(
        tags=RECEIPT_TAGS,
        summary='Жеткізушіден қабылдау',
        description=(
            'Қабылдау құжатын қызметкердің қоймасында жасап, бірден өткізеді — бір транзакцияда. '
            'Әр жолда сатып алу бағасы көрсетіледі. Тауар түгендеуде бұғатталса — 400, ештеңе сақталмайды.'
        ),
        request=ReceiptRequestSerializer,
        responses={201: ReceiptSerializer, **ERROR_RESPONSES},
    )
    def post(self, request):
        data = ReceiptRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        receipt = receipt_create(
            user=request.user,
            supplier=data.validated_data['supplier'],
            lines=data.lines(),
            comment=data.validated_data['comment'],
        )
        receipt = receipt_list(user=request.user).get(pk=receipt.pk)
        return Response(ReceiptSerializer(receipt).data, status=status.HTTP_201_CREATED)


class ReceiptDetailApi(APIView):
    """Жеткізушіден қабылдау және жеткізушіге қайтару: Қоймашы, Басқарушы.

    Қоймашы өз қоймасының қабылдауларын көреді, Басқарушы — барлығын. `search` — нөмірі бойынша дәл іздеу.
    """

    permission_classes = (IsWarehouseStaff,)

    @extend_schema(tags=RECEIPT_TAGS, summary='Қабылдау', parameters=[ID], responses=ReceiptSerializer)
    def get(self, request, id):
        return Response(ReceiptSerializer(get_object_or_404(receipt_list(user=request.user), pk=id)).data)


class SupplierReturnCreateApi(APIView):
    permission_classes = (IsWarehouseStaff,)

    @extend_schema(
        tags=RECEIPT_TAGS,
        summary='Жеткізушіге қайтару',
        description=(
            'Жеткізушіге қайтару құжатын жасап, бірден өткізеді. Жеткізуші мен баға қабылдаудан алынады. '
            'Қабылданған саннан (бұрынғы қайтаруларды шегергенде) және қоймадағы қалдықтан артық қайтаруға болмайды.'
        ),
        parameters=[ID],
        request=ReturnLinesSerializer,
        responses={201: ReturnSerializer, **ERROR_RESPONSES},
    )
    def post(self, request, id):
        receipt = get_object_or_404(receipt_list(user=request.user), pk=id)
        lines = ReturnLinesSerializer(data=request.data)
        lines.is_valid(raise_exception=True)
        supplier_return = supplier_return_create(
            user=request.user, receipt=receipt, lines=lines.lines(), comment=lines.validated_data['comment']
        )
        return Response(
            ReturnSerializer(document_return_get(document_id=supplier_return.pk)).data,
            status=status.HTTP_201_CREATED,
        )
