from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from kassa.common.testing import ServiceMixin, create_fixtures
from kassa.inventory.models import User


class MeEndpointTests(ServiceMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        create_fixtures(cls)
        cls.seller.warehouse = cls.warehouse
        cls.seller.save()

    def test_sections_by_role(self):
        expected = {
            self.seller: ['pos'],
            self.warehouseman: ['warehouse', 'inventory', 'reports'],
            self.manager: ['pos', 'warehouse', 'inventory', 'documents', 'reports'],
        }
        for user, sections in expected.items():
            with self.subTest(role=user.role):
                self.client.force_login(user)
                self.assertEqual(self.client.get('/api/me/').json()['sections'], sections)

    def test_me_shows_warehouse(self):
        self.client.force_login(self.seller)

        data = self.client.get('/api/me/').json()

        self.assertEqual(data['warehouse'], {'id': self.warehouse.pk, 'name': 'Басты қойма'})


class TokenAuthTests(APITestCase):
    """SPA басқа доменде: кіру — токен алу, шығу — токенді өшіру."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('seller', password='secret-123', role=User.Role.SELLER)

    def login(self):
        response = self.client.post('/api/auth/token/', {'username': 'seller', 'password': 'secret-123'}, format='json')
        self.assertEqual(response.status_code, 200)
        return response.data['token']

    def test_login_then_me_with_token(self):
        token = self.login()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        response = self.client.get('/api/me/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'seller')

    def test_wrong_password_is_rejected(self):
        response = self.client.post('/api/auth/token/', {'username': 'seller', 'password': 'wrong'}, format='json')

        self.assertEqual(response.status_code, 400)

    def test_logout_deletes_token(self):
        token = self.login()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        response = self.client.post('/api/auth/logout/')

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Token.objects.filter(user=self.user).exists())
        # Ескі токен енді жарамсыз
        self.assertEqual(self.client.get('/api/me/').status_code, 401)

    def test_login_after_logout_issues_new_token(self):
        old = self.login()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {old}')
        self.client.post('/api/auth/logout/')
        self.client.credentials()

        self.assertNotEqual(self.login(), old)

    def test_logout_requires_authentication(self):
        self.assertEqual(self.client.post('/api/auth/logout/').status_code, 401)


@override_settings(CORS_ALLOWED_ORIGINS=['https://front.example.kz'])
class CorsTests(APITestCase):
    """Frontend басқа доменде: тек рұқсат етілген origin-ге CORS тақырыптары беріледі."""

    def preflight(self, origin, path='/api/me/'):
        return self.client.options(
            path,
            HTTP_ORIGIN=origin,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET',
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS='authorization',
        )

    def test_preflight_from_allowed_origin(self):
        response = self.preflight('https://front.example.kz')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'https://front.example.kz')
        self.assertIn('authorization', response.headers['Access-Control-Allow-Headers'])

    def test_preflight_from_unknown_origin_has_no_cors_headers(self):
        response = self.preflight('https://evil.example.com')

        self.assertNotIn('Access-Control-Allow-Origin', response.headers)

    def test_simple_request_from_allowed_origin(self):
        response = self.client.get('/api/health/', HTTP_ORIGIN='https://front.example.kz')

        self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'https://front.example.kz')

    def test_cors_only_for_api(self):
        response = self.preflight('https://front.example.kz', path='/admin/login/')

        self.assertNotIn('Access-Control-Allow-Origin', response.headers)

    @override_settings(CORS_ALLOWED_ORIGINS=[])
    def test_disabled_by_default(self):
        self.assertNotIn('Access-Control-Allow-Origin', self.preflight('https://front.example.kz').headers)


class RootRedirectTests(TestCase):
    def test_root_redirects_to_api_docs(self):
        response = self.client.get('/')

        self.assertRedirects(response, '/api/docs/', fetch_redirect_response=False)
