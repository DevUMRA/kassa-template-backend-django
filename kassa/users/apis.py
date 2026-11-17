from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from kassa.inventory.models import User

from .selectors import user_profile
from .services import user_token_delete


class MeApi(APIView):
    @extend_schema(
        tags=['Қызмет'],
        summary='Ағымдағы пайдаланушы',
        description='Фронтенд үшін: рөл, қойма және қолжетімді бөлімдер.',
        responses={
            200: inline_serializer(
                'Me',
                {
                    'username': serializers.CharField(),
                    'full_name': serializers.CharField(),
                    'role': serializers.ChoiceField(choices=User.Role.choices),
                    'role_display': serializers.CharField(),
                    'is_manager': serializers.BooleanField(),
                    'warehouse': inline_serializer(
                        'MeWarehouse',
                        {'id': serializers.IntegerField(), 'name': serializers.CharField()},
                        allow_null=True,
                    ),
                    'sections': serializers.ListField(
                        child=serializers.ChoiceField(choices=['pos', 'warehouse', 'inventory', 'documents', 'reports'])
                    ),
                },
            )
        },
    )
    def get(self, request):
        return Response(user_profile(request.user))


class LogoutApi(APIView):
    @extend_schema(
        tags=['auth'],
        summary='Шығу',
        description=(
            'Ағымдағы пайдаланушының токенін өшіреді: осы токенмен келген сұраныстар енді 401 алады. '
            'Қайта кіру — `POST /api/auth/token/`.'
        ),
        request=None,
        responses={204: None},
    )
    def post(self, request):
        user_token_delete(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
