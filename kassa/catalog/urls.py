from django.urls import path

from .apis import (
    ProductByBarcodeApi,
    ProductDetailApi,
    ProductListApi,
    SupplierDetailApi,
    SupplierListApi,
    WarehouseListApi,
)

# Жолдар тарихи бойынша әртүрлі бөлімдерде (/api/pos/, /api/warehouse/) — API келісімшарты өзгермейді
urlpatterns = [
    path('warehouses/', WarehouseListApi.as_view(), name='api-warehouses'),
    path('pos/products/', ProductListApi.as_view(), name='pos-product-list'),
    path('pos/products/barcode/<str:barcode>/', ProductByBarcodeApi.as_view(), name='pos-product-by-barcode'),
    path('pos/products/<int:id>/', ProductDetailApi.as_view(), name='pos-product-detail'),
    path('warehouse/suppliers/', SupplierListApi.as_view(), name='warehouse-supplier-list'),
    path('warehouse/suppliers/<int:id>/', SupplierDetailApi.as_view(), name='warehouse-supplier-detail'),
]
