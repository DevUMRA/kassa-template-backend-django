from decimal import Decimal

from rest_framework.test import APITestCase

from kassa.audits.services import inventory_start
from kassa.common.testing import S, ServiceMixin, T, create_fixtures
from kassa.inventory.models import Document, StockMovement, User


class WriteOffApiTests(ServiceMixin, APITestCase):
    URL = '/api/warehouse/write-offs/'

    @classmethod
    def setUpTestData(cls):
        create_fixtures(cls)
        for user in (cls.seller, cls.manager, cls.warehouseman):
            user.warehouse = cls.warehouse
            user.save()

    def setUp(self):
        self.receive(10)
        self.client.force_authenticate(self.warehouseman)

    def write_off(self, quantity='2', comment='Бүлінген', **line):
        payload = {'items': [line or {'barcode': '4870001112233', 'quantity': quantity}]}
        if comment is not None:
            payload['comment'] = comment
        return self.client.post(self.URL, payload, format='json')

    def test_write_off_decreases_stock_and_logs_movement(self):
        response = self.write_off('2', '  Бөтелке жарылған  ')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], S.POSTED)
        self.assertTrue(response.data['number'].startswith('WOF-'))
        self.assertEqual(response.data['comment'], 'Бөтелке жарылған')
        self.assertEqual(response.data['total'], '300.00')  # 2 × сату бағасы 150
        self.assertEqual(response.data['responsible'], 'warehouseman')
        self.assertEqual(self.stock(), 8)
        movement = StockMovement.objects.get(document_id=response.data['id'])
        self.assertEqual((movement.quantity, movement.user), (Decimal('-2'), self.warehouseman))

    def test_reason_is_required(self):
        for comment in (None, '', '   '):
            with self.subTest(comment=comment):
                response = self.write_off(comment=comment)

                self.assertEqual(response.status_code, 400)
                self.assertIn('comment', response.data)
        self.assertEqual(self.stock(), 10)
        self.assertFalse(Document.objects.filter(doc_type=T.WRITE_OFF).exists())

    def test_insufficient_stock_saves_nothing(self):
        response = self.write_off('11')

        self.assertEqual(response.status_code, 400)
        self.assertIn('Қалдық жеткіліксіз', ' '.join(response.data['detail']))
        self.assertEqual(self.stock(), 10)
        self.assertFalse(Document.objects.filter(doc_type=T.WRITE_OFF).exists())

    def test_blocked_by_inventory(self):
        inventory_start(user=self.warehouseman, products=[self.product])

        response = self.write_off('1')

        self.assertEqual(response.status_code, 400)
        self.assertIn('бұғатталған', ' '.join(response.data['detail']))
        self.assertEqual(self.stock(), 10)

    def test_seller_is_forbidden(self):
        self.client.force_authenticate(self.seller)

        self.assertEqual(self.write_off().status_code, 403)
        self.assertEqual(self.client.get(self.URL).status_code, 403)
        self.assertEqual(self.stock(), 10)

    def test_warehouseman_sees_only_own_warehouse(self):
        self.write_off('1')
        other = User.objects.create_user('other', role=User.Role.WAREHOUSEMAN, warehouse=self.other_warehouse)
        self.receive(5, warehouse=self.other_warehouse)
        self.client.force_authenticate(other)
        self.write_off('1')

        self.assertEqual(self.client.get(self.URL).data['count'], 1)
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.get(self.URL).data['count'], 2)

    def test_shows_in_inventory_report(self):
        self.write_off('3', 'Мерзімі өткен')
        self.client.force_authenticate(self.manager)

        report = self.client.get('/api/reports/inventory/').data['write_offs']

        self.assertEqual(report['total_quantity'], '3.000')
        self.assertEqual([d['reason'] for d in report['documents']], ['Мерзімі өткен'])


class ReceiptApiTests(ServiceMixin, APITestCase):
    URL = '/api/warehouse/receipts/'

    @classmethod
    def setUpTestData(cls):
        create_fixtures(cls)
        for user in (cls.seller, cls.manager, cls.warehouseman):
            user.warehouse = cls.warehouse
            user.save()

    def setUp(self):
        self.client.force_authenticate(self.warehouseman)

    def receipt(self, *items, supplier=None, comment=''):
        items = items or ({'barcode': '4870001112233', 'quantity': '10', 'price': '90.50'},)
        return self.client.post(
            self.URL,
            {
                'supplier_id': (supplier or self.supplier).pk,
                'items': list(items),
                'comment': comment,
            },
            format='json',
        )

    def give_back(self, receipt_id, quantity, comment=''):
        return self.client.post(
            f'{self.URL}{receipt_id}/returns/',
            {
                'items': [{'product_id': self.product.pk, 'quantity': quantity}],
                'comment': comment,
            },
            format='json',
        )

    def test_receipt_increases_stock_with_purchase_price(self):
        response = self.receipt(comment='Накладной №17')

        self.assertEqual(response.status_code, 201)
        data = response.data
        self.assertTrue(data['number'].startswith('RCV-'))
        self.assertEqual(
            (data['status'], data['supplier'], data['comment']), (S.POSTED, 'Серіктес ТОО', 'Накладной №17')
        )
        self.assertEqual(data['items'][0]['price'], '90.50')
        self.assertEqual(data['total'], '905.00')
        self.assertEqual(data['returnable'], {str(self.product.pk): '10.000'})
        self.assertEqual(self.stock(), 10)

    def test_duplicate_lines_are_merged_but_price_must_match(self):
        same = {'product_id': self.product.pk, 'quantity': '2', 'price': '90'}

        self.assertEqual(self.receipt(same, same).data['items'][0]['quantity'], '4.000')
        response = self.receipt(same, {**same, 'price': '95'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('әртүрлі бағамен', ' '.join(response.data['detail']))
        self.assertEqual(self.stock(), 4)

    def test_invalid_input_is_rejected(self):
        line = {'product_id': self.product.pk, 'quantity': '1', 'price': '10'}
        cases = {
            'no price': {'supplier_id': self.supplier.pk, 'items': [{'product_id': self.product.pk, 'quantity': '1'}]},
            'negative price': {'supplier_id': self.supplier.pk, 'items': [{**line, 'price': '-1'}]},
            'unknown supplier': {'supplier_id': 999999, 'items': [line]},
            'no supplier': {'items': [line]},
            'no items': {'supplier_id': self.supplier.pk, 'items': []},
        }
        for name, payload in cases.items():
            with self.subTest(name):
                self.assertEqual(self.client.post(self.URL, payload, format='json').status_code, 400)
        self.assertFalse(Document.objects.exists())

    def test_supplier_return_uses_receipt_supplier_and_price(self):
        receipt = self.receipt().data

        response = self.give_back(receipt['id'], '3', 'Ақаулы партия')

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['number'].startswith('RTS-'))
        self.assertEqual(response.data['items'][0]['price'], '90.50')
        self.assertEqual(response.data['comment'], 'Ақаулы партия')
        document = Document.objects.get(pk=response.data['id'])
        self.assertEqual((document.supplier, document.base_document_id), (self.supplier, receipt['id']))
        self.assertEqual(self.stock(), 7)
        self.assertEqual(
            self.client.get(f'{self.URL}{receipt["id"]}/').data['returnable'], {str(self.product.pk): '7.000'}
        )

    def test_supplier_return_cannot_exceed_received(self):
        receipt = self.receipt().data
        self.give_back(receipt['id'], '8')

        response = self.give_back(receipt['id'], '3')

        self.assertEqual(response.status_code, 400)
        self.assertIn('қайтаруға болатыны 2', ' '.join(response.data['detail']))
        self.assertEqual(self.stock(), 2)

    def test_supplier_return_cannot_exceed_stock(self):
        receipt = self.receipt().data
        self.client.force_authenticate(self.manager)
        self.client.post(
            '/api/pos/sales/', {'items': [{'product_id': self.product.pk, 'quantity': '9'}]}, format='json'
        )
        self.client.force_authenticate(self.warehouseman)

        response = self.give_back(receipt['id'], '5')

        self.assertEqual(response.status_code, 400)
        self.assertIn('Қалдық жеткіліксіз', ' '.join(response.data['detail']))
        self.assertEqual(self.stock(), 1)

    def test_receipt_blocked_by_inventory(self):
        self.receipt()
        inventory_start(user=self.warehouseman, products=[self.product])

        response = self.receipt()

        self.assertEqual(response.status_code, 400)
        self.assertIn('бұғатталған', ' '.join(response.data['detail']))
        self.assertEqual(self.stock(), 10)

    def test_access(self):
        self.client.force_authenticate(self.seller)
        self.assertEqual(self.receipt().status_code, 403)
        self.assertEqual(self.client.get(self.URL).status_code, 403)
        self.assertEqual(self.client.get('/api/warehouse/suppliers/').status_code, 403)

        other = User.objects.create_user('other', role=User.Role.WAREHOUSEMAN, warehouse=self.other_warehouse)
        self.client.force_authenticate(self.warehouseman)
        receipt = self.receipt().data
        self.client.force_authenticate(other)
        # Басқа қойманың қабылдауы көрінбейді және одан қайтаруға болмайды
        self.assertEqual(self.client.get(self.URL).data['count'], 0)
        self.assertEqual(self.give_back(receipt['id'], '1').status_code, 404)
        self.assertEqual(self.stock(), 10)

    def test_supplier_search(self):
        response = self.client.get('/api/warehouse/suppliers/', {'search': 'Серік'})

        self.assertEqual([s['name'] for s in response.data['results']], ['Серіктес ТОО'])
