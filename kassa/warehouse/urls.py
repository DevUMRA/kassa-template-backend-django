from django.urls import path

from .apis import (
    ReceiptDetailApi,
    ReceiptListCreateApi,
    SupplierReturnCreateApi,
    WriteOffDetailApi,
    WriteOffListCreateApi,
)

urlpatterns = [
    path('write-offs/', WriteOffListCreateApi.as_view(), name='warehouse-write-off-list'),
    path('write-offs/<int:id>/', WriteOffDetailApi.as_view(), name='warehouse-write-off-detail'),
    path('receipts/', ReceiptListCreateApi.as_view(), name='warehouse-receipt-list'),
    path('receipts/<int:id>/', ReceiptDetailApi.as_view(), name='warehouse-receipt-detail'),
    path('receipts/<int:id>/returns/', SupplierReturnCreateApi.as_view(), name='warehouse-receipt-returns'),
]
