"""Домен қателері және оларды HTTP-ға айналдыру — бір жерде.

Сервистер мен селекторлар тек осы қателерді лақтырады (HTTP туралы ештеңе білмейді),
API жауабын `exception_handler` жасайды (settings: REST_FRAMEWORK['EXCEPTION_HANDLER']).
"""

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class ApplicationError(Exception):
    """Барлық домен қателерінің негізі. `messages` — пайдаланушыға көрсетілетін хабарлар тізімі."""

    def __init__(self, messages):
        self.messages = [messages] if isinstance(messages, str) else list(messages)
        super().__init__(' '.join(self.messages))


class BusinessRuleError(ApplicationError):
    """Бизнес-ереже бұзылды (қалдық жетпейді, түгендеу бұғаты, …) → 400 {"detail": ["...", ...]}."""


class AccessDeniedError(ApplicationError):
    """Рөлге немесе қоймаға рұқсат жоқ → 403 {"detail": "..."}."""


def exception_handler(exc, context):
    if isinstance(exc, AccessDeniedError):
        return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, BusinessRuleError):
        return Response({'detail': exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    # Django-ның өз қателері (мысалы, model.full_clean()) — DRF оларды хабарламасыз береді
    if isinstance(exc, DjangoValidationError):
        return Response({'detail': exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, DjangoPermissionDenied) and exc.args:
        return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, ParseError):
        # DRF-тің «JSON parse error» хабарының аудармасы жоқ, ал ішкі мәтіні (кодек қатесі) пайдаланушыға түсініксіз
        return Response(
            {'detail': 'Сұраныс денесі оқылмады: JSON пішімі мен UTF-8 кодтауын тексеріңіз.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return drf_exception_handler(exc, context)
