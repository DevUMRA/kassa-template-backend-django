from kassa.inventory.models import User


def user_is_manager(user):
    """Басқарушы немесе суперпайдаланушы: барлық қойма, барлық құжат."""
    return user.is_superuser or user.role == User.Role.MANAGER


def user_sections(user):
    """Фронтендтің қолжетімді бөлімдері (мәзір): pos, warehouse, inventory, documents, reports."""
    manager = user_is_manager(user)
    sections = []
    if manager or user.role == User.Role.SELLER:
        sections.append('pos')
    if manager or user.role == User.Role.WAREHOUSEMAN:
        sections += ['warehouse', 'inventory']
        if manager:
            sections.append('documents')
        sections.append('reports')
    return sections


def user_profile(user):
    """GET /api/me/ жауабы: рөл, қойма және бөлімдер."""
    return {
        'username': user.username,
        'full_name': user.get_full_name() or user.username,
        'role': user.role,
        'role_display': 'Әкімші' if user.is_superuser else user.get_role_display(),
        'is_manager': user_is_manager(user),
        'warehouse': {'id': user.warehouse_id, 'name': user.warehouse.name} if user.warehouse_id else None,
        'sections': user_sections(user),
    }
