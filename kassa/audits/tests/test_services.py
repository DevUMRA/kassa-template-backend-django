from kassa.audits.services import inventory_start
from kassa.common.exceptions import AccessDeniedError, BusinessRuleError
from kassa.common.testing import ServiceTestCase, T
from kassa.documents.services import document_cancel, document_post


class InventoryServiceTests(ServiceTestCase):
    def setUp(self):
        self.warehouseman.warehouse = self.warehouse
        self.warehouseman.save()

    def test_start_records_expected_quantity_and_requires_counts(self):
        self.receive(100)
        audit = inventory_start(user=self.warehouseman, products=[self.product])

        item = audit.items.get()
        self.assertEqual(audit.number, f'INV-{audit.pk:06d}')
        self.assertEqual(item.expected_quantity, 100)
        self.assertFalse(item.is_counted)
        with self.assertRaisesMessage(BusinessRuleError, 'әлі саналмаған'):
            document_post(document=audit, user=self.manager)

    def test_cancel_of_posted_sale_is_blocked_during_inventory(self):
        self.receive(100)
        sale = document_post(document=self.make_doc(T.SALE, 10), user=self.seller)
        inventory_start(user=self.warehouseman, products=[self.product])

        with self.assertRaisesMessage(BusinessRuleError, 'түгендеуінде бұғатталған'):
            document_cancel(document=sale, user=self.manager, reason='Қате енгізілген')
        self.assertEqual(self.stock(), 90)

    def test_product_cannot_be_in_two_running_inventories(self):
        inventory_start(user=self.warehouseman, products=[self.product])

        with self.assertRaisesMessage(BusinessRuleError, 'түгендеуінде тұр'):
            inventory_start(user=self.warehouseman, products=[self.product, self.other_product])

    def test_seller_cannot_start_inventory(self):
        self.seller.warehouse = self.warehouse
        self.seller.save()

        with self.assertRaises(AccessDeniedError):
            inventory_start(user=self.seller, products=[self.product])
