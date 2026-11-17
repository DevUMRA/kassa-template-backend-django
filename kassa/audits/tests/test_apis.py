from decimal import Decimal

from rest_framework.test import APITestCase

from kassa.common.testing import S, ServiceMixin, T, create_fixtures
from kassa.documents.services import document_post
from kassa.inventory.models import StockMovement, User


class InventoryApiTests(ServiceMixin, APITestCase):
    URL = '/api/inventory/audits/'

    @classmethod
    def setUpTestData(cls):
        create_fixtures(cls)
        for user in (cls.seller, cls.manager, cls.warehouseman):
            user.warehouse = cls.warehouse
            user.save()

    def setUp(self):
        self.receive(100)
        self.receive(20, product=self.other_product)
        self.client.force_authenticate(self.warehouseman)

    def start(self, payload=None):
        return self.client.post(self.URL, payload or {'product_ids': [self.product.pk]}, format='json')

    def count(self, audit_id, *items):
        return self.client.post(f'{self.URL}{audit_id}/counts/', {'items': list(items)}, format='json')

    def as_manager(self):
        self.client.force_authenticate(self.manager)

    def test_full_flow_start_count_approve(self):
        audit = self.start({'product_ids': [self.product.pk, self.other_product.pk]}).data
        self.assertEqual(audit['status'], S.DRAFT)
        self.assertEqual(audit['progress'], {'total': 2, 'counted': 0})

        response = self.count(
            audit['id'],
            {'barcode': '4870001112233', 'quantity': '97'},
            {'product_id': self.other_product.pk, 'quantity': '20'},
        )
        self.assertEqual(response.status_code, 200)
        items = {item['product_id']: item for item in response.data['items']}
        self.assertEqual(items[self.product.pk]['expected_quantity'], '100.000')
        self.assertEqual(items[self.product.pk]['counted_quantity'], '97.000')
        self.assertEqual(items[self.product.pk]['difference'], '-3.000')
        self.assertEqual(items[self.other_product.pk]['difference'], '0.000')

        self.as_manager()
        response = self.client.post(f'{self.URL}{audit["id"]}/approve/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], S.POSTED)
        self.assertEqual(self.stock(), 97)
        self.assertEqual(self.stock(self.other_product), 20)
        self.assertEqual(
            list(StockMovement.objects.filter(document_id=audit['id']).values_list('quantity', flat=True)),
            [Decimal(-3)],
        )

    def test_start_all_active_products(self):
        response = self.start({'all': True})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['progress']['total'], 2)

    def test_invalid_start_payloads(self):
        cases = [{}, {'product_ids': []}, {'product_ids': [999999]}, {'product_ids': [self.product.pk], 'all': True}]
        for payload in cases:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post(self.URL, payload, format='json').status_code, 400)

    def test_running_inventory_blocks_pos_sale(self):
        self.start()
        self.client.force_authenticate(self.seller)

        response = self.client.post(
            '/api/pos/sales/', {'items': [{'barcode': '4870001112233', 'quantity': '1'}]}, format='json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('түгендеуінде бұғатталған', response.data['detail'][0])

    def test_recount_overwrites_previous_value(self):
        audit = self.start().data
        self.count(audit['id'], {'barcode': '4870001112233', 'quantity': '90'})

        response = self.count(audit['id'], {'barcode': '4870001112233', 'quantity': '0'})

        self.assertEqual(response.data['items'][0]['counted_quantity'], '0.000')

    def test_count_of_product_not_in_audit_is_rejected(self):
        audit = self.start().data

        response = self.count(audit['id'], {'product_id': self.other_product.pk, 'quantity': '1'})

        self.assertEqual(response.status_code, 400)
        self.assertIn('түгендеуінде жоқ', response.data['detail'][0])

    def test_approve_requires_all_counted(self):
        audit = self.start({'product_ids': [self.product.pk, self.other_product.pk]}).data
        self.count(audit['id'], {'barcode': '4870001112233', 'quantity': '97'})
        self.as_manager()

        response = self.client.post(f'{self.URL}{audit["id"]}/approve/')

        self.assertEqual(response.status_code, 400)
        self.assertIn('әлі саналмаған', response.data['detail'][0])
        self.assertEqual(self.stock(), 100)

    def test_warehouseman_cannot_approve(self):
        audit = self.start().data
        self.count(audit['id'], {'barcode': '4870001112233', 'quantity': '97'})

        response = self.client.post(f'{self.URL}{audit["id"]}/approve/')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.stock(), 100)

    def test_counts_after_approve_are_rejected(self):
        audit = self.start().data
        self.count(audit['id'], {'barcode': '4870001112233', 'quantity': '97'})
        self.as_manager()
        self.client.post(f'{self.URL}{audit["id"]}/approve/')

        response = self.count(audit['id'], {'barcode': '4870001112233', 'quantity': '50'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.stock(), 97)

    def test_manager_cancels_running_audit_and_unblocks_sales(self):
        audit = self.start().data
        self.as_manager()

        response = self.client.post(f'{self.URL}{audit["id"]}/cancel/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], S.CANCELED)
        document_post(document=self.make_doc(T.SALE, 1), user=self.seller)
        self.assertEqual(self.stock(), 99)

    def test_seller_has_no_access(self):
        self.client.force_authenticate(self.seller)

        self.assertEqual(self.client.get(self.URL).status_code, 403)
        self.assertEqual(self.start().status_code, 403)

    def test_warehouseman_sees_only_own_warehouse(self):
        own = self.start().data['id']
        other = User.objects.create_user('wh2', role=User.Role.WAREHOUSEMAN, warehouse=self.other_warehouse)
        self.client.force_authenticate(other)
        foreign = self.start().data['id']

        self.assertEqual([a['id'] for a in self.client.get(self.URL).data['results']], [foreign])
        self.assertEqual(self.count(own, {'barcode': '4870001112233', 'quantity': '1'}).status_code, 404)

        self.as_manager()
        self.assertEqual({a['id'] for a in self.client.get(self.URL).data['results']}, {own, foreign})
        self.assertEqual(
            [a['id'] for a in self.client.get(self.URL, {'status': 'DRAFT'}).data['results'] if a['id'] == own], [own]
        )
