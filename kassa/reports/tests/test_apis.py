from datetime import date, datetime
from datetime import timezone as dt_timezone
from decimal import Decimal

from rest_framework.test import APITestCase

from kassa.common.testing import ServiceMixin, T, create_fixtures
from kassa.documents.services import document_cancel, document_post
from kassa.inventory.models import Document, StockMovement


class ReportApiTests(ServiceMixin, APITestCase):
    """Есептер: құжаттардың уақыты кезеңдерді тексеру үшін нақты күндерге жылжытылады."""

    @classmethod
    def setUpTestData(cls):
        create_fixtures(cls)
        for user in (cls.seller, cls.manager, cls.warehouseman):
            user.warehouse = cls.warehouse
            user.save()

    def setUp(self):
        self.client.force_authenticate(self.manager)

    def on(self, document, day):
        """Құжатты және оның қозғалыстарын 2026-09-<day> 12:00 уақытына жылжытады."""
        moment = datetime(2026, 9, day, 12, tzinfo=dt_timezone.utc)
        Document.objects.filter(pk=document.pk).update(posted_at=moment)
        StockMovement.objects.filter(document=document).update(date=moment)
        return document

    def get(self, name, **params):
        return self.client.get(f'/api/reports/{name}/', params)

    def build_history(self):
        """1-қыркүйек: +100 қабылдау; 10: сату 10 және 5; 11: 2 қайтару, 3 есептен шығару; 12: түгендеу 79 (−1)."""
        self.on(self.receive(100), 1)
        sale = self.on(document_post(document=self.make_doc(T.SALE, 10, price=150), user=self.seller), 10)
        self.on(document_post(document=self.make_doc(T.SALE, 5, price=150), user=self.seller), 10)
        canceled = document_post(document=self.make_doc(T.SALE, 1, price=150), user=self.seller)
        document_cancel(document=canceled, user=self.manager, reason='Қате енгізілген')
        self.on(canceled, 10)
        self.on(document_post(document=self.make_doc(T.SALE_RETURN, 2, base=sale, price=150), user=self.seller), 11)
        self.on(document_post(document=self.make_doc(T.WRITE_OFF, 3, price=100), user=self.warehouseman), 11)
        self.on(document_post(document=self.make_doc(T.INVENTORY, 83, price=150), user=self.manager), 12)
        self.assertEqual(self.stock(), 83)

    def test_stock_report_totals_and_low_filter(self):
        self.receive(100)
        self.receive(5, product=self.other_product)

        report = self.get('stock').data

        self.assertEqual(report['totals'], {'positions': 2, 'value': '17500.00'})  # 100×150 + 5×500
        low = self.get('stock', low='10').data['rows']
        self.assertEqual([row['product_name'] for row in low], ['Шырын 1л'])

    def test_turnover_opening_incoming_outgoing_closing(self):
        self.build_history()

        report = self.get('turnover', date_from='2026-09-10', date_to='2026-09-12').data

        [row] = report['rows']
        # Бастапқы 100; кіріс: +1 кері (күші жойылған сату) +2 қайтару; шығыс: 10+5+1 сату, 3 шығару, 1 түгендеу
        self.assertEqual(
            (row['opening'], row['incoming'], row['outgoing'], row['closing']),
            ('100.000', '3.000', '20.000', '83.000'),
        )
        self.assertEqual(Decimal(row['closing']), self.stock())

    def test_turnover_before_any_movement_is_empty(self):
        self.build_history()

        self.assertEqual(self.get('turnover', date_from='2026-08-01', date_to='2026-08-31').data['rows'], [])

    def test_movements_journal_is_filtered_and_paginated(self):
        self.build_history()

        report = self.get('movements', date_from='2026-09-10', date_to='2026-09-10', doc_type='SALE').data

        self.assertEqual(report['count'], 4)  # 10, 5, 1 және оның кері жазбасы
        self.assertEqual(report['date_from'], date(2026, 9, 10))
        self.assertEqual({row['quantity'] for row in report['results']}, {'-10.000', '-5.000', '-1.000', '1.000'})

    def test_sales_report_by_day_excludes_canceled_and_subtracts_returns(self):
        self.build_history()

        report = self.get('sales', date_from='2026-09-01', date_to='2026-09-30').data

        self.assertEqual(
            [(row['day'], row['receipts'], row['sold_amount'], row['returned_amount']) for row in report['rows']],
            [(date(2026, 9, 10), 2, '2250.00', '0.00'), (date(2026, 9, 11), 0, '0.00', '300.00')],
        )
        self.assertEqual(report['totals']['net_amount'], '1950.00')

    def test_sales_report_by_product_and_cashier(self):
        self.build_history()
        period = {'date_from': '2026-09-01', 'date_to': '2026-09-30'}

        [by_product] = self.get('sales', group_by='product', **period).data['rows']
        [by_cashier] = self.get('sales', group_by='cashier', **period).data['rows']

        self.assertEqual((by_product['sold_qty'], by_product['returned_qty']), ('15.000', '2.000'))
        self.assertEqual((by_cashier['cashier'], by_cashier['net_amount']), ('manager', '1950.00'))

    def test_inventory_report_shortage_and_write_offs(self):
        self.build_history()

        report = self.get('inventory', date_from='2026-09-01', date_to='2026-09-30').data

        [audit] = report['audits']
        self.assertEqual(audit['lines'][0]['difference'], '-1.000')
        self.assertEqual(report['totals']['shortage_amount'], '150.00')
        self.assertEqual(report['totals']['surplus_qty'], '0.000')
        self.assertEqual(
            (report['write_offs']['total_quantity'], report['write_offs']['total_amount']), ('3.000', '300.00')
        )
        self.assertEqual({doc['reason'] for doc in report['write_offs']['documents']}, {'Бүлінген'})

    def test_warehouseman_sees_only_own_warehouse(self):
        self.receive(100)
        self.receive(7, warehouse=self.other_warehouse)
        self.client.force_authenticate(self.warehouseman)

        rows = self.get('stock').data['rows']

        self.assertEqual([row['warehouse'] for row in rows], ['Басты қойма'])
        self.assertEqual(self.get('stock', warehouse=self.other_warehouse.pk).status_code, 403)

    def test_manager_filters_by_warehouse(self):
        self.receive(100)
        self.receive(7, warehouse=self.other_warehouse)

        self.assertEqual(len(self.get('stock').data['rows']), 2)
        rows = self.get('stock', warehouse=self.other_warehouse.pk).data['rows']
        self.assertEqual([row['quantity'] for row in rows], ['7.000'])

    def test_access_by_role(self):
        self.client.force_authenticate(self.seller)
        for name in ('stock', 'movements', 'turnover', 'sales', 'inventory'):
            with self.subTest(report=name):
                self.assertEqual(self.get(name).status_code, 403)

        self.client.force_authenticate(self.warehouseman)
        self.assertEqual(self.get('sales').status_code, 403)
        self.assertEqual(self.get('turnover').status_code, 200)

    def test_invalid_period_is_rejected(self):
        self.assertEqual(self.get('turnover', date_from='2026-09-30', date_to='2026-09-01').status_code, 400)
        self.assertEqual(self.get('sales', group_by='week').status_code, 400)
