from drf_spectacular.utils import extend_schema
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from kassa.common.schema import ERROR_RESPONSES
from kassa.users.permissions import IsInventoryStaff, IsManager

from . import serializers as schemas
from .selectors import (
    inventory_report,
    movement_list,
    movement_row,
    report_warehouse_ids,
    sales_report,
    stock_report,
    turnover_report,
)
from .serializers import (
    MovementParamsSerializer,
    PeriodSerializer,
    SalesParamsSerializer,
    StockParamsSerializer,
)

TAGS = ['Есептер']


def _params(serializer_class, request):
    params = serializer_class(data=request.query_params)
    params.is_valid(raise_exception=True)
    return params.validated_data


def _period(params):
    return {'date_from': params['date_from'], 'date_to': params['date_to']}


class StockReportApi(APIView):
    permission_classes = (IsInventoryStaff,)

    @extend_schema(
        tags=TAGS,
        summary='Қалдықтар',
        parameters=[StockParamsSerializer],
        description='Ағымдағы қалдық және оның сату бағасымен құны. Басқарушы, Қоймашы.',
        responses={200: schemas.StockReportSerializer, **ERROR_RESPONSES},
    )
    def get(self, request):
        params = _params(StockParamsSerializer, request)
        warehouse_ids = report_warehouse_ids(user=request.user, requested=params.get('warehouse'))
        return Response(stock_report(warehouse_ids=warehouse_ids, search=params.get('search'), low=params.get('low')))


class MovementReportApi(APIView):
    permission_classes = (IsInventoryStaff,)

    @extend_schema(
        tags=TAGS,
        summary='Қозғалыс журналы',
        parameters=[MovementParamsSerializer],
        description='Кезең ішіндегі StockMovement жазбалары, жаңалары бірінші, беттеп. Басқарушы, Қоймашы.',
        responses={200: schemas.MovementPageSerializer, **ERROR_RESPONSES},
    )
    def get(self, request):
        params = _params(MovementParamsSerializer, request)
        movements = movement_list(
            start=params['start'],
            end=params['end'],
            warehouse_ids=report_warehouse_ids(user=request.user, requested=params.get('warehouse')),
            product_id=params.get('product'),
            doc_type=params.get('doc_type'),
        )
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(movements, request, view=self)
        response = paginator.get_paginated_response([movement_row(movement) for movement in page])
        response.data = {**_period(params), **response.data}
        return response


class TurnoverReportApi(APIView):
    permission_classes = (IsInventoryStaff,)

    @extend_schema(
        tags=TAGS,
        summary='Айналым ведомосі',
        parameters=[PeriodSerializer],
        description=(
            'Тауар × қойма бойынша: бастапқы қалдық + кіріс − шығыс = соңғы қалдық. '
            'Күшін жоюдан туған кері жазбалар бағыты бойынша кіріс/шығысқа түседі. Басқарушы, Қоймашы.'
        ),
        responses={200: schemas.TurnoverReportSerializer, **ERROR_RESPONSES},
    )
    def get(self, request):
        params = _params(PeriodSerializer, request)
        report = turnover_report(
            start=params['start'],
            end=params['end'],
            warehouse_ids=report_warehouse_ids(user=request.user, requested=params.get('warehouse')),
            product_id=params.get('product'),
        )
        return Response({**_period(params), **report})


class SalesReportApi(APIView):
    permission_classes = (IsManager,)

    @extend_schema(
        tags=TAGS,
        summary='Сату есебі',
        parameters=[SalesParamsSerializer],
        description=(
            'Өткізілген сатулар мен сатушылық қайтарулар (posted_at бойынша), түсім = сату − қайтару. '
            'Күші жойылған құжаттар кірмейді. Тек Басқарушы.'
        ),
        responses={200: schemas.SalesReportSerializer, **ERROR_RESPONSES},
    )
    def get(self, request):
        params = _params(SalesParamsSerializer, request)
        report = sales_report(
            start=params['start'],
            end=params['end'],
            warehouse_ids=report_warehouse_ids(user=request.user, requested=params.get('warehouse')),
            group_by=params['group_by'],
        )
        return Response({**_period(params), **report})


class InventoryReportApi(APIView):
    permission_classes = (IsInventoryStaff,)

    @extend_schema(
        tags=TAGS,
        summary='Түгендеу нәтижелері',
        parameters=[PeriodSerializer],
        description=(
            'Бекітілген түгендеулердің кемшілігі мен артығы (журналдағы нақты айырма) '
            'және кезеңдегі есептен шығарулар. Басқарушы, Қоймашы.'
        ),
        responses={200: schemas.InventoryReportSerializer, **ERROR_RESPONSES},
    )
    def get(self, request):
        params = _params(PeriodSerializer, request)
        report = inventory_report(
            start=params['start'],
            end=params['end'],
            warehouse_ids=report_warehouse_ids(user=request.user, requested=params.get('warehouse')),
        )
        return Response({**_period(params), **report})
