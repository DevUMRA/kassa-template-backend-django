from django.urls import path

from .apis import SaleDetailApi, SaleListCreateApi, SaleReturnCreateApi

urlpatterns = [
    path('sales/', SaleListCreateApi.as_view(), name='pos-sale-list'),
    path('sales/<int:id>/', SaleDetailApi.as_view(), name='pos-sale-detail'),
    path('sales/<int:id>/returns/', SaleReturnCreateApi.as_view(), name='pos-sale-returns'),
]
