from django.apps import AppConfig


class InventoryConfig(AppConfig):
    """Барлық домендердің модельдері, миграциялары және админі.

    Label `inventory` — дерекқор кестелері (`inventory_*`) мен миграциялар тарихы алғашқы
    шаблонмен үйлесімді болуы үшін. Бизнес-логика мұнда емес, домен пакеттерінде
    (`kassa/<домен>/services.py`, `selectors.py`).
    """

    name = 'kassa.inventory'
    label = 'inventory'
    verbose_name = 'Касса және қойма'
