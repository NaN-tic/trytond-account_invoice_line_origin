#This file is part account_invoice_line_origin module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.

try:
    from trytond.modules.party.tests.test_account_invoice_line_origin import suite
except ImportError:
    from .test_account_invoice_line_origin import suite

__all__ = ['suite']
