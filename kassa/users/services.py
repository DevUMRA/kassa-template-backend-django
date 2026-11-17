from rest_framework.authtoken.models import Token


def user_token_delete(*, user):
    """Шығу: пайдаланушының API токенін өшіреді — ол бар барлық құрылғыда сессия аяқталады.

    Келесі кіргенде (POST /api/auth/token/) жаңа токен жасалады.
    """
    Token.objects.filter(user=user).delete()
