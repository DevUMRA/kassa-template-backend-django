from rest_framework.pagination import PageNumberPagination


def get_paginated_response(*, pagination_class, serializer_class, queryset, request, view):
    """Тізімді беттеп береді: {count, next, previous, results}. Беттің өлшемі — settings.PAGE_SIZE."""
    paginator = pagination_class()
    page = paginator.paginate_queryset(queryset, request, view=view)
    return paginator.get_paginated_response(serializer_class(page, many=True).data)


__all__ = ['PageNumberPagination', 'get_paginated_response']
