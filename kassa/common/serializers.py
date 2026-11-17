from rest_framework import serializers


class SearchSerializer(serializers.Serializer):
    """Тізімдердің `?search=` параметрі (DRF SearchFilter-дегідей тексеріледі)."""

    search = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
