import io

from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APITestCase

from kassa.common.testing import ServiceMixin, create_fixtures
from kassa.inventory.models import User


class ApiSchemaTests(APITestCase):
    def test_schema_is_valid_and_has_no_warnings(self):
        # Жаңа endpoint құжаттамасыз (extend_schema-сыз) қосылса, осы тест құлайды
        call_command('spectacular', '--validate', '--fail-on-warn', stdout=io.StringIO(), stderr=io.StringIO())

    def test_schema_documents_all_endpoints(self):
        user = User.objects.create_user('docs')
        self.client.force_authenticate(user)

        schema = self.client.get('/api/schema/', HTTP_ACCEPT='application/vnd.oai.openapi+json').json()

        self.assertTrue(
            {
                '/api/auth/token/',
                '/api/pos/sales/',
                '/api/pos/sales/{id}/returns/',
                '/api/inventory/audits/{id}/approve/',
                '/api/reports/sales/',
                '/api/reports/turnover/',
            }
            <= set(schema['paths'])
        )
        sale_request = schema['paths']['/api/pos/sales/']['post']['requestBody']['content']['application/json']
        self.assertEqual(sale_request['schema']['$ref'], '#/components/schemas/LinesRequest')
        self.assertIn('tokenAuth', schema['components']['securitySchemes'])

    def test_health_is_public(self):
        response = self.client.get('/api/health/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'status': 'ok', 'database': 'ok'})

    def test_docs_pages_require_login(self):
        for url in ('/api/docs/', '/api/redoc/', '/api/schema/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)
        self.client.force_authenticate(User.objects.create_user('docs'))
        self.assertEqual(self.client.get('/api/docs/').status_code, 200)
        self.assertEqual(self.client.get('/api/redoc/').status_code, 200)


class LocalizationTests(ServiceMixin, APITestCase):
    """Django/DRF стандарт хабарлары қазақша (LANGUAGE_CODE='kk')."""

    @classmethod
    def setUpTestData(cls):
        create_fixtures(cls)
        cls.warehouseman.warehouse = cls.warehouse
        cls.warehouseman.save()

    def test_field_errors_are_in_kazakh(self):
        self.client.force_authenticate(self.warehouseman)

        response = self.client.post(
            '/api/warehouse/write-offs/',
            {
                'items': [{'product_id': self.product.pk, 'quantity': '-1'}],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['comment'], ['Бұл мән міндетті.'])
        self.assertIn('кемінде', response.data['items'][0]['quantity'][0])

    def test_auth_errors_are_in_kazakh(self):
        response = self.client.get('/api/warehouse/write-offs/')

        self.assertEqual(response.status_code, 401)
        self.assertNotIn('credentials', str(response.data['detail']))

    def test_broken_json_has_readable_message(self):
        self.client.force_authenticate(self.warehouseman)

        response = self.client.post('/api/warehouse/write-offs/', b'{"items": [', content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('JSON', response.data['detail'])
        self.assertIn('UTF-8', response.data['detail'])

    def test_admin_login_page_is_in_kazakh(self):
        # Бұрын кірмеген пайдаланушыда кіру беті 500 беретін (AnonymousUser-де role жоқ)
        response = self.client.get(reverse('admin:login'))

        self.assertContains(response, 'lang="kk"')
        self.assertRedirects(self.client.get(reverse('admin:index')), f'{reverse("admin:login")}?next=/admin/')
