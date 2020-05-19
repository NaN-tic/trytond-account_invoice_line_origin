# This file is part of the account_invoice_line_origin module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import doctest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker


class AccountInvoiceLineOriginTestCase(ModuleTestCase):
    'Test Account Invoice Line Origin module'
    module = 'account_invoice_line_origin'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountInvoiceLineOriginTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_account_invoice_line_origin.rst',
            tearDown=doctest_teardown, encoding='UTF-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
