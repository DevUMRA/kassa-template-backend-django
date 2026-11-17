from decimal import Decimal

from django.urls import reverse

from kassa.common.testing import S, ServiceTestCase, T
from kassa.inventory.models import Document, User


class DocumentAdminActionTests(ServiceTestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin')
        self.client.force_login(self.admin)
        self.url = reverse('admin:inventory_document_changelist')

    def run_action(self, action, *documents):
        return self.client.post(
            self.url, {'action': action, '_selected_action': [d.pk for d in documents]}, follow=True
        )

    def test_post_action_posts_valid_and_reports_invalid(self):
        receipt = self.make_doc(T.RECEIPT, 10, supplier=self.supplier)
        oversell = self.make_doc(T.SALE, 50)

        response = self.run_action('post_documents', receipt, oversell)

        receipt.refresh_from_db()
        oversell.refresh_from_db()
        self.assertEqual(receipt.status, S.POSTED)
        self.assertEqual(oversell.status, S.DRAFT)
        self.assertEqual(self.stock(), 10)
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('өткізілді' in m for m in messages))
        self.assertTrue(any('Қалдық жеткіліксіз' in m for m in messages))

    def test_cancel_action_asks_reason_then_reverses(self):
        receipt = self.receive(10)

        # 1-қадам: аралық бет — әлі ештеңе өзгермейді
        page = self.run_action('cancel_documents', receipt)
        self.assertTemplateUsed(page, 'admin/inventory/document/cancel_confirmation.html')
        self.assertContains(page, receipt.number)
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, S.POSTED)

        # Себепсіз растау — форма қатесі, құжат өзгермейді
        empty = self.client.post(
            self.url,
            {
                'action': 'cancel_documents',
                '_selected_action': [receipt.pk],
                'apply': '1',
                'reason': '',
            },
        )
        self.assertTrue(empty.context['form'].errors)
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, S.POSTED)

        # 2-қадам: себеппен растау
        self.client.post(
            self.url,
            {
                'action': 'cancel_documents',
                '_selected_action': [receipt.pk],
                'apply': '1',
                'reason': 'Қате жеткізуші',
            },
            follow=True,
        )

        receipt.refresh_from_db()
        self.assertEqual(
            (receipt.status, receipt.canceled_by, receipt.cancel_reason), (S.CANCELED, self.admin, 'Қате жеткізуші')
        )
        self.assertEqual(self.stock(), 0)

    def test_cancel_action_reason_optional_for_drafts(self):
        draft = self.make_doc(T.RECEIPT, 10, supplier=self.supplier)

        self.client.post(
            self.url,
            {
                'action': 'cancel_documents',
                '_selected_action': [draft.pk],
                'apply': '1',
                'reason': '',
            },
            follow=True,
        )

        draft.refresh_from_db()
        self.assertEqual((draft.status, draft.canceled_by), (S.CANCELED, self.admin))


class AdminRoleTests(ServiceTestCase):
    """Админдегі рөлдік шектеулер (CLAUDE.md RBAC). Барлық қызметкерде is_staff бар."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        for user in (cls.manager, cls.warehouseman, cls.seller):
            user.is_staff = True
            user.warehouse = cls.warehouse
            user.save()

    def login(self, user):
        self.client.force_login(user)

    def url(self, model, action='changelist', *args):
        return reverse(f'admin:inventory_{model}_{action}', args=args)

    def status(self, model, action='changelist', *args):
        return self.client.get(self.url(model, action, *args)).status_code

    def admin_receipt_data(self, doc_type=T.RECEIPT, warehouse=None, **extra):
        return {
            'number': 'ADM-1',
            'doc_type': doc_type,
            'warehouse': (warehouse or self.warehouse).pk,
            'supplier': self.supplier.pk,
            'responsible': self.manager.pk,
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-product': self.product.pk,
            'items-0-quantity': '10',
            'items-0-price': '100',
            **extra,
        }

    def test_index_shows_only_allowed_models(self):
        expected = {
            self.manager: {
                'Тауарлар',
                'Жеткізушілер',
                'Қоймалар',
                'Құжаттар',
                'Қалдықтар',
                'Қызметкерлер',
                'Тауар қозғалыстары',
                'Құжат жолдары',
            },
            self.warehouseman: {
                'Тауарлар',
                'Жеткізушілер',
                'Қоймалар',
                'Құжаттар',
                'Қалдықтар',
                'Тауар қозғалыстары',
                'Құжат жолдары',
            },
            self.seller: {'Тауарлар', 'Құжаттар', 'Қалдықтар'},
        }
        for user, models in expected.items():
            with self.subTest(role=user.role):
                self.login(user)
                app_list = self.client.get(reverse('admin:index')).context['app_list']
                self.assertEqual({m['name'] for app in app_list for m in app['models']}, models)

    def test_only_manager_edits_directories(self):
        for user in (self.warehouseman, self.seller):
            with self.subTest(role=user.role):
                self.login(user)
                self.assertEqual(self.status('product', 'add'), 403)
                response = self.client.post(
                    self.url('product', 'change', self.product.pk),
                    {'name': 'Hacked', 'sku': 'WATER-05', 'unit': 'PCS', 'sale_price': '1'},
                )
                self.assertEqual(response.status_code, 403)
        self.product.refresh_from_db()
        self.assertEqual(self.product.sale_price, Decimal('150'))

        self.login(self.manager)
        self.assertEqual(self.status('product', 'add'), 200)
        self.assertEqual(self.status('supplier', 'add'), 200)

    def test_only_superuser_edits_staff(self):
        self.login(self.manager)
        self.assertEqual(self.status('user'), 200)
        self.assertEqual(self.status('user', 'add'), 403)
        response = self.client.post(self.url('user', 'change', self.manager.pk), {'is_superuser': 'on'})
        self.assertEqual(response.status_code, 403)
        self.manager.refresh_from_db()
        self.assertFalse(self.manager.is_superuser)

        self.login(self.warehouseman)
        self.assertEqual(self.status('user'), 403)

    def test_warehouseman_creates_receipt_in_own_warehouse_as_responsible(self):
        self.login(self.warehouseman)

        response = self.client.post(self.url('document', 'add'), self.admin_receipt_data())

        self.assertEqual(response.status_code, 302)
        document = Document.objects.get(number='ADM-1')
        self.assertEqual(
            (document.status, document.warehouse, document.responsible), (S.DRAFT, self.warehouse, self.warehouseman)
        )
        self.assertEqual(document.items.get().quantity, 10)

    def test_warehouseman_cannot_create_sale_or_use_other_warehouse(self):
        self.login(self.warehouseman)
        for data in (
            self.admin_receipt_data(doc_type=T.SALE),
            self.admin_receipt_data(doc_type=T.INVENTORY),
            self.admin_receipt_data(warehouse=self.other_warehouse),
        ):
            with self.subTest(doc_type=data['doc_type'], warehouse=data['warehouse']):
                response = self.client.post(self.url('document', 'add'), data)
                self.assertEqual(response.status_code, 200)  # форма қатемен қайта көрсетіледі
                self.assertTrue(response.context['adminform'].form.errors)
        self.assertFalse(Document.objects.filter(number='ADM-1').exists())

    def test_warehouseman_sees_only_own_warehouse_documents(self):
        own = self.make_doc(T.RECEIPT, 1, supplier=self.supplier)
        foreign = self.make_doc(T.RECEIPT, 1, supplier=self.supplier, warehouse=self.other_warehouse)
        self.login(self.warehouseman)

        listed = list(self.client.get(self.url('document')).context['cl'].queryset)

        self.assertEqual(listed, [own])
        self.assertEqual(self.status('document', 'change', foreign.pk), 302)  # «табылмады» → индекске

    def test_posted_document_is_read_only_and_not_deletable(self):
        receipt = self.receive(10)
        self.login(self.manager)

        response = self.client.get(self.url('document', 'change', receipt.pk))

        self.assertFalse(response.context['has_change_permission'])
        self.assertEqual(self.status('document', 'delete', receipt.pk), 403)

    def test_warehouseman_cannot_edit_sale_draft_and_has_no_cancel_action(self):
        sale = self.make_doc(T.SALE, 1)
        self.login(self.warehouseman)

        response = self.client.get(self.url('document', 'change', sale.pk))
        actions = [
            name for name, _ in self.client.get(self.url('document')).context['action_form'].fields['action'].choices
        ]

        self.assertFalse(response.context['has_change_permission'])
        self.assertIn('post_documents', actions)
        self.assertNotIn('cancel_documents', actions)

    def test_seller_only_views_own_sales(self):
        sale = self.make_doc(T.SALE, 1)
        self.make_doc(T.RECEIPT, 1, supplier=self.supplier)
        self.login(self.seller)

        listed = list(self.client.get(self.url('document')).context['cl'].queryset)

        self.assertEqual(listed, [sale])
        self.assertEqual(self.status('document', 'add'), 403)
        self.assertFalse(self.client.get(self.url('document', 'change', sale.pk)).context['has_change_permission'])
        self.assertEqual(self.client.get(self.url('document')).context['action_form'], None)

    def test_stock_and_movements_scoped_and_read_only(self):
        self.receive(10)
        self.receive(5, warehouse=self.other_warehouse)

        self.login(self.seller)
        self.assertEqual([s.quantity for s in self.client.get(self.url('stock')).context['cl'].queryset], [10])
        self.assertEqual(self.status('stockmovement'), 403)

        self.login(self.warehouseman)
        self.assertEqual(self.client.get(self.url('stockmovement')).context['cl'].result_count, 1)

        self.login(self.manager)
        self.assertEqual(self.client.get(self.url('stock')).context['cl'].result_count, 2)
        self.assertEqual(self.status('stock', 'add'), 403)
