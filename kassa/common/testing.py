"""Тесттерге ортақ дайындық: қызметкерлер, қоймалар, тауарлар және құжат жасау көмекшілері."""

import itertools
import threading
from decimal import Decimal

from django.db import connection
from django.test import TestCase, TransactionTestCase

from kassa.common.exceptions import ApplicationError
from kassa.documents.services import document_post
from kassa.inventory.models import Document, DocumentItem, Product, Stock, Supplier, User, Warehouse

T = Document.Type
S = Document.Status

_doc_numbers = itertools.count(1)


def create_fixtures(target):
    target.manager = User.objects.create_user('manager', role=User.Role.MANAGER)
    target.warehouseman = User.objects.create_user('warehouseman', role=User.Role.WAREHOUSEMAN)
    target.seller = User.objects.create_user('seller', role=User.Role.SELLER)
    target.warehouse = Warehouse.objects.create(name='Басты қойма')
    target.other_warehouse = Warehouse.objects.create(name='Екінші қойма')
    target.supplier = Supplier.objects.create(name='Серіктес ТОО')
    target.other_supplier = Supplier.objects.create(name='Басқа жеткізуші')
    target.product = Product.objects.create(
        name='Су 0.5л', sku='WATER-05', barcode='4870001112233', sale_price=Decimal('150')
    )
    target.other_product = Product.objects.create(name='Шырын 1л', sku='JUICE-1', sale_price=Decimal('500'))


class ServiceMixin:
    def make_doc(
        self,
        doc_type,
        qty,
        user=None,
        product=None,
        warehouse=None,
        supplier=None,
        base=None,
        price=Decimal('100'),
        comment=None,
    ):
        if comment is None:
            # Есептен шығаруда себеп міндетті
            comment = 'Бүлінген' if doc_type == T.WRITE_OFF else ''
        document = Document.objects.create(
            number=f'T-{next(_doc_numbers)}',
            doc_type=doc_type,
            warehouse=warehouse or self.warehouse,
            supplier=supplier,
            responsible=user or self.manager,
            base_document=base,
            comment=comment,
        )
        DocumentItem.objects.create(
            document=document, product=product or self.product, quantity=Decimal(qty), price=price
        )
        return document

    def receive(self, qty, **kwargs):
        kwargs.setdefault('supplier', self.supplier)
        return document_post(document=self.make_doc(T.RECEIPT, qty, **kwargs), user=self.warehouseman)

    def stock(self, product=None, warehouse=None):
        return Stock.objects.get(product=product or self.product, warehouse=warehouse or self.warehouse).quantity


class ServiceTestCase(ServiceMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        create_fixtures(cls)


class ConcurrencyTestCase(ServiceMixin, TransactionTestCase):
    """Нақты параллель транзакциялар: әр ағынның өз DB қосылымы бар, барлығы Barrier арқылы бір мезетте басталады."""

    THREADS = 8

    def setUp(self):
        create_fixtures(self)

    def run_parallel(self, calls):
        barrier = threading.Barrier(len(calls))
        results = [None] * len(calls)

        def worker(index, call):
            try:
                barrier.wait()
                results[index] = ('ok', call())
            except Exception as e:
                results[index] = ('error', e)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(i, call)) for i, call in enumerate(calls)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        succeeded = [value for status, value in results if status == 'ok']
        errors = [value for status, value in results if status == 'error']
        # Deadlock немесе IntegrityError сияқты күтпеген қателер болмауы тиіс — тек бизнес-тексерулер
        unexpected = [e for e in errors if not isinstance(e, ApplicationError)]
        self.assertEqual(unexpected, [])
        return succeeded, errors
