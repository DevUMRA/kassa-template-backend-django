from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from kassa.common.pagination import PageNumberPagination, get_paginated_response
from kassa.common.schema import ERROR_RESPONSES, ID, SEARCH
from kassa.inventory.models import Document
from kassa.users.permissions import IsManagerDocuments

from .selectors import document_list
from .serializers import CancelSerializer, DocumentFilterSerializer, DocumentSerializer
from .services import document_cancel

TAGS = ['Құжаттар']


class DocumentListApi(APIView):
    """Барлық түрдегі құжаттар журналы және күшін жою. Тек Басқарушы. `search` — нөмірі бойынша."""

    permission_classes = (IsManagerDocuments,)
    pagination_class = PageNumberPagination

    @extend_schema(
        tags=TAGS,
        summary='Құжаттар журналы',
        parameters=[
            OpenApiParameter('doc_type', OpenApiTypes.STR, enum=Document.Type.values),
            OpenApiParameter('status', OpenApiTypes.STR, enum=Document.Status.values),
            OpenApiParameter('warehouse', OpenApiTypes.INT, description='Қойма id'),
            OpenApiParameter('date_from', OpenApiTypes.DATE, description='Құжат күні, бастап (қоса)'),
            OpenApiParameter('date_to', OpenApiTypes.DATE, description='Құжат күні, дейін (қоса)'),
            SEARCH,
        ],
        responses=DocumentSerializer(many=True),
    )
    def get(self, request):
        filters = DocumentFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        return get_paginated_response(
            pagination_class=self.pagination_class,
            serializer_class=DocumentSerializer,
            queryset=document_list(filters=filters.validated_data),
            request=request,
            view=self,
        )


class DocumentDetailApi(APIView):
    """Барлық түрдегі құжаттар журналы және күшін жою. Тек Басқарушы. `search` — нөмірі бойынша."""

    permission_classes = (IsManagerDocuments,)

    @extend_schema(tags=TAGS, summary='Құжат', parameters=[ID], responses=DocumentSerializer)
    def get(self, request, id):
        document = get_object_or_404(document_list(), pk=id)
        return Response(DocumentSerializer(document).data)


class DocumentCancelApi(APIView):
    """Барлық түрдегі құжаттар журналы және күшін жою. Тек Басқарушы. `search` — нөмірі бойынша."""

    permission_classes = (IsManagerDocuments,)

    @extend_schema(
        tags=TAGS,
        summary='Құжаттың күшін жою',
        description=(
            'DRAFT — жай ғана күші жойылады; POSTED — кері қозғалыстар жазылады, қалдық қалпына келеді, '
            '`reason` міндетті. Өткізілген қайтаруы бар сатудың/қабылдаудың, түгендеуде бұғатталған '
            'тауарлардың немесе кері қозғалыстан кейін теріс қалдық болатын құжаттың күшін жоюға болмайды (400). '
            'Кім және неге жойғаны сақталады.'
        ),
        parameters=[ID],
        request=CancelSerializer,
        responses={200: DocumentSerializer, **ERROR_RESPONSES},
    )
    def post(self, request, id):
        data = CancelSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        document = get_object_or_404(document_list(), pk=id)
        document_cancel(document=document, user=request.user, reason=data.validated_data['reason'])
        return Response(DocumentSerializer(get_object_or_404(document_list(), pk=id)).data)
