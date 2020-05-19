#This file is part account_invoice_line_origin module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from trytond.pool import Pool
from . import invoice


def register():
    Pool.register(
        invoice.InvoiceLine,
        module='account_invoice_line_origin', type_='model')
