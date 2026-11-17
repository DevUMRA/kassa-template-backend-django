from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .selectors import database_is_available


class HealthApi(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=['Қызмет'],
        summary='Денсаулық тексеруі',
        description='Аутентификациясыз. Мониторинг/load balancer үшін: қолданба мен PostgreSQL жауап бере ме.',
        responses={
            200: inline_serializer('Health', {'status': serializers.CharField(), 'database': serializers.CharField()}),
            503: inline_serializer(
                'Unhealthy', {'status': serializers.CharField(), 'database': serializers.CharField()}
            ),
        },
    )
    def get(self, request):
        if not database_is_available():
            return Response({'status': 'error', 'database': 'unavailable'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({'status': 'ok', 'database': 'ok'})
