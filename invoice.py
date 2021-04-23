#This file is part account_invoice_line_origin module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from datetime import datetime
from trytond.model import fields, Model
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from sql import Cast, Literal, operators
from sql.functions import Substring, Position
from sql.operators import Like

__all__ = ['InvoiceLine']


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'
    origin_reference = fields.Function(fields.Char('Origin Reference'),
        'get_origin_reference', searcher='search_origin_reference')
    origin_date = fields.Function(fields.Date('Origin Date'),
        'get_origin_reference', searcher='search_origin_reference')
    # origin_shipment/date fields in __setup__ method

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        if hasattr(cls, 'stock_moves'):
            cls.origin_shipment = fields.Function(fields.Char('Shipment'),
                'get_origin_shipment', searcher='search_origin_shipment')

    @classmethod
    def origin_reference_models(cls):
        return {
            'account.invoice.line': 'invoice',
            'purchase.line': 'purchase',
            'sale.line': 'sale',
            }

    def get_origin_reference(self, name):
        if self.origin and isinstance(self.origin, Model):
            origin = self.origin
            parent = self.origin_reference_models().get(origin.__name__)
            if not parent:
                return

            source = getattr(origin, parent, None)
            if not source:
                return

            if name.endswith('reference'):
                if (hasattr(source, 'number')
                        and hasattr(source, 'reference')):
                    references = []
                    if source.number:
                        references.append(source.number)
                    if source.reference:
                        references.append(source.reference)
                    reference = ' / '.join(references)
                elif hasattr(source, 'reference'):
                    reference = source.reference
                else:
                    reference = source.rec_name
                return reference
            elif name.endswith('date'):
                parent_date = getattr(source, parent+'_date', None)
                if parent_date:
                    return parent_date

    @classmethod
    def search_origin_reference(cls, name, clause):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        try:
            SaleLine = pool.get('sale.line')
            Sale = pool.get('sale.sale')
        except:
            Sale = None
        try:
            PurchaseLine = pool.get('purchase.line')
            Purchase = pool.get('purchase.purchase')
        except:
            Purchase = None

        invoice_type = Transaction().context.get('invoice_type', 'both')

        invoice_line = cls.__table__()
        invoice_line2 = cls.__table__()
        invoice = Invoice.__table__()

        if Sale:
            sale_line = SaleLine.__table__()
            sale = Sale.__table__()
        if Purchase:
            purchase_line = PurchaseLine.__table__()
            purchase = Purchase.__table__()

        field, operator_, value = clause

        if operator_ == '!=':
            PYSQL_CONDITION = 'not'
        elif operator_ == '=':
            PYSQL_CONDITION = 'and'
        elif operator_ == 'not ilike':
            PYSQL_CONDITION = 'not'
        else:
            PYSQL_CONDITION = 'and'

        Operator = fields.SQL_OPERATORS[operator_]

        if name.endswith('date'):
            sql_where = (Operator(invoice.invoice_date, value))
        else:
            sql_where = (Operator(invoice.reference, value))

        query = (invoice_line
            .join(invoice_line2, 'LEFT', condition=(
                    (Cast(Substring(invoice_line.origin,
                                Position(',', invoice_line.origin)
                        + Literal(1)), 'INTEGER') == invoice_line2.id)
                    &
                    (Like(invoice_line.origin, 'account.invoice.line,%'))
                    ))
            .join(invoice, 'LEFT', condition=(
                    invoice_line2.invoice == invoice.id
                    )))

        # sales
        if Sale and (invoice_type == 'out' or invoice_type == 'both'):
            query = query.join(sale_line, 'LEFT', condition=(
                    (Cast(Substring(invoice_line.origin,
                                Position(',', invoice_line.origin)
                        + Literal(1)), 'INTEGER') == sale_line.id)
                    &
                    (Like(invoice_line.origin, 'sale.line,%'))
                    ))
            query = query.join(sale, 'LEFT', condition=(
                    sale_line.sale == sale.id
                    ))

            if name.endswith('date'):
                sql_where = (sql_where
                    | (Operator(sale.sale_date, value))
                    )
            else:
                if PYSQL_CONDITION == 'and':
                    sql_where = (sql_where
                        | (Operator(sale.reference, value))
                        | (Operator(sale.number, value))
                        )
                else:
                    sql_where = (sql_where
                        | (Operator(sale.reference, value))
                        & (Operator(sale.number, value))
                        )

        # purchase
        if Purchase and (invoice_type == 'in' or invoice_type == 'both'):
            query = query.join(purchase_line, 'LEFT', condition=(
                    (Cast(Substring(invoice_line.origin,
                                Position(',', invoice_line.origin)
                        + Literal(1)), 'INTEGER') == purchase_line.id)
                    &
                    (Like(invoice_line.origin, 'purchase.line,%'))
                    ))
            query = query.join(purchase, 'LEFT', condition=(
                    purchase_line.purchase == purchase.id
                    ))

            if name.endswith('date'):
                sql_where = (sql_where
                    | (Operator(purchase.purchase_date, value))
                    )
            else:
                if PYSQL_CONDITION == 'and':
                    sql_where = (sql_where
                        | (Operator(purchase.reference, value))
                        | (Operator(purchase.number, value))
                        )
                else:
                    sql_where = (sql_where
                        | (Operator(purchase.reference, value))
                        & (Operator(purchase.number, value))
                        )
        query = query.select(invoice_line.id, where=sql_where)

        return [('id', 'in', query)]

    def get_origin_shipment(self, name):
        locale = Transaction().context.get('locale')
        format = locale.get('date', '%Y-%m-%d') if locale else '%Y-%m-%d'

        shipments = set()
        for move in self.stock_moves:
            if move.shipment:
                if move.shipment.effective_date:
                    key = '%s - %s' % (move.shipment.rec_name,
                        move.shipment.effective_date.strftime(format))
                else:
                    key = '%s' % move.shipment.rec_name
                shipments.add(key)

        return ', '.join(shipments)

    @classmethod
    def search_origin_shipment(cls, name, clause):
        pool = Pool()
        LineMove = pool.get('account.invoice.line-stock.move')
        Move = pool.get('stock.move')
        ShipmentOut = pool.get('stock.shipment.out')
        ShipmentOutReturn = pool.get('stock.shipment.out.return')
        ShipmentIn = pool.get('stock.shipment.in')
        ShipmentInReturn = pool.get('stock.shipment.in.return')

        invoice_line = cls.__table__()
        line_move = LineMove.__table__()
        move = Move.__table__()
        shipment_out = ShipmentOut.__table__()
        shipment_out_return = ShipmentOutReturn.__table__()
        shipment_in = ShipmentIn.__table__()
        shipment_in_return = ShipmentInReturn.__table__()

        field, operator_, value = clause

        Operator = fields.SQL_OPERATORS[operator_]

        try:
            locale = Transaction().context.get('locale')
            format_date = (locale.get('date', '%Y-%m-%d')
                if locale else '%Y-%m-%d')
            value_date = (datetime.strptime(value.replace('%', ''),
                    format_date).strftime('%Y-%m-%d') if value else None)
        except ValueError:
            value_date = None

        if value_date:
            if Operator in (operators.Like, operators.ILike):
                Operator = operators.Equal
            elif Operator in (operators.NotLike, operators.NotILike):
                Operator = operators.NotEqual

            sql_where = (Operator(shipment_out.effective_date, value_date)
                | Operator(shipment_out_return.effective_date, value_date)
                | Operator(shipment_in.effective_date, value_date)
                | Operator(shipment_in_return.effective_date, value_date))
        else:
            sql_where = (Operator(shipment_out.number, value)
                | Operator(shipment_out_return.number, value)
                | Operator(shipment_in.number, value)
                | Operator(shipment_in_return.number, value))

        query = invoice_line.join(line_move,
            condition=invoice_line.id == line_move.invoice_line).join(
            move, condition=move.id == line_move.stock_move)
        query = query.join(shipment_out, 'LEFT',
            condition=Cast(Substring(move.shipment, Position(
            ',', move.shipment) + Literal(1)), 'INTEGER') == shipment_out.id)
        query = query.join(shipment_out_return, 'LEFT',
            condition=Cast(Substring(move.shipment, Position(
            ',', move.shipment) + Literal(1)), 'INTEGER') == shipment_out_return.id)
        query = query.join(shipment_in, 'LEFT',
            condition=Cast(Substring(move.shipment, Position(
            ',', move.shipment) + Literal(1)), 'INTEGER') == shipment_in.id)
        query = query.join(shipment_in_return, 'LEFT',
            condition=Cast(Substring(move.shipment, Position(
            ',', move.shipment) + Literal(1)), 'INTEGER') == shipment_in_return.id)
        query = query.select(invoice_line.id, where=sql_where)

        return [('id', 'in', query)]
