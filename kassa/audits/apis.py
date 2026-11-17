from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from kassa.common.pagination import PageNumberPagination, get_paginated_response
from kassa.common.schema import ERROR_RESPONSES, ID
from kassa.documents.serializers import CancelSerializer
from kassa.inventory.models import Document
from kassa.users.permissions import IsInventoryStaff

from .selectors import inventory_list
from .serializers import (
    ApproveSerializer,
    CountsSerializer,
    InventoryFilterSerializer,
    InventorySerializer,
    StartInventorySerializer,
)
from .services import inventory_approve, inventory_cancel, inventory_counts_record, inventory_start

TAGS = ['Түгендеу']


def _inventory_response(request, document, code=status.HTTP_200_OK):
    """Әрекеттен кейін — түгендеудің жаңа күйі (жолдары мен прогресі)."""
    document = inventory_list(user=request.user).get(pk=document.pk)
    return Response(InventorySerializer(document).data, status=code)


class InventoryListCreateApi(APIView):
    """Түгендеу: бастау → нақты санды енгізу (Қоймашы) → бекіту немесе күшін жою (Басқарушы).

    Қоймашы өз қоймасының түгендеулерін көреді, Басқарушы — барлығын.
    """

    permission_classes = (IsInventoryStaff,)
    pagination_class = PageNumberPagination

    @extend_schema(
        tags=TAGS,
        summary='Түгендеулер тізімі',
        parameters=[OpenApiParameter('status', OpenApiTypes.STR, enum=Document.Status.values)],
        responses=InventorySerializer(many=True),
    )
    def get(self, request):
        filters = InventoryFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        return get_paginated_response(
            pagination_class=self.pagination_class,
            serializer_class=InventorySerializer,
            queryset=inventory_list(user=request.user, status=filters.validated_data.get('status')),
            request=request,
            view=self,
        )

    @extend_schema(
        tags=TAGS,
        summary='Түгендеуді бастау',
        description=(
            'DRAFT түгендеу құжатын жасайды, әр тауарға сол сәттегі есептік қалдық жазылады. '
            'Сол сәттен бастап бұл тауарлар бойынша кез келген қозғалыс (сату, қайтару, күшін жою, …) '
            'бекітілгенше немесе күші жойылғанша бұғатталады. Қоймашы, Басқарушы.'
        ),
        request=StartInventorySerializer,
        responses={201: InventorySerializer, **ERROR_RESPONSES},
    )
    def post(self, request):
        data = StartInventorySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        document = inventory_start(
            user=request.user, products=data.validated_data['products'], comment=data.validated_data['comment']
        )
        return _inventory_response(request, document, status.HTTP_201_CREATED)


class InventoryDetailApi(APIView):
    """Түгендеу: бастау → нақты санды енгізу (Қоймашы) → бекіту немесе күшін жою (Басқарушы).

    Қоймашы өз қоймасының түгендеулерін көреді, Басқарушы — барлығын.
    """

    permission_classes = (IsInventoryStaff,)

    @extend_schema(tags=TAGS, summary='Түгендеу', parameters=[ID], responses=InventorySerializer)
    def get(self, request, id):
        return Response(InventorySerializer(get_object_or_404(inventory_list(user=request.user), pk=id)).data)


class InventoryCountsApi(APIView):
    permission_classes = (IsInventoryStaff,)

    @extend_schema(
        tags=TAGS,
        summary='Нақты санды енгізу',
        description='Саналған санды енгізеді (0 болуы мүмкін). Қайта енгізілсе — соңғысы сақталады. Тек DRAFT.',
        parameters=[ID],
        request=CountsSerializer,
        responses={200: InventorySerializer, **ERROR_RESPONSES},
    )
    def post(self, request, id):
        document = get_object_or_404(inventory_list(user=request.user), pk=id)
        lines = CountsSerializer(data=request.data)
        lines.is_valid(raise_exception=True)
        inventory_counts_record(user=request.user, document=document, lines=lines.lines())
        return _inventory_response(request, document)


class InventoryApproveApi(APIView):
    permission_classes = (IsInventoryStaff,)

    @extend_schema(
        tags=TAGS,
        summary='Түгендеуді бекіту',
        description=(
            'Қалдықты нақты санға теңестіреді, айырма StockMovement журналына жазылады. '
            'Барлық тауар саналған болуы тиіс. Тек Басқарушы. `comment` — айырманың түсіндірмесі (міндетті емес).'
        ),
        parameters=[ID],
        request=ApproveSerializer,
        responses={200: InventorySerializer, **ERROR_RESPONSES},
    )
    def post(self, request, id):
        data = ApproveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        document = get_object_or_404(inventory_list(user=request.user), pk=id)
        document = inventory_approve(user=request.user, document=document, comment=data.validated_data.get('comment'))
        return _inventory_response(request, document)


class InventoryCancelApi(APIView):
    permission_classes = (IsInventoryStaff,)

    @extend_schema(
        tags=TAGS,
        summary='Түгендеудің күшін жою',
        description=(
            'DRAFT — бұғат алынады; POSTED — кері қозғалыстар жазылады, `reason` міндетті. Тек Басқарушы. '
            'Кім және неге жойғаны сақталады (`canceled_by`, `cancel_reason`).'
        ),
        parameters=[ID],
        request=CancelSerializer,
        responses={200: InventorySerializer, **ERROR_RESPONSES},
    )
    def post(self, request, id):
        data = CancelSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        document = get_object_or_404(inventory_list(user=request.user), pk=id)
        document = inventory_cancel(user=request.user, document=document, reason=data.validated_data['reason'])
        return _inventory_response(request, document)
