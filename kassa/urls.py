"""Барлық API жолдары: /api/... Әр домен өз urls.py-ын береді."""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from kassa.common.apis import HealthApi

urlpatterns = [
    path('health/', HealthApi.as_view(), name='api-health'),
    path('schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='api-schema'), name='api-docs'),
    path('redoc/', SpectacularRedocView.as_view(url_name='api-schema'), name='api-redoc'),
    # me/, auth/token/, auth/logout/
    path('', include('kassa.users.urls')),
    # warehouses/, pos/products/, warehouse/suppliers/
    path('', include('kassa.catalog.urls')),
    path('pos/', include('kassa.pos.urls')),
    path('warehouse/', include('kassa.warehouse.urls')),
    path('inventory/', include('kassa.audits.urls')),
    path('documents/', include('kassa.documents.urls')),
    path('reports/', include('kassa.reports.urls')),
]
