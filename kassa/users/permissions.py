"""API рұқсаттары рөл бойынша (CLAUDE.md RBAC). Суперпайдаланушыға бәрі рұқсат.

Бұл тек «есікті» тексереді (endpoint-ке кім кіре алады). Құжат түрі мен қойма бойынша
нақты ережелерді сервистер тексереді (kassa.documents.services).
"""

from rest_framework.permissions import BasePermission

from kassa.inventory.models import User


class HasRole(BasePermission):
    roles = frozenset()

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_superuser or user.role in self.roles))


class IsCashier(HasRole):
    """Кассалық операциялар: Сатушы, Басқарушы."""

    message = 'Кассалық операциялар тек Сатушы мен Басқарушыға рұқсат.'
    roles = frozenset({User.Role.SELLER, User.Role.MANAGER})


class IsManager(HasRole):
    message = 'Бұл есеп тек Басқарушыға рұқсат.'
    roles = frozenset({User.Role.MANAGER})


class IsManagerDocuments(IsManager):
    message = 'Құжаттар журналы мен күшін жою тек Басқарушыға рұқсат.'


class IsInventoryStaff(HasRole):
    """Түгендеу және есептер: Қоймашы (санайды), Басқарушы (бекітеді)."""

    message = 'Түгендеу тек Қоймашы мен Басқарушыға рұқсат.'
    roles = frozenset({User.Role.WAREHOUSEMAN, User.Role.MANAGER})


class IsWarehouseStaff(IsInventoryStaff):
    """Қоймалық операциялар (қабылдау, есептен шығару): Қоймашы, Басқарушы."""

    message = 'Қоймалық операциялар тек Қоймашы мен Басқарушыға рұқсат.'
