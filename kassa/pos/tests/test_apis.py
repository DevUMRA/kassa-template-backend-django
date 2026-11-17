from rest_framework.test import APITestCase

from kassa.common.testing import S, ServiceMixin, T, create_fixtures
from kassa.inventory.models import Document, User


class PosApiTests(ServiceMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        create_fixtures(cls)
        for user in (cls.seller, cls.manager, cls.warehouseman):
            user.warehouse = cls.warehouse
            user.save()

    def setUp(self):
        self.receive(100)
        self.client.force_authenticate(self.seller)

    def sell(self, *items, user=None):
        if user:
            self.client.force_authenticate(user)
        return self.client.post('/api/pos/sales/', {'items': list(items)}, format='json')

    def sell_water(self, qty, user=None):
        return self.sell({'barcode': '4870001112233', 'quantity': str(qty)}, user=user)

    def return_items(self, sale_id, *items):
        return self.client.post(f'/api/pos/sales/{sale_id}/returns/', {'items': list(items)}, format='json')

    def test_requires_authentication(self):
        self.client.force_authenticate(None)

        self.assertEqual(self.client.get('/api/pos/products/').status_code, 401)

    def test_token_auth(self):
        self.seller.set_password('secret-123')
        self.seller.save()
        self.client.force_authenticate(None)

        response = self.client.post('/api/auth/token/', {'username': 'seller', 'password': 'secret-123'})
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {response.data["token"]}')

        self.assertEqual(self.client.get('/api/pos/products/').status_code, 200)

    def test_products_show_available_stock_of_cashier_warehouse(self):
        self.receive(7, warehouse=self.other_warehouse)

        response = self.client.get('/api/pos/products/', {'search': 'Су'})

        self.assertEqual(response.status_code, 200)
        [product] = response.data['results']
        self.assertEqual(product['barcode'], '4870001112233')
        self.assertEqual(product['available'], '100.000')

    def test_product_without_stock_has_zero_available(self):
        response = self.client.get(f'/api/pos/products/{self.other_product.pk}/')

        self.assertEqual(response.data['available'], '0.000')

    def test_barcode_lookup(self):
        response = self.client.get('/api/pos/products/barcode/4870001112233/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Су 0.5л')
        self.assertEqual(self.client.get('/api/pos/products/barcode/000/').status_code, 404)

    def test_sale_is_created_and_posted_with_server_price(self):
        # Клиент жіберген баға еленбейді — баға тауардың сату бағасынан алынады
        response = self.sell({'barcode': '4870001112233', 'quantity': '3', 'price': '1'})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], S.POSTED)
        self.assertEqual(response.data['number'], f'SAL-{response.data["id"]:06d}')
        self.assertEqual(response.data['items'][0]['price'], '150.00')
        self.assertEqual(response.data['total'], '450.00')
        self.assertEqual(response.data['cashier'], 'seller')
        self.assertEqual(self.stock(), 97)

    def test_duplicate_lines_are_merged(self):
        response = self.sell(
            {'barcode': '4870001112233', 'quantity': '2'},
            {'product_id': self.product.pk, 'quantity': '3'},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(response.data['items'][0]['quantity'], '5.000')
        self.assertEqual(self.stock(), 95)

    def test_oversell_returns_400_and_leaves_no_document(self):
        documents_before = Document.objects.count()

        response = self.sell_water(101)

        self.assertEqual(response.status_code, 400)
        self.assertIn('Қалдық жеткіліксіз:', response.data['detail'])
        self.assertEqual(Document.objects.count(), documents_before)
        self.assertEqual(self.stock(), 100)

    def test_invalid_lines_are_rejected(self):
        cases = [
            [],
            [{'quantity': '1'}],
            [{'barcode': '4870001112233', 'product_id': self.product.pk, 'quantity': '1'}],
            [{'barcode': 'unknown', 'quantity': '1'}],
            [{'barcode': '4870001112233', 'quantity': '0'}],
        ]
        for items in cases:
            with self.subTest(items=items):
                self.assertEqual(self.sell(*items).status_code, 400)
        self.assertEqual(self.stock(), 100)

    def test_warehouseman_cannot_sell(self):
        self.assertEqual(self.sell_water(1, user=self.warehouseman).status_code, 403)

    def test_cashier_without_warehouse_cannot_sell(self):
        self.seller.warehouse = None
        self.seller.save()

        response = self.sell_water(1)

        self.assertEqual(response.status_code, 400)
        self.assertIn('қойма бекітілмеген', response.data['detail'][0])

    def test_sale_during_inventory_is_rejected(self):
        self.make_doc(T.INVENTORY, 90)

        response = self.sell_water(1)

        self.assertEqual(response.status_code, 400)
        self.assertIn('түгендеуінде бұғатталған', response.data['detail'][0])

    def test_seller_sees_only_own_warehouse_sales(self):
        own = self.sell_water(1).data['id']
        other_seller = User.objects.create_user('other', role=User.Role.SELLER, warehouse=self.other_warehouse)
        self.receive(10, warehouse=self.other_warehouse)
        foreign = self.sell_water(1, user=other_seller).data['id']

        self.client.force_authenticate(self.seller)
        self.assertEqual([s['id'] for s in self.client.get('/api/pos/sales/').data['results']], [own])
        self.assertEqual(self.client.get(f'/api/pos/sales/{foreign}/').status_code, 404)

        self.client.force_authenticate(self.manager)
        self.assertEqual({s['id'] for s in self.client.get('/api/pos/sales/').data['results']}, {own, foreign})

    def test_search_sale_by_number(self):
        number = self.sell_water(1).data['number']
        self.sell_water(1)

        results = self.client.get('/api/pos/sales/', {'search': number}).data['results']

        self.assertEqual([sale['number'] for sale in results], [number])

    def test_return_within_sold_quantity(self):
        sale = self.sell_water(5).data

        response = self.return_items(sale['id'], {'barcode': '4870001112233', 'quantity': '2'})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['number'], f'SRT-{response.data["id"]:06d}')
        self.assertEqual(response.data['items'][0]['price'], '150.00')
        self.assertEqual(response.data['total'], '300.00')
        self.assertEqual(self.stock(), 97)

        detail = self.client.get(f'/api/pos/sales/{sale["id"]}/').data
        self.assertEqual(detail['returnable'], {str(self.product.pk): '3.000'})
        self.assertEqual([r['number'] for r in detail['returns']], [response.data['number']])

    def test_return_more_than_sold_is_rejected(self):
        sale = self.sell_water(5).data

        response = self.return_items(sale['id'], {'barcode': '4870001112233', 'quantity': '6'})

        self.assertEqual(response.status_code, 400)
        self.assertIn('қайтаруға болатыны 5.000', response.data['detail'][0])
        self.assertEqual(self.stock(), 95)

    def test_return_of_product_not_in_sale_is_rejected(self):
        sale = self.sell_water(5).data

        response = self.return_items(sale['id'], {'product_id': self.other_product.pk, 'quantity': '1'})

        self.assertEqual(response.status_code, 400)
        self.assertIn('құжатында жоқ', response.data['detail'][0])
