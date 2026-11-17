from django.urls import path

from .apis import (
    InventoryApproveApi,
    InventoryCancelApi,
    InventoryCountsApi,
    InventoryDetailApi,
    InventoryListCreateApi,
)

urlpatterns = [
    path('audits/', InventoryListCreateApi.as_view(), name='inventory-audit-list'),
    path('audits/<int:id>/', InventoryDetailApi.as_view(), name='inventory-audit-detail'),
    path('audits/<int:id>/counts/', InventoryCountsApi.as_view(), name='inventory-audit-counts'),
    path('audits/<int:id>/approve/', InventoryApproveApi.as_view(), name='inventory-audit-approve'),
    path('audits/<int:id>/cancel/', InventoryCancelApi.as_view(), name='inventory-audit-cancel'),
]
