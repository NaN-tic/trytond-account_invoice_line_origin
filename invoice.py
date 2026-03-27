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


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'
    origin_number = fields.Function(fields.Char('Origin Number'),
        'get_origin_reference', searcher='search_origin_reference')
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

    def _get_origin_reference_origin(self):
        origin = self.origin
        if not (origin and isinstance(origin, Model)):
            return
        if origin.__name__ == 'stock.move':
            origin = origin.origin if isinstance(origin.origin, Model) else None
        return origin

    def get_origin_reference(self, name):
        origin = self._get_origin_reference_origin()
        if origin:
            parent = self.origin_reference_models().get(origin.__name__)
            if not parent:
                return

            source = getattr(origin, parent, None)
            if not source:
                return

            if name.endswith('number'):
                return source.number if hasattr(source, 'number') else None
            elif name.endswith('reference'):
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
                return parent_date if parent_date else None

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
        try:
            StockMove = pool.get('stock.move')
        except:
            StockMove = None

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
        if StockMove:
            stock_move = StockMove.__table__()

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
        elif name.endswith('number'):
            sql_where = (Operator(invoice.number, value))
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
        if StockMove:
            query = query.join(stock_move, 'LEFT', condition=(
                    (Cast(Substring(invoice_line.origin,
                                Position(',', invoice_line.origin)
                        + Literal(1)), 'INTEGER') == stock_move.id)
                    &
                    (Like(invoice_line.origin, 'stock.move,%'))
                    ))

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
            elif name.endswith('number'):
                sql_where = (sql_where
                    | (Operator(sale.number, value))
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

        if (StockMove and Sale
                and (invoice_type == 'out' or invoice_type == 'both')):
            sale_line_move = SaleLine.__table__()
            sale_move = Sale.__table__()
            query = query.join(sale_line_move, 'LEFT', condition=(
                    (Cast(Substring(stock_move.origin,
                                Position(',', stock_move.origin)
                        + Literal(1)), 'INTEGER') == sale_line_move.id)
                    &
                    (Like(stock_move.origin, 'sale.line,%'))
                    ))
            query = query.join(sale_move, 'LEFT', condition=(
                    sale_line_move.sale == sale_move.id
                    ))

            if name.endswith('date'):
                sql_where = (sql_where
                    | (Operator(sale_move.sale_date, value))
                    )
            elif name.endswith('number'):
                sql_where = (sql_where
                    | (Operator(sale_move.number, value))
                    )
            else:
                if PYSQL_CONDITION == 'and':
                    sql_where = (sql_where
                        | (Operator(sale_move.reference, value))
                        | (Operator(sale_move.number, value))
                        )
                else:
                    sql_where = (sql_where
                        | (Operator(sale_move.reference, value))
                        & (Operator(sale_move.number, value))
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
            elif name.endswith('number'):
                sql_where = (sql_where
                    | (Operator(purchase.number, value))
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
        if (StockMove and Purchase
                and (invoice_type == 'in' or invoice_type == 'both')):
            purchase_line_move = PurchaseLine.__table__()
            purchase_move = Purchase.__table__()
            query = query.join(purchase_line_move, 'LEFT', condition=(
                    (Cast(Substring(stock_move.origin,
                                Position(',', stock_move.origin)
                        + Literal(1)), 'INTEGER') == purchase_line_move.id)
                    &
                    (Like(stock_move.origin, 'purchase.line,%'))
                    ))
            query = query.join(purchase_move, 'LEFT', condition=(
                    purchase_line_move.purchase == purchase_move.id
                    ))

            if name.endswith('date'):
                sql_where = (sql_where
                    | (Operator(purchase_move.purchase_date, value))
                    )
            elif name.endswith('number'):
                sql_where = (sql_where
                    | (Operator(purchase_move.number, value))
                    )
            else:
                if PYSQL_CONDITION == 'and':
                    sql_where = (sql_where
                        | (Operator(purchase_move.reference, value))
                        | (Operator(purchase_move.number, value))
                        )
                else:
                    sql_where = (sql_where
                        | (Operator(purchase_move.reference, value))
                        & (Operator(purchase_move.number, value))
                        )
        query = query.select(invoice_line.id, where=sql_where)

        return [('id', 'in', query)]

    def get_origin_shipment(self, name):
        locale = Transaction().context.get('locale')
        format = locale.get('date', '%Y-%m-%d') if locale else '%Y-%m-%d'

        shipments = set()
        for move in self.stock_moves:
            if move.shipment:
                if move.shipment.effective_date and move.shipment.reference:
                    key = '%s - %s - %s' % (move.shipment.rec_name,
                        move.shipment.effective_date.strftime(format),
                        move.shipment.reference)
                elif (move.shipment.effective_date and
                        not move.shipment.reference):
                    key = '%s - %s' % (move.shipment.rec_name,
                        move.shipment.effective_date.strftime(format))
                elif (not move.shipment.effective_date and
                        move.shipment.reference):
                    key = '%s - %s ' % (move.shipment.rec_name,
                        move.shipment.reference)
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
                | Operator(shipment_in_return.number, value)
                | Operator(shipment_out.reference, value)
                | Operator(shipment_out_return.reference, value)
                | Operator(shipment_in.reference, value)
                | Operator(shipment_in_return.reference, value))

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
