from django.urls import path

from .apis import DocumentCancelApi, DocumentDetailApi, DocumentListApi

urlpatterns = [
    path('', DocumentListApi.as_view(), name='document-list'),
    path('<int:id>/', DocumentDetailApi.as_view(), name='document-detail'),
    path('<int:id>/cancel/', DocumentCancelApi.as_view(), name='document-cancel'),
]
