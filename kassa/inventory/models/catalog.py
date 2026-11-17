from django.core.validators import MinValueValidator
from django.db import models


class Product(models.Model):
    class Unit(models.TextChoices):
        PIECE = 'PCS', 'дана'
        KILOGRAM = 'KG', 'кг'
        LITER = 'L', 'литр'
        METER = 'M', 'метр'
        PACK = 'PACK', 'қаптама'

    name = models.CharField('Атауы', max_length=255)
    sku = models.CharField('Артикулы', max_length=64, unique=True)
    barcode = models.CharField('Штрихкоды', max_length=64, unique=True, null=True, blank=True)
    category = models.CharField('Санаты', max_length=128, blank=True)
    unit = models.CharField('Өлшем бірлігі', max_length=10, choices=Unit.choices, default=Unit.PIECE)
    sale_price = models.DecimalField('Сату бағасы', max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    is_active = models.BooleanField('Белсенді', default=True)

    class Meta:
        verbose_name = 'Тауар'
        verbose_name_plural = 'Тауарлар'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} [{self.sku}]'


class Supplier(models.Model):
    name = models.CharField('Атауы', max_length=255)
    contact_person = models.CharField('Байланыс тұлғасы', max_length=255, blank=True)
    phone = models.CharField('Телефоны', max_length=32, blank=True)
    email = models.EmailField('Email', blank=True)
    address = models.CharField('Мекенжайы', max_length=255, blank=True)
    bin = models.CharField('БСН/ЖСН', max_length=12, blank=True)
    bank_account = models.CharField('ИИК (шот)', max_length=34, blank=True)
    bank_name = models.CharField('Банк', max_length=255, blank=True)
    bik = models.CharField('БСК', max_length=11, blank=True)

    class Meta:
        verbose_name = 'Жеткізуші'
        verbose_name_plural = 'Жеткізушілер'
        ordering = ['name']

    def __str__(self):
        return self.name


class Warehouse(models.Model):
    name = models.CharField('Атауы', max_length=255, unique=True)
    address = models.CharField('Мекенжайы', max_length=255, blank=True)
    is_active = models.BooleanField('Белсенді', default=True)

    class Meta:
        verbose_name = 'Қойма'
        verbose_name_plural = 'Қоймалар'
        ordering = ['name']

    def __str__(self):
        return self.name
