from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.test import APITestCase

from kassa.audits.services import inventory_start
from kassa.common.exceptions import AccessDeniedError, BusinessRuleError
from kassa.common.testing import S, ServiceMixin, ServiceTestCase, T, create_fixtures
from kassa.documents.services import document_cancel, document_post
from kassa.inventory.models import Document, DocumentItem, StockMovement, User


class PostDocumentTests(ServiceTestCase):
    def test_receipt_increases_stock_and_writes_movement(self):
        document = self.receive(100)

        self.assertEqual(document.status, S.POSTED)
        self.assertIsNotNone(document.posted_at)
        self.assertEqual(self.stock(), 100)
        movement = StockMovement.objects.get(document=document)
        self.assertEqual(movement.quantity, 100)
        self.assertEqual(movement.doc_type, T.RECEIPT)
        self.assertEqual(movement.user, self.warehouseman)
        self.assertFalse(movement.is_reversal)

    def test_sale_decreases_stock(self):
        self.receive(100)
        document_post(document=self.make_doc(T.SALE, 10), user=self.seller)

        self.assertEqual(self.stock(), 90)

    def test_write_off_decreases_stock(self):
        self.receive(100)
        document_post(document=self.make_doc(T.WRITE_OFF, 2), user=self.warehouseman)

        self.assertEqual(self.stock(), 98)

    def test_repost_is_rejected(self):
        document = self.receive(100)

        with self.assertRaises(BusinessRuleError):
            document_post(document=document, user=self.warehouseman)
        self.assertEqual(self.stock(), 100)
        self.assertEqual(StockMovement.objects.filter(document=document).count(), 1)

    def test_insufficient_stock_is_rejected(self):
        self.receive(10)
        sale = self.make_doc(T.SALE, 15)

        with self.assertRaisesMessage(BusinessRuleError, 'Қалдық жеткіліксіз'):
            document_post(document=sale, user=self.seller)
        sale.refresh_from_db()
        self.assertEqual(sale.status, S.DRAFT)
        self.assertEqual(self.stock(), 10)

    def test_sale_without_any_stock_is_rejected(self):
        with self.assertRaisesMessage(BusinessRuleError, 'Қалдық жеткіліксіз'):
            document_post(document=self.make_doc(T.SALE, 1), user=self.seller)

    def test_empty_document_is_rejected(self):
        document = Document.objects.create(
            number='EMPTY',
            doc_type=T.RECEIPT,
            warehouse=self.warehouse,
            supplier=self.supplier,
            responsible=self.manager,
        )
        with self.assertRaisesMessage(BusinessRuleError, 'бірде-бір тауар жоқ'):
            document_post(document=document, user=self.manager)

    def test_receipt_requires_supplier(self):
        with self.assertRaisesMessage(BusinessRuleError, 'жеткізуші көрсетілуі тиіс'):
            document_post(document=self.make_doc(T.RECEIPT, 10), user=self.manager)

    def test_inactive_product_and_warehouse_are_rejected(self):
        self.product.is_active = False
        self.product.save()
        self.warehouse.is_active = False
        self.warehouse.save()

        with self.assertRaises(BusinessRuleError) as ctx:
            document_post(document=self.make_doc(T.RECEIPT, 10, supplier=self.supplier), user=self.manager)
        self.assertEqual(len(ctx.exception.messages), 2)

    def test_zero_quantity_is_rejected(self):
        with self.assertRaisesMessage(BusinessRuleError, 'нөлден үлкен'):
            document_post(document=self.make_doc(T.RECEIPT, 0, supplier=self.supplier), user=self.manager)


class RolePermissionTests(ServiceTestCase):
    def test_seller_cannot_post_receipt(self):
        with self.assertRaises(AccessDeniedError):
            document_post(document=self.make_doc(T.RECEIPT, 10, supplier=self.supplier), user=self.seller)

    def test_warehouseman_cannot_post_sale(self):
        self.receive(10)
        with self.assertRaises(AccessDeniedError):
            document_post(document=self.make_doc(T.SALE, 1), user=self.warehouseman)

    def test_only_manager_approves_inventory(self):
        for user in (self.seller, self.warehouseman):
            with self.assertRaises(AccessDeniedError):
                document_post(document=self.make_doc(T.INVENTORY, 5), user=user)

    def test_superuser_can_post_anything(self):
        admin = User.objects.create_superuser('admin', role=User.Role.SELLER)
        document_post(document=self.make_doc(T.RECEIPT, 10, supplier=self.supplier), user=admin)

        self.assertEqual(self.stock(), 10)


class InventoryTests(ServiceTestCase):
    def test_inventory_sets_stock_to_counted_quantity(self):
        self.receive(100)
        document = document_post(document=self.make_doc(T.INVENTORY, 97), user=self.manager)

        self.assertEqual(self.stock(), 97)
        self.assertEqual(StockMovement.objects.get(document=document).quantity, -3)

    def test_inventory_without_difference_writes_no_movement(self):
        self.receive(100)
        document = document_post(document=self.make_doc(T.INVENTORY, 100), user=self.manager)

        self.assertEqual(self.stock(), 100)
        self.assertFalse(StockMovement.objects.filter(document=document).exists())

    def test_draft_inventory_blocks_movements_of_its_products(self):
        self.receive(100)
        self.make_doc(T.INVENTORY, 97)

        with self.assertRaisesMessage(BusinessRuleError, 'түгендеуінде бұғатталған'):
            document_post(document=self.make_doc(T.SALE, 1), user=self.seller)

    def test_draft_inventory_does_not_block_other_products_or_warehouses(self):
        self.receive(10)
        self.receive(10, product=self.other_product)
        self.receive(10, warehouse=self.other_warehouse)
        self.make_doc(T.INVENTORY, 5)

        document_post(document=self.make_doc(T.SALE, 1, product=self.other_product), user=self.seller)
        document_post(document=self.make_doc(T.SALE, 1, warehouse=self.other_warehouse), user=self.seller)

        self.assertEqual(self.stock(self.other_product), 9)
        self.assertEqual(self.stock(warehouse=self.other_warehouse), 9)


class CancelDocumentTests(ServiceTestCase):
    def test_cancel_posted_writes_reversal_and_restores_stock(self):
        self.receive(100)
        sale = document_post(document=self.make_doc(T.SALE, 10), user=self.seller)

        document_cancel(document=sale, user=self.manager, reason='Қате енгізілген')

        sale.refresh_from_db()
        self.assertEqual(sale.status, S.CANCELED)
        self.assertIsNotNone(sale.canceled_at)
        self.assertEqual(self.stock(), 100)
        quantities = list(sale.movements.order_by('id').values_list('quantity', 'is_reversal'))
        self.assertEqual(quantities, [(Decimal(-10), False), (Decimal(10), True)])

    def test_cancel_draft_changes_only_status(self):
        sale = self.make_doc(T.SALE, 10, user=self.seller)

        document_cancel(document=sale, user=self.seller)

        sale.refresh_from_db()
        self.assertEqual(sale.status, S.CANCELED)
        self.assertFalse(sale.movements.exists())

    def test_cancel_twice_is_rejected(self):
        self.receive(100)
        sale = document_post(document=self.make_doc(T.SALE, 10), user=self.seller)
        document_cancel(document=sale, user=self.manager, reason='Қате енгізілген')

        with self.assertRaises(BusinessRuleError):
            document_cancel(document=sale, user=self.manager, reason='Қате енгізілген')
        self.assertEqual(self.stock(), 100)

    def test_only_manager_cancels_posted(self):
        self.receive(100)
        sale = document_post(document=self.make_doc(T.SALE, 10), user=self.seller)

        with self.assertRaises(AccessDeniedError):
            document_cancel(document=sale, user=self.seller)

    def test_cancel_that_would_make_stock_negative_is_rejected(self):
        receipt = self.receive(100)
        document_post(document=self.make_doc(T.SALE, 10), user=self.seller)

        with self.assertRaisesMessage(BusinessRuleError, 'Қалдық жеткіліксіз'):
            document_cancel(document=receipt, user=self.manager, reason='Қате енгізілген')
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, S.POSTED)
        self.assertEqual(self.stock(), 90)


class SaleReturnTests(ServiceTestCase):
    def setUp(self):
        self.receive(100)
        self.sale = document_post(document=self.make_doc(T.SALE, 5), user=self.seller)

    def sale_return(self, qty, base=None, **kwargs):
        return self.make_doc(T.SALE_RETURN, qty, base=base, **kwargs)

    def test_return_within_sold_quantity(self):
        document_post(document=self.sale_return(2, self.sale), user=self.seller)
        document_post(document=self.sale_return(3, self.sale), user=self.seller)

        self.assertEqual(self.stock(), 100)

    def test_return_requires_base_sale(self):
        with self.assertRaisesMessage(BusinessRuleError, 'негіз құжат'):
            document_post(document=self.sale_return(1), user=self.seller)

    def test_return_more_than_sold_is_rejected(self):
        document_post(document=self.sale_return(2, self.sale), user=self.seller)

        with self.assertRaisesMessage(BusinessRuleError, 'қайтаруға болатыны 3.000'):
            document_post(document=self.sale_return(4, self.sale), user=self.seller)
        self.assertEqual(self.stock(), 97)

    def test_canceled_returns_free_up_quantity(self):
        first = document_post(document=self.sale_return(5, self.sale), user=self.seller)
        document_cancel(document=first, user=self.manager, reason='Қате енгізілген')

        document_post(document=self.sale_return(5, self.sale), user=self.seller)

        self.assertEqual(self.stock(), 100)

    def test_return_from_canceled_sale_is_rejected(self):
        document_cancel(document=self.sale, user=self.manager, reason='Қате енгізілген')

        with self.assertRaisesMessage(BusinessRuleError, 'тек өткізілген құжаттан'):
            document_post(document=self.sale_return(1, self.sale), user=self.seller)

    def test_return_with_wrong_base_type_is_rejected(self):
        receipt = Document.objects.get(doc_type=T.RECEIPT)

        with self.assertRaisesMessage(BusinessRuleError, '«Сату» емес'):
            document_post(document=self.sale_return(1, receipt), user=self.seller)

    def test_return_to_other_warehouse_is_rejected(self):
        with self.assertRaisesMessage(BusinessRuleError, 'қоймасынан жасалуы тиіс'):
            document_post(document=self.sale_return(1, self.sale, warehouse=self.other_warehouse), user=self.seller)

    def test_return_of_product_not_in_sale_is_rejected(self):
        with self.assertRaisesMessage(BusinessRuleError, 'құжатында жоқ'):
            document_post(document=self.sale_return(1, self.sale, product=self.other_product), user=self.seller)

    def test_sale_with_posted_returns_cannot_be_canceled(self):
        document_post(document=self.sale_return(2, self.sale), user=self.seller)

        with self.assertRaisesMessage(BusinessRuleError, 'өткізілген қайтарулары бар'):
            document_cancel(document=self.sale, user=self.manager, reason='Қате енгізілген')

    def test_base_document_on_non_return_is_rejected(self):
        with self.assertRaisesMessage(BusinessRuleError, 'тек қайтару құжаттарында'):
            document_post(document=self.make_doc(T.SALE, 1, base=self.sale), user=self.seller)


class SupplierReturnTests(ServiceTestCase):
    def setUp(self):
        self.receipt = self.receive(100)

    def supplier_return(self, qty, base=None, supplier=None, **kwargs):
        return self.make_doc(T.SUPPLIER_RETURN, qty, base=base, supplier=supplier or self.supplier, **kwargs)

    def test_return_within_received_quantity(self):
        document_post(document=self.supplier_return(5, self.receipt), user=self.warehouseman)

        self.assertEqual(self.stock(), 95)

    def test_return_requires_base_receipt(self):
        with self.assertRaisesMessage(BusinessRuleError, 'негіз құжат'):
            document_post(document=self.supplier_return(1), user=self.warehouseman)

    def test_return_more_than_received_is_rejected(self):
        document_post(document=self.supplier_return(5, self.receipt), user=self.warehouseman)

        with self.assertRaisesMessage(BusinessRuleError, 'қайтаруға болатыны 95.000'):
            document_post(document=self.supplier_return(96, self.receipt), user=self.warehouseman)

    def test_return_to_other_supplier_is_rejected(self):
        with self.assertRaisesMessage(BusinessRuleError, 'жеткізушісіне («Серіктес ТОО»)'):
            document_post(
                document=self.supplier_return(1, self.receipt, supplier=self.other_supplier), user=self.warehouseman
            )

    def test_return_with_sale_as_base_is_rejected(self):
        sale = document_post(document=self.make_doc(T.SALE, 1), user=self.seller)

        with self.assertRaises(BusinessRuleError) as ctx:
            document_post(document=self.supplier_return(1, sale), user=self.warehouseman)
        self.assertEqual(ctx.exception.messages, [f'№{sale.number} құжаты «Жеткізушіден қабылдау» емес.'])

    def test_receipt_with_posted_returns_cannot_be_canceled(self):
        document_post(document=self.supplier_return(5, self.receipt), user=self.warehouseman)

        with self.assertRaisesMessage(BusinessRuleError, 'өткізілген қайтарулары бар'):
            document_cancel(document=self.receipt, user=self.manager, reason='Қате енгізілген')

    def test_return_limited_by_stock_too(self):
        document_post(document=self.make_doc(T.SALE, 98), user=self.seller)

        with self.assertRaisesMessage(BusinessRuleError, 'Қалдық жеткіліксіз'):
            document_post(document=self.supplier_return(5, self.receipt), user=self.warehouseman)


class CancelReasonTests(ServiceMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        create_fixtures(cls)
        for user in (cls.seller, cls.manager, cls.warehouseman):
            user.warehouse = cls.warehouse
            user.save()

    def test_posted_requires_reason(self):
        receipt = self.receive(10)

        for blank in ('', '   '):
            with self.subTest(reason=blank):
                with self.assertRaisesMessage(BusinessRuleError, 'себебі көрсетілуі тиіс'):
                    document_cancel(document=receipt, user=self.manager, reason=blank)
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, S.POSTED)
        self.assertEqual(self.stock(), 10)
        self.assertFalse(StockMovement.objects.filter(is_reversal=True).exists())

    def test_who_and_why_are_stored(self):
        receipt = self.receive(10)

        document_cancel(document=receipt, user=self.manager, reason='  Қате жеткізуші  ')

        receipt.refresh_from_db()
        self.assertEqual((receipt.canceled_by, receipt.cancel_reason), (self.manager, 'Қате жеткізуші'))
        self.assertIsNotNone(receipt.canceled_at)

    def test_permission_checked_before_reason(self):
        # Басқарушы емес қызметкерге «себеп жоқ» емес, «рұқсат жоқ» деп жауап беру керек
        receipt = self.receive(1)

        with self.assertRaises(AccessDeniedError):
            document_cancel(document=receipt, user=self.warehouseman)

    def test_draft_reason_is_optional(self):
        draft = self.make_doc(T.WRITE_OFF, 1)

        document_cancel(document=draft, user=self.warehouseman)

        draft.refresh_from_db()
        self.assertEqual((draft.status, draft.canceled_by, draft.cancel_reason), (S.CANCELED, self.warehouseman, ''))

    def test_inventory_cancel_api(self):
        self.receive(10)
        self.client.force_authenticate(self.manager)
        audit = inventory_start(user=self.manager, products=[self.product])
        DocumentItem.objects.filter(document=audit).update(quantity=8, is_counted=True)
        document_post(document=audit, user=self.manager)
        url = f'/api/inventory/audits/{audit.pk}/cancel/'

        self.assertEqual(self.client.post(url, format='json').status_code, 400)
        response = self.client.post(url, {'reason': 'Қайта санау керек'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            (response.data['status'], response.data['canceled_by'], response.data['cancel_reason']),
            (S.CANCELED, 'manager', 'Қайта санау керек'),
        )
        self.assertEqual(self.stock(), 10)
        movements = self.client.get('/api/reports/movements/', {'doc_type': T.INVENTORY}).data['results']
        reversal = next(m for m in movements if m['is_reversal'])
        self.assertEqual((reversal['cancel_reason'], reversal['user']), ('Қайта санау керек', 'manager'))
        self.assertEqual(next(m for m in movements if not m['is_reversal'])['cancel_reason'], '')

    def test_canceled_return_shows_in_sale(self):
        self.receive(10)
        self.client.force_authenticate(self.seller)
        sale = self.client.post(
            '/api/pos/sales/', {'items': [{'product_id': self.product.pk, 'quantity': '2'}]}, format='json'
        ).data
        sale_return = self.client.post(
            f'/api/pos/sales/{sale["id"]}/returns/',
            {
                'items': [{'product_id': self.product.pk, 'quantity': '1'}],
            },
            format='json',
        ).data
        document_cancel(
            document=Document.objects.get(pk=sale_return['id']), user=self.manager, reason='Клиент тауарды қайтып алды'
        )

        data = self.client.get(f'/api/pos/sales/{sale["id"]}/').data

        self.assertEqual(data['returns'][0]['canceled_by'], 'manager')
        self.assertEqual(data['returns'][0]['cancel_reason'], 'Клиент тауарды қайтып алды')
        self.assertIsNone(data['canceled_by'])
        self.assertEqual(data['returnable'], {str(self.product.pk): '2.000'})


class DocumentCommentTests(ServiceMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        create_fixtures(cls)
        for user in (cls.seller, cls.manager, cls.warehouseman):
            user.warehouse = cls.warehouse
            user.save()

    def setUp(self):
        self.receive(100)

    def test_write_off_without_reason_is_rejected(self):
        for blank in ('', '   '):
            with self.subTest(comment=blank):
                document = self.make_doc(T.WRITE_OFF, 2, comment=blank)

                with self.assertRaisesMessage(BusinessRuleError, 'себебі көрсетілуі тиіс'):
                    document_post(document=document, user=self.warehouseman)
                self.assertEqual(self.stock(), 100)

    def test_write_off_with_reason_is_posted(self):
        document = document_post(
            document=self.make_doc(T.WRITE_OFF, 2, comment='Мерзімі өткен'), user=self.warehouseman
        )

        self.assertEqual(document.status, S.POSTED)
        self.assertEqual(Document.objects.get(pk=document.pk).comment, 'Мерзімі өткен')
        self.assertEqual(self.stock(), 98)

    def test_other_documents_do_not_require_comment(self):
        document_post(document=self.make_doc(T.RECEIPT, 1, supplier=self.supplier, comment=''), user=self.warehouseman)

        self.assertEqual(self.stock(), 101)

    def test_model_clean_requires_write_off_reason(self):
        # Админ формасы model.full_clean() шақырады — қате comment өрісінің жанында шығады
        document = Document(number='X-1', doc_type=T.WRITE_OFF, warehouse=self.warehouse, responsible=self.manager)

        with self.assertRaises(DjangoValidationError) as ctx:
            document.full_clean()
        self.assertIn('comment', ctx.exception.message_dict)

    def test_sale_return_reason_via_api(self):
        self.client.force_authenticate(self.seller)
        sale = self.client.post(
            '/api/pos/sales/', {'items': [{'product_id': self.product.pk, 'quantity': '2'}]}, format='json'
        ).data

        response = self.client.post(
            f'/api/pos/sales/{sale["id"]}/returns/',
            {
                'items': [{'product_id': self.product.pk, 'quantity': '1'}],
                'comment': '  Ақаулы қақпақ  ',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['comment'], 'Ақаулы қақпақ')
        sale = self.client.get(f'/api/pos/sales/{sale["id"]}/').data
        self.assertEqual(sale['returns'][0]['comment'], 'Ақаулы қақпақ')

    def test_inventory_comment_on_start_and_approve(self):
        self.client.force_authenticate(self.warehouseman)
        audit = self.client.post(
            '/api/inventory/audits/',
            {
                'product_ids': [self.product.pk],
                'comment': 'Жоспарлы',
            },
            format='json',
        ).data
        self.assertEqual(audit['comment'], 'Жоспарлы')
        self.client.post(
            f'/api/inventory/audits/{audit["id"]}/counts/',
            {
                'items': [{'product_id': self.product.pk, 'quantity': '99'}],
            },
            format='json',
        )

        self.client.force_authenticate(self.manager)
        response = self.client.post(
            f'/api/inventory/audits/{audit["id"]}/approve/', {'comment': 'Бір дана ұрланған'}, format='json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['comment'], 'Бір дана ұрланған')
        report = self.client.get('/api/reports/inventory/').data
        self.assertEqual(report['audits'][0]['comment'], 'Бір дана ұрланған')
        movements = self.client.get('/api/reports/movements/', {'doc_type': T.INVENTORY}).data['results']
        self.assertEqual(movements[0]['comment'], 'Бір дана ұрланған')

    def test_approve_without_comment_keeps_start_comment(self):
        audit = inventory_start(user=self.warehouseman, products=[self.product], comment='Жоспарлы')
        DocumentItem.objects.filter(document=audit).update(quantity=100, is_counted=True)
        self.client.force_authenticate(self.manager)

        response = self.client.post(f'/api/inventory/audits/{audit.pk}/approve/', format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['comment'], 'Жоспарлы')

    def test_comment_too_long_is_rejected(self):
        self.client.force_authenticate(self.warehouseman)

        response = self.client.post(
            '/api/inventory/audits/',
            {
                'product_ids': [self.product.pk],
                'comment': 'x' * 501,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Document.objects.filter(doc_type=T.INVENTORY).exists())
