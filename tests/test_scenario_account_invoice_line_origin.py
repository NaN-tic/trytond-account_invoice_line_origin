import datetime
import unittest
from decimal import Decimal

from proteus import Model
from trytond.modules.account.tests.tools import (create_chart,
                                                 create_fiscalyear,
                                                 get_accounts)
from trytond.modules.account_invoice.tests.tools import (
    create_payment_term, set_fiscalyear_invoice_sequences)
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Imports

        # Install account_invoice_line_origin, purchase_invoice_line_standalone
        activate_modules([
            'account_invoice_line_origin', 'purchase_invoice_line_standalone',
            'sale'
        ])

        # Create company
        _ = create_company()
        company = get_company()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']
        expense = accounts['expense']

        # Create parties
        Party = Model.get('party.party')
        supplier = Party(name='Supplier')
        supplier.save()
        customer = Party(name='Customer')
        customer.save()

        # Create account category
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name="Account Category")
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.save()

        # Create product
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'goods'
        template.purchasable = True
        template.salable = True
        template.list_price = Decimal('10')
        template.cost_price_method = 'fixed'
        template.account_category = account_category
        product, = template.products
        product.cost_price = Decimal('5')
        template.save()
        product, = template.products

        # Create payment term
        payment_term = create_payment_term()
        payment_term.save()

        # Compute dates
        today = datetime.date.today()
        tomorrow = today + datetime.timedelta(days=1)
        yesterday = today - datetime.timedelta(days=1)

        # Purchases
        Purchase = Model.get('purchase.purchase')
        PurchaseLine = Model.get('purchase.line')
        purchase = Purchase()
        purchase.party = supplier
        purchase.payment_term = payment_term
        purchase.invoice_method = 'order'
        purchase_line = PurchaseLine()
        purchase.lines.append(purchase_line)
        purchase_line.product = product
        purchase_line.quantity = 2.0
        purchase_line = PurchaseLine()
        purchase.lines.append(purchase_line)
        purchase_line.product = product
        purchase_line.quantity = 3.0
        purchase_line = PurchaseLine()
        purchase.lines.append(purchase_line)
        purchase_line.product = product
        purchase_line.quantity = 4.0
        purchase.click('quote')
        purchase.click('confirm')
        purchase.click('process')
        self.assertEqual(purchase.state, 'processing')
        purchase.reload()
        self.assertEqual(purchase.shipment_state, 'waiting')
        self.assertEqual(purchase.invoice_state, 'pending')
        self.assertEqual(len(purchase.moves), 3)

        self.assertEqual(len(purchase.shipment_returns), 0)

        self.assertEqual(len(purchase.invoices), 1)

        self.assertEqual(len(purchase.invoice_lines), 3)
        purchase2, = Purchase.duplicate([purchase])
        purchase2.purchase_date = tomorrow
        purchase2.save()
        purchase2.click('quote')
        purchase2.click('confirm')
        purchase2.click('process')
        self.assertEqual(purchase2.state, 'processing')
        purchase3, = Purchase.duplicate([purchase])
        purchase3.purchase_date = yesterday
        purchase3.save()
        purchase3.click('quote')
        purchase3.click('confirm')
        purchase3.click('process')
        self.assertEqual(purchase3.state, 'processing')

        # Create shipment:
        Move = Model.get('stock.move')
        ShipmentIn = Model.get('stock.shipment.in')
        shipment = ShipmentIn()
        shipment.supplier = supplier
        for move in purchase.moves[:-1]:

            incoming_move = Move(id=move.id)

            shipment.incoming_moves.append(incoming_move)
        shipment.save()
        shipment.click('receive')
        shipment.click('done')
        shipment2 = ShipmentIn()
        shipment2.supplier = supplier
        for move in purchase2.moves[:-2]:

            incoming_move = Move(id=move.id)

            shipment2.incoming_moves.append(incoming_move)
        shipment2.save()
        shipment2.click('receive')
        shipment2.click('done')

        # Sales
        Sale = Model.get('sale.sale')
        SaleLine = Model.get('sale.line')
        sale = Sale()
        sale.party = customer
        sale.payment_term = payment_term
        sale.invoice_method = 'order'
        sale_line = SaleLine()
        sale.lines.append(sale_line)
        sale_line.product = product
        sale_line.quantity = 2.0
        sale_line = SaleLine()
        sale.lines.append(sale_line)
        sale_line.product = product
        sale_line.quantity = 3.0
        sale_line = SaleLine()
        sale.lines.append(sale_line)
        sale_line.product = product
        sale_line.quantity = 4.0
        sale.click('quote')
        sale.click('confirm')
        sale.click('process')
        self.assertEqual(sale.state, 'processing')
        sale.reload()
        self.assertEqual(len(sale.invoices), 1)
        self.assertEqual(len(sale.invoices), 1)
        sale2, = Sale.duplicate([sale])
        sale2.reference = 'ABC'
        sale2.sale_date = tomorrow
        sale2.save()
        sale2.click('quote')
        sale2.click('confirm')
        sale2.click('process')
        self.assertEqual(sale2.state, 'processing')
        sale3, = Sale.duplicate([sale])
        sale3.sale_date = yesterday
        sale3.save()
        sale3.click('quote')
        sale3.click('confirm')
        sale3.click('process')
        self.assertEqual(sale3.state, 'processing')

        # Search invoice lines
        Line = Model.get('account.invoice.line')
        self.assertEqual(len(Line.find()), 18)
        self.assertEqual(len(Line.find([('origin_number', '=', '2')])), 6)
        self.assertEqual(len(Line.find([('origin_number', '=', 'ABC')])), 0)
        self.assertEqual(len(Line.find([('origin_reference', '=', '2')])), 6)
        self.assertEqual(len(Line.find([('origin_reference', '=', 'ABC')])), 3)
        self.assertEqual(
            len(
                set([
                    l.origin.__class__
                    for l in Line.find([('origin_reference', '=', '2')])
                ])), 2)
        self.assertEqual(len(Line.find([('origin_date', '=', yesterday)])), 6)
        self.assertEqual(len(Line.find([('origin_date', '>=', today)])), 12)
        self.assertEqual(len(Line.find([('origin_shipment', '!=', '1')])), 7)
        self.assertEqual(len(Line.find([('origin_shipment', '=', '2')])), 4)
        self.assertEqual(len(Line.find([('origin_shipment', '!=', '2')])), 8)
        self.assertEqual(
            len(
                Line.find([('origin_shipment', '=', today.strftime('%m/%d/%Y'))
                           ])), 9)
