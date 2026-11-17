from django.urls import path

from .apis import InventoryReportApi, MovementReportApi, SalesReportApi, StockReportApi, TurnoverReportApi

urlpatterns = [
    path('stock/', StockReportApi.as_view(), name='report-stock'),
    path('movements/', MovementReportApi.as_view(), name='report-movements'),
    path('turnover/', TurnoverReportApi.as_view(), name='report-turnover'),
    path('sales/', SalesReportApi.as_view(), name='report-sales'),
    path('inventory/', InventoryReportApi.as_view(), name='report-inventory'),
]
