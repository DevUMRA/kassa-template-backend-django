from rest_framework.test import APITestCase

from kassa.common.testing import S, ServiceMixin, T, create_fixtures
from kassa.documents.services import document_post


class DocumentApiTests(ServiceMixin, APITestCase):
    URL = '/api/documents/'

    @classmethod
    def setUpTestData(cls):
        create_fixtures(cls)
        for user in (cls.seller, cls.manager, cls.warehouseman):
            user.warehouse = cls.warehouse
            user.save()

    def setUp(self):
        self.client.force_authenticate(self.manager)

    def cancel(self, document, reason=None):
        body = {} if reason is None else {'reason': reason}
        return self.client.post(f'{self.URL}{document.pk}/cancel/', body, format='json')

    def test_only_manager(self):
        receipt = self.receive(10)
        for user in (self.seller, self.warehouseman):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user)
                self.assertEqual(self.client.get(self.URL).status_code, 403)
                self.assertEqual(self.cancel(receipt, 'x').status_code, 403)
        self.assertEqual(self.stock(), 10)

    def test_journal_lists_all_types_with_filters(self):
        receipt = self.receive(10)
        sale = document_post(document=self.make_doc(T.SALE, 2), user=self.seller)
        document_post(document=self.make_doc(T.WRITE_OFF, 1), user=self.warehouseman)

        data = self.client.get(self.URL).data
        self.assertEqual(data['count'], 3)
        self.assertEqual({d['doc_type'] for d in data['results']}, {T.RECEIPT, T.SALE, T.WRITE_OFF})
        sales = self.client.get(self.URL, {'doc_type': T.SALE}).data['results']
        self.assertEqual([d['number'] for d in sales], [sale.number])
        self.assertEqual(self.client.get(self.URL, {'search': receipt.number}).data['count'], 1)
        self.assertEqual(self.client.get(self.URL, {'status': S.CANCELED}).data['count'], 0)
        self.assertEqual(
            self.client.get(self.URL, {'date_from': '2000-01-01', 'date_to': '2000-01-31'}).data['count'], 0
        )
        self.assertEqual(self.client.get(self.URL, {'doc_type': 'BAD'}).status_code, 400)
        self.assertEqual(
            self.client.get(self.URL, {'date_from': '2026-02-01', 'date_to': '2026-01-01'}).status_code, 400
        )

    def test_cancel_sale_restores_stock(self):
        self.receive(10)
        sale = document_post(document=self.make_doc(T.SALE, 3), user=self.seller)

        self.assertEqual(self.cancel(sale).status_code, 400)
        self.assertEqual(self.stock(), 7)
        response = self.cancel(sale, 'Кассир қате тауар соқты')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            (response.data['status'], response.data['canceled_by'], response.data['cancel_reason']),
            (S.CANCELED, 'manager', 'Кассир қате тауар соқты'),
        )
        self.assertEqual(self.stock(), 10)

    def test_cancel_draft_without_reason(self):
        draft = self.make_doc(T.RECEIPT, 5, supplier=self.supplier)

        response = self.cancel(draft)

        self.assertEqual((response.status_code, response.data['status']), (200, S.CANCELED))

    def test_cannot_cancel_base_with_posted_returns(self):
        receipt = self.receive(10)
        supplier_return = document_post(
            document=self.make_doc(T.SUPPLIER_RETURN, 2, supplier=self.supplier, base=receipt), user=self.warehouseman
        )

        response = self.cancel(receipt, 'Қате')

        self.assertEqual(response.status_code, 400)
        self.assertIn(supplier_return.number, ' '.join(response.data['detail']))
        detail = self.client.get(f'{self.URL}{receipt.pk}/').data
        self.assertEqual([r['number'] for r in detail['returns']], [supplier_return.number])
        # Алдымен қайтарудың, содан кейін қабылдаудың күшін жоюға болады
        self.assertEqual(self.cancel(supplier_return, 'Қате').status_code, 200)
        self.assertEqual(self.cancel(receipt, 'Қате').status_code, 200)
        self.assertEqual(self.stock(), 0)

    def test_cannot_cancel_receipt_if_goods_already_sold(self):
        receipt = self.receive(10)
        document_post(document=self.make_doc(T.SALE, 8), user=self.seller)

        response = self.cancel(receipt, 'Қате')

        self.assertEqual(response.status_code, 400)
        self.assertIn('Қалдық жеткіліксіз', ' '.join(response.data['detail']))
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, S.POSTED)
        self.assertEqual(self.stock(), 2)

    def test_detail_shows_base_document(self):
        receipt = self.receive(10)
        supplier_return = document_post(
            document=self.make_doc(T.SUPPLIER_RETURN, 2, supplier=self.supplier, base=receipt), user=self.warehouseman
        )

        data = self.client.get(f'{self.URL}{supplier_return.pk}/').data

        self.assertEqual(data['base_document']['number'], receipt.number)
        self.assertEqual((data['supplier'], data['doc_type_display']), ('Серіктес ТОО', 'Жеткізушіге қайтару'))
