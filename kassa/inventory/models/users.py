from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        SELLER = 'SELLER', 'Сатушы'
        WAREHOUSEMAN = 'WAREHOUSEMAN', 'Қоймашы'
        MANAGER = 'MANAGER', 'Басқарушы'

    role = models.CharField('Рөлі', max_length=20, choices=Role.choices, default=Role.SELLER)
    # Кассир осы қоймадан сатады (POS API)
    warehouse = models.ForeignKey(
        'Warehouse',
        on_delete=models.PROTECT,
        related_name='staff',
        null=True,
        blank=True,
        verbose_name='Қоймасы',
    )

    class Meta:
        verbose_name = 'Қызметкер'
        verbose_name_plural = 'Қызметкерлер'

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.get_role_display()})'

    @property
    def is_seller(self):
        return self.role == self.Role.SELLER

    @property
    def is_warehouseman(self):
        return self.role == self.Role.WAREHOUSEMAN

    @property
    def is_manager(self):
        return self.role == self.Role.MANAGER
