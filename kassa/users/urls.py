from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from .apis import LogoutApi, MeApi

urlpatterns = [
    path('me/', MeApi.as_view(), name='api-me'),
    # Кіру: {username, password} → {token}; әрі қарай `Authorization: Token <token>`
    path('auth/token/', obtain_auth_token, name='api-token'),
    path('auth/logout/', LogoutApi.as_view(), name='api-logout'),
]
