from kassa.audits.services import inventory_start
from kassa.common.testing import ConcurrencyTestCase, S, T
from kassa.documents.services import document_cancel, document_post
from kassa.inventory.models import Document, DocumentItem, Stock, StockMovement


class ConcurrencyTests(ConcurrencyTestCase):
    def test_parallel_sales_never_oversell(self):
        self.receive(10)
        sales = [self.make_doc(T.SALE, 3, user=self.seller) for _ in range(self.THREADS)]

        succeeded, errors = self.run_parallel([lambda d=d: document_post(document=d, user=self.seller) for d in sales])

        self.assertEqual(len(succeeded), 3)
        self.assertEqual(len(errors), self.THREADS - 3)
        self.assertEqual(self.stock(), 1)
        self.assertEqual(StockMovement.objects.filter(doc_type=T.SALE).count(), 3)
        self.assertEqual(Document.objects.filter(doc_type=T.SALE, status=S.POSTED).count(), 3)

    def test_same_document_posted_in_parallel_only_once(self):
        receipt = self.make_doc(T.RECEIPT, 10, supplier=self.supplier)

        succeeded, errors = self.run_parallel(
            [lambda: document_post(document=receipt, user=self.warehouseman)] * self.THREADS
        )

        self.assertEqual(len(succeeded), 1)
        self.assertEqual(len(errors), self.THREADS - 1)
        self.assertEqual(self.stock(), 10)
        self.assertEqual(StockMovement.objects.filter(document=receipt).count(), 1)

    def test_same_document_canceled_in_parallel_only_once(self):
        receipt = self.receive(10)

        succeeded, errors = self.run_parallel(
            [lambda: document_cancel(document=receipt, user=self.manager, reason='Қате енгізілген')] * self.THREADS
        )

        self.assertEqual(len(succeeded), 1)
        self.assertEqual(self.stock(), 0)
        self.assertEqual(StockMovement.objects.filter(document=receipt, is_reversal=True).count(), 1)

    def test_parallel_returns_never_exceed_sold_quantity(self):
        self.receive(100)
        sale = document_post(document=self.make_doc(T.SALE, 5), user=self.seller)
        returns = [self.make_doc(T.SALE_RETURN, 2, base=sale) for _ in range(self.THREADS)]

        succeeded, errors = self.run_parallel(
            [lambda d=d: document_post(document=d, user=self.seller) for d in returns]
        )

        self.assertEqual(len(succeeded), 2)
        self.assertEqual(self.stock(), 99)

    def test_parallel_first_receipts_create_single_stock_row(self):
        receipts = [self.make_doc(T.RECEIPT, 5, supplier=self.supplier) for _ in range(self.THREADS)]

        succeeded, errors = self.run_parallel(
            [lambda d=d: document_post(document=d, user=self.warehouseman) for d in receipts]
        )

        self.assertEqual(len(succeeded), self.THREADS)
        self.assertEqual(Stock.objects.filter(product=self.product, warehouse=self.warehouse).count(), 1)
        self.assertEqual(self.stock(), 5 * self.THREADS)

    def test_opposite_item_order_does_not_deadlock(self):
        self.receive(1000)
        self.receive(1000, product=self.other_product)
        sales = []
        for i in range(self.THREADS * 2):
            # Жартысында тауарлар A→B ретімен, жартысында B→A — бұғаттау реті сұрыпталмаса, deadlock болар еді
            first, second = (self.product, self.other_product) if i % 2 else (self.other_product, self.product)
            sale = self.make_doc(T.SALE, 1, product=first)
            DocumentItem.objects.create(document=sale, product=second, quantity=1, price=100)
            sales.append(sale)

        succeeded, errors = self.run_parallel([lambda d=d: document_post(document=d, user=self.seller) for d in sales])

        self.assertEqual(len(succeeded), len(sales))
        self.assertEqual(self.stock(), 1000 - len(sales))
        self.assertEqual(self.stock(self.other_product), 1000 - len(sales))


class InventoryConcurrencyTests(ConcurrencyTestCase):
    """Түгендеу басталған сәтте қатар өтіп жатқан сатулар есептік қалдықты бұзбауы тиіс."""

    def test_sales_racing_with_inventory_start_never_change_snapshot(self):
        self.warehouseman.warehouse = self.warehouse
        self.warehouseman.save()
        self.receive(1000)
        sales = [self.make_doc(T.SALE, 1, user=self.seller) for _ in range(self.THREADS * 2)]
        calls = [lambda d=d: document_post(document=d, user=self.seller) for d in sales]
        calls.insert(len(calls) // 2, lambda: inventory_start(user=self.warehouseman, products=[self.product]))

        self.run_parallel(calls)

        # Түгендеу басталғаннан кейін өткен әр сату қалдықты есептік мәннен өзгертер еді
        audit = Document.objects.get(doc_type=T.INVENTORY)
        self.assertEqual(self.stock(), audit.items.get().expected_quantity)
        sold = Document.objects.filter(doc_type=T.SALE, status=S.POSTED).count()
        self.assertEqual(self.stock(), 1000 - sold)
