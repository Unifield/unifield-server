# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import osv, fields

import logging
import functools


def check(fn):

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        if kwargs.get('context', args[-1]).get('log_sale_purchase'):
            return fn(self, *args, **kwargs)
        else:
            self._logger.warn(
                "Unable to call %s on model %s if "
                "log_sale_purchase is not set in the context!"
                % (fn.__name__, self._name) )
            return True

    return wrapper


class RunWithoutException(Exception):
    pass


class SyncException(Exception):
    def __init__(self, value, target_object, target_id, line_number=False, no_prod=False, line_vals=False):
        super(Exception, self).__init__(value)
        self.target_object = target_object
        self.target_id = target_id
        self.line_number = line_number
        self.no_prod = no_prod
        self.line_vals = line_vals


class log_sale_purchase(osv.osv):
    _name = 'sync.client.log_sale_purchase'
    _logger = logging.getLogger(_name)

    def _get_model_from_document(self, cr, uid, ids, field, args, context=None):
        return dict(
            (rec['id'], (rec['document'].split(',')[0]
                         if rec['document'] else ''))
            for rec in self.read(cr, uid, ids, ['document'], context=context) )

    def _get_model_id_from_document(self, cr, uid, ids, field, args, context=None):
        self.read(cr, uid, ids, ['model'], context=context)
        cr.execute("""
            SELECT log.id, m.id
            FROM %s log
            LEFT JOIN ir_model m
            ON log.model = m.model
            WHERE log.id IN %%s;""" % (self._table,), [tuple(ids)])  # not_a_user_entry
        return dict(cr.fetchall())

    @check
    def create(self, *a, **kw):
        return super(log_sale_purchase, self).create(*a, **kw)

    @check
    def write(self, *a, **kw):
        return super(log_sale_purchase, self).write(*a, **kw)

    # UF-2239: Sort the list by synchronisation id
    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False, count=False):
        if not orderby:
            orderby = 'synchro_datetime desc'
        return super(log_sale_purchase, self).read_group(cr, uid, domain, fields, groupby, offset, limit, context, orderby, count=count)

    _columns = {
        # Synchronization
        'synchro_id' :
            fields.many2one('sync.monitor', "Synchronization",
                            ondelete='cascade', readonly=True),
        'synchro_datetime' :
            fields.related('synchro_id', 'start', type='datetime', store=True,
                           string="Synchronization Date/Time", readonly=True),

        # Document
        'document' :
            fields.reference("Document", selection=[
                ('sale.order','Sale Order'),
                ('purchase.order','Field Order'),
                ('stock.picking','Picking'),
                ('shipment','Shipment'),
            ], size=128, required=True, readonly=True),
        'model' :
            fields.function(_get_model_from_document, method=True,
                            string="Model", type='char', size=64,
                            store=True, readonly=True),
        'model_id' :
            fields.function(_get_model_id_from_document, method=True,
                            string="Model", type='many2one', relation='ir.model',
                            store=True, readonly=True),

        # Log information
        'action_type' :
            fields.selection([
                ('creation','Created'),
                ('modification','Modified'),
            ], string="Action", required=True, readonly=True),
        'action_datetime' :
            fields.datetime("Log Date/Time", readonly=True),

        # Log content
        'is_status_modified' :
            fields.boolean("Status changed", readonly=True),
        'is_product_added' :
            fields.boolean("Products added", readonly=True),
        'is_product_removed' :
            fields.boolean("Products removed", readonly=True),
        'is_quantity_modified' :
            fields.boolean("Quantity changed", readonly=True),
        'is_product_price_modified' :
            fields.boolean("Product price changed", readonly=True),
        'is_date_modified' :
            fields.boolean("Date changed", readonly=True),
    }

    _defaults = {
        'action_datetime' : fields.datetime.now,
    }

    _order = "synchro_id desc"


log_sale_purchase()


class SalePurchaseLogger(object):
    def __init__(self, cr, uid, model, res_id, context=None):
        self._cr = cr
        self._uid = uid
        self._model = model.pool.get(log_sale_purchase._name)
        self._values = {
            'document' : "%s,%d" % (model._name, res_id),
            'action_type' : 'modification',
        }
        self._id = None
        self._context = dict(context or {})

    def __getattr__(self, symbol):
        if not symbol.startswith('_') \
           and symbol in list(self._model._all_columns.keys()):
            return self._values.get(symbol,
                                    (False if symbol.startswith('is_') else None))
        return self.__dict__[symbol]

    def write(self):
        if self._id is not None:
            self._model.write(self._cr, self._uid, [self._id],
                              self._values, context=self._context)
        else:
            self._id = self._model.create(self._cr, self._uid,
                                          self._values, context=self._context)
            if 'logger' in self._context:
                self._context['logger'].link(
                    self._model._name, 'synchro_id', self._id)

    def __setattr__(self, symbol, value):
        if not symbol.startswith('_') \
           and symbol in list(self._model._all_columns.keys()):
            if getattr(self, symbol) != value:
                self._values[symbol] = value
                self.write()
        else:
            self.__dict__[symbol] = value

    def delete(self):
        if self._id is not None:
            if 'logger' in self._context:
                self._context['logger'].unlink(
                    self._model._name, 'synchro_id', self._id)
            self._model.unlink(self._cr, self._uid, [self._id])
            self._id = None


def get_sale_purchase_logger(cr, uid, model, res_id, context=None):
    assert context is not None, \
        "The context must be defined to call this method!"
    assert 'sale_purchase_logger' in context, \
        "sale_purchase_logger must be initialzed in the context " \
        "in order to call this method"
    return context['sale_purchase_logger']\
        .setdefault(model._name, {})\
        .setdefault(res_id,
                    SalePurchaseLogger(cr, uid, model, res_id, context=context))
