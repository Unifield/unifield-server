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

from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
from operator import itemgetter
from itertools import groupby

from osv import fields, osv
from tools.translate import _
import netsvc
import tools
import decimal_precision as dp
import logging
from osv.orm import browse_record

#----------------------------------------------------------
# Incoterms
#----------------------------------------------------------
class stock_incoterms(osv.osv):
    _name = "stock.incoterms"
    _description = "Incoterms"
    _columns = {
        'name': fields.char('Name', size=64, required=True, help="Incoterms are series of sales terms.They are used to divide transaction costs and responsibilities between buyer and seller and reflect state-of-the-art transportation practices."),
        'code': fields.char('Code', size=3, required=True, help="Code for Incoterms"),
        'active': fields.boolean('Active', help="By unchecking the active field, you may hide an INCOTERM without deleting it."),
    }
    _defaults = {
        'active': True,
    }

stock_incoterms()

class stock_journal(osv.osv):
    _name = "stock.journal"
    _description = "Stock Journal"
    _columns = {
        'name': fields.char('Stock Journal', size=32, required=True),
        'user_id': fields.many2one('res.users', 'Responsible'),
    }
    _defaults = {
        'user_id': lambda s, c, u, ctx: u
    }

stock_journal()

#----------------------------------------------------------
# Stock Location
#----------------------------------------------------------
class stock_location(osv.osv):
    _name = "stock.location"
    _description = "Location"
    _parent_name = "location_id"
    _parent_store = True
    _parent_order = 'posz,name'
    _order = 'parent_left'

    def name_get(self, cr, uid, ids, context=None):
        res = []
        if context is None:
            context = {}
        if not len(ids):
            return []
        reads = self.read(cr, uid, ids, ['name','location_id'], context=context)
        for record in reads:
            name = record['name']
            if context.get('full',False):
                if record['location_id']:
                    name = record['location_id'][1] + ' / ' + name
                res.append((record['id'], name))
            else:
                res.append((record['id'], name))
        return res

    def _complete_name(self, cr, uid, ids, name, args, context=None):
        """ Forms complete name of location from parent location to child location.
        @return: Dictionary of values
        """
        def _get_one_full_name(location, level=4):
            if location.location_id:
                parent_path = _get_one_full_name(location.location_id, level-1) + "/"
            else:
                parent_path = ''
            return parent_path + location.name
        res = {}
        for m in self.browse(cr, uid, ids, context=context):
            res[m.id] = _get_one_full_name(m)
        return res


    def _product_value(self, cr, uid, ids, field_names, arg, context=None):
        """Computes stock value (real and virtual) for a product, as well as stock qty (real and virtual).
        @param field_names: Name of field
        @return: Dictionary of values
        """
        prod_id = context and context.get('product_id', False)

        product_product_obj = self.pool.get('product.product')

        cr.execute('select distinct product_id, location_id from stock_move where location_id in %s', (tuple(ids), ))
        dict1 = cr.dictfetchall()
        cr.execute('select distinct product_id, location_dest_id as location_id from stock_move where location_dest_id in %s', (tuple(ids), ))
        dict2 = cr.dictfetchall()
        res_products_by_location = sorted(dict1+dict2, key=itemgetter('location_id'))
        products_by_location = dict((k, [v['product_id'] for v in itr]) for k, itr in groupby(res_products_by_location, itemgetter('location_id')))

        result = dict([(i, {}.fromkeys(field_names, 0.0)) for i in ids])
        result.update(dict([(i, {}.fromkeys(field_names, 0.0)) for i in list(set([aaa['location_id'] for aaa in res_products_by_location]))]))

        currency_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
        currency_obj = self.pool.get('res.currency')
        currency = currency_obj.browse(cr, uid, currency_id, context=context)
        for loc_id, product_ids in products_by_location.items():
            if prod_id:
                product_ids = [prod_id]
            c = (context or {}).copy()
            c['location'] = loc_id
            for prod in product_product_obj.read(cr, uid, product_ids,
                                                 ['qty_available',
                                                  'virtual_available',
                                                  'standard_price',], context=c):
                for f in field_names:
                    if f == 'stock_real':
                        if loc_id not in result:
                            result[loc_id] = {}
                        result[loc_id][f] += prod['qty_available']
                    elif f == 'stock_virtual':
                        result[loc_id][f] += prod['virtual_available']
                    elif f == 'stock_real_value':
                        amount = prod['qty_available'] * prod['standard_price']
                        amount = currency_obj.round(cr, uid, currency.rounding, amount)
                        result[loc_id][f] += amount
                    elif f == 'stock_virtual_value':
                        amount = prod['virtual_available'] * prod['standard_price']
                        amount = currency_obj.round(cr, uid, currency.rounding, amount)
                        result[loc_id][f] += amount
        return result

    _columns = {
        'name': fields.char('Location Name', size=64, required=True, translate=True),
        'active': fields.boolean('Active', help="By unchecking the active field, you may hide a location without deleting it."),
        'usage': fields.selection([('supplier', 'Supplier Location'), ('view', 'View'), ('internal', 'Internal Location'), ('customer', 'Customer Location'), ('inventory', 'Inventory'), ('procurement', 'Procurement'), ('production', 'Production'), ('transit', 'Transit Location for Inter-Companies Transfers')], 'Location Type', required=True,
                                  help="""* Supplier Location: Virtual location representing the source location for products coming from your suppliers
                       \n* View: Virtual location used to create a hierarchical structures for your warehouse, aggregating its child locations ; can't directly contain products
                       \n* Internal Location: Physical locations inside your own warehouses,
                       \n* Customer Location: Virtual location representing the destination location for products sent to your customers
                       \n* Inventory: Virtual location serving as counterpart for inventory operations used to correct stock levels (Physical inventories)
                       \n* Procurement: Virtual location serving as temporary counterpart for procurement operations when the source (supplier or production) is not known yet. This location should be empty when the procurement scheduler has finished running.
                       \n* Production: Virtual counterpart location for production operations: this location consumes the raw material and produces finished products
                      """, select = True),
        # temporarily removed, as it's unused: 'allocation_method': fields.selection([('fifo', 'FIFO'), ('lifo', 'LIFO'), ('nearest', 'Nearest')], 'Allocation Method', required=True),
        'complete_name': fields.function(_complete_name, method=True, type='char', size=100, string="Location Name"),

        'stock_real': fields.function(_product_value, method=True, type='float', string='Real Stock', multi="stock"),
        'stock_virtual': fields.function(_product_value, method=True, type='float', string='Virtual Stock', multi="stock"),

        'location_id': fields.many2one('stock.location', 'Parent Location', select=True, ondelete='cascade'),
        'child_ids': fields.one2many('stock.location', 'location_id', 'Contains'),

        'chained_journal_id': fields.many2one('stock.journal', 'Chaining Journal',help="Inventory Journal in which the chained move will be written, if the Chaining Type is not Transparent (no journal is used if left empty)"),
        'chained_location_id': fields.many2one('stock.location', 'Chained Location If Fixed'),
        'chained_location_type': fields.selection([('none', 'None'), ('customer', 'Customer'), ('fixed', 'Fixed Location')],
                                                  'Chained Location Type', required=True,
                                                  help="Determines whether this location is chained to another location, i.e. any incoming product in this location \n" \
                                                  "should next go to the chained location. The chained location is determined according to the type :"\
                                                  "\n* None: No chaining at all"\
                                                  "\n* Customer: The chained location will be taken from the Customer Location field on the Partner form of the Partner that is specified in the Picking list of the incoming products." \
                                                  "\n* Fixed Location: The chained location is taken from the next field: Chained Location if Fixed." \
                                                  ),
        'chained_auto_packing': fields.selection(
            [('auto', 'Automatic Move'), ('manual', 'Manual Operation'), ('transparent', 'Automatic No Step Added')],
            'Chaining Type',
            required=True,
            help="This is used only if you select a chained location type.\n" \
            "The 'Automatic Move' value will create a stock move after the current one that will be "\
            "validated automatically. With 'Manual Operation', the stock move has to be validated "\
            "by a worker. With 'Automatic No Step Added', the location is replaced in the original move."
        ),
        'chained_picking_type': fields.selection([('out', 'Sending Goods'), ('in', 'Getting Goods'), ('internal', 'Internal')], 'Shipping Type', help="Shipping Type of the Picking List that will contain the chained move (leave empty to automatically detect the type based on the source and destination locations)."),
        'chained_company_id': fields.many2one('res.company', 'Chained Company', help='The company the Picking List containing the chained move will belong to (leave empty to use the default company determination rules'),
        'chained_delay': fields.integer('Chaining Lead Time',help="Delay between original move and chained move in days"),
        'address_id': fields.many2one('res.partner.address', 'Location Address',help="Address of  customer or supplier."),
        'icon': fields.selection(tools.icons, 'Icon', size=64,help="Icon show in  hierarchical tree view"),

        'comment': fields.text('Additional Information'),
        'posx': fields.integer('Corridor (X)',help="Optional localization details, for information purpose only"),
        'posy': fields.integer('Shelves (Y)', help="Optional localization details, for information purpose only"),
        'posz': fields.integer('Height (Z)', help="Optional localization details, for information purpose only"),

        'parent_left': fields.integer('Left Parent', select=1),
        'parent_right': fields.integer('Right Parent', select=1),
        'stock_real_value': fields.function(_product_value, method=True, type='float', string='Real Stock Value', multi="stock", digits_compute=dp.get_precision('Account')),
        'stock_virtual_value': fields.function(_product_value, method=True, type='float', string='Virtual Stock Value', multi="stock", digits_compute=dp.get_precision('Account')),
        'company_id': fields.many2one('res.company', 'Company', select=1, help='Let this field empty if this location is shared between all companies'),
        'scrap_location': fields.boolean('Scrap Location', help='Check this box to allow using this location to put scrapped/damaged goods.'),
        'valuation_in_account_id': fields.many2one('account.account', 'Stock Input Account',domain = [('type','=','other')], help='This account will be used to value stock moves that have this location as destination, instead of the stock output account from the product.'),
        'valuation_out_account_id': fields.many2one('account.account', 'Stock Output Account',domain = [('type','=','other')], help='This account will be used to value stock moves that have this location as source, instead of the stock input account from the product.'),
    }
    _defaults = {
        'active': True,
        'usage': 'internal',
        'chained_location_type': 'none',
        'chained_auto_packing': 'manual',
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.location', context=c),
        'posx': 0,
        'posy': 0,
        'posz': 0,
        'icon': False,
        'scrap_location': False,
    }

    def _hook_chained_location_get(self, cr, uid, context={}, *args, **kwargs):
        return kwargs.get('result', None)

    def picking_type_get(self, cr, uid, from_location, to_location, context=None):
        """ Gets type of picking.
        @param from_location: Source location
        @param to_location: Destination location
        @return: Location type
        """
        result = 'internal'
        if (from_location.usage=='internal') and (to_location and to_location.usage in ('customer', 'supplier')):
            result = 'out'
        elif (from_location.usage in ('supplier', 'customer')) and (to_location.usage in ('internal', 'inventory')):
            result = 'in'
        return result

    def _product_get_all_report(self, cr, uid, ids, product_ids=False, context=None):
        return self._product_get_report(cr, uid, ids, product_ids, context, recursive=True)

    def _product_get_report(self, cr, uid, ids, product_ids=False,
                            context=None, recursive=False):
        """ Finds the product quantity and price for particular location.
        @param product_ids: Ids of product
        @param recursive: True or False
        @return: Dictionary of values
        """
        if context is None:
            context = {}
        product_obj = self.pool.get('product.product')
        # Take the user company and pricetype
        context['currency_id'] = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id

        # To be able to offer recursive or non-recursive reports we need to prevent recursive quantities by default
        context['compute_child'] = False

        if not product_ids:
            product_ids = product_obj.search(cr, uid, [], context={'active_test': False})

        products = product_obj.browse(cr, uid, product_ids, context=context)
        products_by_uom = {}
        products_by_id = {}
        for product in products:
            products_by_uom.setdefault(product.uom_id.id, [])
            products_by_uom[product.uom_id.id].append(product)
            products_by_id.setdefault(product.id, [])
            products_by_id[product.id] = product

        result = {}
        result['product'] = []
        for id in ids:
            quantity_total = 0.0
            total_price = 0.0
            for uom_id in products_by_uom.keys():
                fnc = self._product_get
                if recursive:
                    fnc = self._product_all_get
                ctx = context.copy()
                ctx['uom'] = uom_id
                qty = fnc(cr, uid, id, [x.id for x in products_by_uom[uom_id]],
                          context=ctx)
                for product_id in qty.keys():
                    if not qty[product_id]:
                        continue
                    product = products_by_id[product_id]
                    quantity_total += qty[product_id]

                    # Compute based on pricetype
                    # Choose the right filed standard_price to read
                    amount_unit = product.price_get('standard_price', context)[product.id]
                    price = qty[product_id] * amount_unit

                    total_price += price
                    result['product'].append({
                        'price': amount_unit,
                        'prod_name': product.name,
                        'code': product.default_code, # used by lot_overview_all report!
                        'variants': product.variants or '',
                        'uom': product.uom_id.name,
                        'prod_qty': qty[product_id],
                        'price_value': price,
                    })
        result['total'] = quantity_total
        result['total_price'] = total_price
        return result

    def _product_get_multi_location(self, cr, uid, ids, product_ids=False, context=None,
                                    states=['done'], what=('in', 'out')):
        """
        @param product_ids: Ids of product
        @param states: List of states
        @param what: Tuple of
        @return:
        """
        product_obj = self.pool.get('product.product')
        if context is None:
            context = {}
        context.update({
            'states': states,
            'what': what,
            'location': ids
        })
        return product_obj.get_product_available(cr, uid, product_ids, context=context)

    def _product_get(self, cr, uid, id, product_ids=False, context=None, states=['done']):
        """
        @param product_ids:
        @param states:
        @return:
        """
        ids = id and [id] or []
        return self._product_get_multi_location(cr, uid, ids, product_ids, context=context, states=states)

    def _product_all_get(self, cr, uid, id, product_ids=False, context=None, states=['done']):
        # build the list of ids of children of the location given by id
        ids = id and [id] or []
        location_ids = self.search(cr, uid, [('location_id', 'child_of', ids)],
                                   order='NO_ORDER')
        return self._product_get_multi_location(cr, uid, location_ids, product_ids, context, states)

    def _product_virtual_get(self, cr, uid, id, product_ids=False, context=None, states=['confirmed', 'waiting', 'assigned', 'done']):
        return self._product_all_get(cr, uid, id, product_ids, context, states=states)

    def _product_reserve(self, cr, uid, ids, product_id, product_qty, location_dest_id, context=None, lock=False):
        """
        Attempt to find a quantity ``product_qty`` (in the product's default uom or the uom passed in ``context``) of product ``product_id``
        in locations with id ``ids`` and their child locations. If ``lock`` is True, the stock.move lines
        of product with id ``product_id`` in the searched location will be write-locked using Postgres's
        "FOR UPDATE NOWAIT" option until the transaction is committed or rolled back, to prevent reservin
        twice the same products.
        If ``lock`` is True and the lock cannot be obtained (because another transaction has locked some of
        the same stock.move lines), a log line will be output and False will be returned, as if there was
        not enough stock.

        :param product_id: Id of product to reserve
        :param product_qty: Quantity of product to reserve (in the product's default uom or the uom passed in ``context``)
        :param lock: if True, the stock.move lines of product with id ``product_id`` in all locations (and children locations) with ``ids`` will
                     be write-locked using postgres's "FOR UPDATE NOWAIT" option until the transaction is committed or rolled back. This is
                     to prevent reserving twice the same products.
        :param context: optional context dictionary: it a 'uom' key is present it will be used instead of the default product uom to
                        compute the ``product_qty`` and in the return value.
        :return: List of tuples in the form (qty, location_id) with the (partial) quantities that can be taken in each location to
                 reach the requested product_qty (``qty`` is expressed in the default uom of the product), of False if enough
                 products could not be found, or the lock could not be obtained (and ``lock`` was True).
        """
        amount = 0.0
        if context is None:
            context = {}
        pool_uom = self.pool.get('product.uom')

        temp = self.search(cr, uid, [('location_id', 'child_of', ids)], order="parent_left")
        if location_dest_id in temp:
            temp.remove(location_dest_id)
            temp.append(location_dest_id)

        result_qty = []
        for id in temp:
            if lock:
                try:
                    # Must lock with a separate select query because FOR UPDATE can't be used with
                    # aggregation/group by's (when individual rows aren't identifiable).
                    # We use a SAVEPOINT to be able to rollback this part of the transaction without
                    # failing the whole transaction in case the LOCK cannot be acquired.
                    cr.execute("SAVEPOINT stock_location_product_reserve")
                    cr.execute("""SELECT id FROM stock_move
                                  WHERE product_id=%s AND
                                          (
                                            (location_dest_id=%s AND
                                             location_id<>%s AND
                                             state='done')
                                            OR
                                            (location_id=%s AND
                                             location_dest_id<>%s AND
                                             state in ('done', 'assigned'))
                                          )
                                  FOR UPDATE of stock_move NOWAIT""", (product_id, id, id, id, id), log_exceptions=False)
                except Exception:
                    # Here it's likely that the FOR UPDATE NOWAIT failed to get the LOCK,
                    # so we ROLLBACK to the SAVEPOINT to restore the transaction to its earlier
                    # state, we return False as if the products were not available, and log it:
                    cr.execute("ROLLBACK TO stock_location_product_reserve")
                    logger = logging.getLogger('stock.location')
                    logger.warn("Failed attempt to reserve %s x product %s, likely due to another transaction already in progress. Next attempt is likely to work. Detailed error available at DEBUG level.", product_qty, product_id)
                    logger.debug("Trace of the failed product reservation attempt: ", exc_info=True)
                    return False

            # XXX TODO: rewrite this with one single query, possibly even the quantity conversion
            cr.execute("""SELECT product_uom, sum(product_qty) AS product_qty
                          FROM stock_move
                          WHERE location_dest_id=%s AND
                                location_id<>%s AND
                                product_id=%s AND
                                state='done' AND (expired_date is null or expired_date >= CURRENT_DATE)
                          GROUP BY product_uom
                       """,
                       (id, id, product_id))
            results = cr.dictfetchall()
            cr.execute("""SELECT product_uom,-sum(product_qty) AS product_qty
                          FROM stock_move
                          WHERE location_id=%s AND
                                location_dest_id<>%s AND
                                product_id=%s AND
                                state in ('done', 'assigned')
                                AND (expired_date is null or expired_date >= CURRENT_DATE)
                          GROUP BY product_uom
                       """,
                       (id, id, product_id))
            results += cr.dictfetchall()
            total_loc = 0.0

            for r in results:
                amount = pool_uom._compute_qty(cr, uid, r['product_uom'], r['product_qty'], context.get('uom', False))
                total_loc += amount

            if total_loc <= 0.0:
                continue

            if product_qty <= total_loc:
                result_qty.append((product_qty, id))
                return result_qty

            result_qty.append((total_loc, id))
            product_qty -= total_loc

        if not result_qty:
            # zero available stock
            return []

        if product_qty:
            # remaining not available qty
            result_qty.append((product_qty, False))

        return result_qty



stock_location()


class stock_tracking(osv.osv):
    _name = "stock.tracking"
    _description = "Packs"

    def checksum(sscc):
        salt = '31' * 8 + '3'
        sum = 0
        for sscc_part, salt_part in zip(sscc, salt):
            sum += int(sscc_part) * int(salt_part)
        return (10 - (sum % 10)) % 10
    checksum = staticmethod(checksum)

    def make_sscc(self, cr, uid, context=None):
        sequence = self.pool.get('ir.sequence').get(cr, uid, 'stock.lot.tracking')
        try:
            return sequence + str(self.checksum(sequence))
        except Exception:
            return sequence

    _columns = {
        'name': fields.char('Pack Reference', size=64, required=True, select=True),
        'active': fields.boolean('Active', help="By unchecking the active field, you may hide a pack without deleting it."),
        'serial': fields.char('Additional Reference', size=64, select=True, help="Other reference or serial number"),
        'move_ids': fields.one2many('stock.move', 'tracking_id', 'Moves for this pack', readonly=True),
        'date': fields.datetime('Creation Date', required=True),
    }
    _defaults = {
        'active': 1,
        'name': make_sscc,
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        ids = self.search(cr, user, [('serial', '=', name)]+ args, limit=limit,
                          order='NO_ORDER', context=context)
        ids += self.search(cr, user, [('name', operator, name)]+ args,
                           limit=limit, order='NO_ORDER', context=context)
        return self.name_get(cr, user, ids, context)

    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        res = [(r['id'], r['name']+' ['+(r['serial'] or '')+']') for r in self.read(cr, uid, ids, ['name', 'serial'], context)]
        return res

    def unlink(self, cr, uid, ids, context=None):
        raise osv.except_osv(_('Error'), _('You can not remove a lot line !'))

    def action_traceability(self, cr, uid, ids, context={}):
        """ It traces the information of a product
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: List of IDs selected
        @param context: A standard dictionary
        @return: A dictionary of values
        """
        value = {}
        value = self.pool.get('action.traceability').action_traceability(cr,uid,ids,context)
        return value
stock_tracking()

#----------------------------------------------------------
# Stock Picking
#----------------------------------------------------------
class stock_picking(osv.osv):
    _name = "stock.picking"
    _description = "Picking List"

    def _set_maximum_date(self, cr, uid, ids, name, value, arg, context=None):
        """ Calculates planned date if it is greater than 'value'.
        @param name: Name of field
        @param value: Value of field
        @param arg: User defined argument
        @return: True or False
        """
        if not value:
            return False
        if isinstance(ids, (int, long)):
            ids = [ids]
        for pick in self.read(cr, uid, ids,['max_date'], context=context):
            sql_str = """update stock_move set
                    date=%s
                where
                    picking_id=%s"""
            sql_params = (value, pick['id'])
            if pick['max_date']:
                sql_str += " and (date=%s or date>%s)"
                sql_params.extend((pick['max_date'], value))
            cr.execute(sql_str, sql_params)
        return True

    def _set_minimum_date(self, cr, uid, ids, name, value, arg, context=None):
        """ Calculates planned date if it is less than 'value'.
        @param name: Name of field
        @param value: Value of field
        @param arg: User defined argument
        @return: True or False
        """
        if not value:
            return False
        if isinstance(ids, (int, long)):
            ids = [ids]
        for pick in self.read(cr, uid, ids, ['min_date'], context=context):
            sql_str = """update stock_move set
                    date=%s
                where
                    picking_id=%s"""
            sql_params = (value, pick['id'])
            if pick['min_date']:
                sql_str += " and (date=%s or date<%s)"
                sql_params.extend((pick['min_date'], value))
            cr.execute(sql_str, sql_params)
        return True

    def get_min_max_date(self, cr, uid, ids, field_name, arg, context=None):
        """ Finds minimum and maximum dates for picking.
        @return: Dictionary of values
        """
        res = {}
        for id in ids:
            res[id] = {'min_date': False, 'max_date': False}
        if not ids:
            return res
        cr.execute("""select
                picking_id,
                min(date_expected),
                max(date_expected)
            from
                stock_move
            where
                picking_id IN %s
            group by
                picking_id""",(tuple(ids),))
        for pick, dt1, dt2 in cr.fetchall():
            res[pick]['min_date'] = dt1
            res[pick]['max_date'] = dt2
        return res

    def create(self, cr, user, vals, context=None):
        if vals.get('type', False) and vals['type'] == 'in' \
                and not vals.get('from_wkf', False) and not vals.get('from_wkf_sourcing', False):
            reason_type = self.pool.get('stock.reason.type').browse(cr, user, vals.get('reason_type_id', False), context=context)
            if reason_type and reason_type.name == 'Damage':
                raise osv.except_osv(_('Error'), _('You can not create an Incoming Shipment from scratch with %s reason type')
                                     % (reason_type.name,))
        if 'type' in vals and (('name' not in vals) or (vals.get('name')=='/')):
            seq_obj_name =  'stock.picking.' + vals['type']
            vals['name'] = self.pool.get('ir.sequence').get(cr, user, seq_obj_name)
        new_id = super(stock_picking, self).create(cr, user, vals, context)
        return new_id


    def _get_location_dest_active_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns True if there is draft moves on Picking Ticket
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        res = {}
        for pick in self.browse(cr, uid, ids, fields_to_fetch=['move_lines'], context=context):
            res[pick.id] = True
            for int_move in self.pool.get('stock.move').browse(cr, uid, [x.id for x in pick.move_lines], fields_to_fetch=['location_dest_id'], context=context):
                if not int_move.location_dest_id.active:
                    res[pick.id] = False
                    break

        return res

    def _get_object_name(self, cr, uid, ids, field_name, args, context=None):
        # TODO: update stock_picking set is_subpick = 't' where subtype='picking' and name like '%-%';
        ret = {}
        for pick in self.read(cr, uid, ids, ['is_subpick', 'subtype'], context=context):
            if pick['subtype'] == 'picking':
                if pick['is_subpick']:
                    ret[pick['id']] = _('Picking Ticket')
                else:
                    ret[pick['id']] = _('Picking List')
            else:
                ret[pick['id']] = False
        return ret

    _columns = {
        'object_name': fields.function(_get_object_name, type='char', method=True, string='Title'),
        'name': fields.char('Reference', size=64, select=True),
        'origin': fields.char('Origin', size=512, help="Reference of the document that produced this picking.", select=True),
        'backorder_id': fields.many2one('stock.picking', 'Back Order of', help="If this picking was split this field links to the picking that contains the other part that has been processed already.", select=True),
        'type': fields.selection([('out', 'Sending Goods'), ('in', 'Getting Goods'), ('internal', 'Internal')], 'Shipping Type', required=True, select=True, help="Shipping type specify, goods coming in or going out."),
        'note': fields.text('Notes'),
        'stock_journal_id': fields.many2one('stock.journal','Stock Journal', select=True),
        'location_id': fields.many2one('stock.location', 'Location', help="Keep empty if you produce at the location where the finished products are needed." \
                                       "Set a location if you produce at a fixed location. This can be a partner location " \
                                       "if you subcontract the manufacturing operations.", select=True),
        'location_dest_id': fields.many2one('stock.location', 'Dest. Location',help="Location where the system will stock the finished products.", select=True),
        'move_type': fields.selection([('direct', 'Partial Delivery'), ('one', 'All at once')], 'Delivery Method', required=True, help="It specifies goods to be delivered all at once or by direct delivery"),
        'state': fields.selection([
            ('draft', 'Draft'),
            ('auto', 'Waiting'),
            ('confirmed', 'Confirmed'),
            ('assigned', 'Available'),
            ('done', 'Done'),
            ('cancel', 'Cancelled'),
        ], 'State', readonly=True, select=True,
            help="* Draft: not confirmed yet and will not be scheduled until confirmed\n"\
                 "* Confirmed: still waiting for the availability of products\n"\
                 "* Available: products reserved, simply waiting for confirmation.\n"\
                 "* Waiting: waiting for another move to proceed before it becomes automatically available (e.g. in Make-To-Order flows)\n"\
                 "* Done: has been processed, can't be modified or cancelled anymore\n"\
                 "* Cancelled: has been cancelled, can't be confirmed anymore"),
        'min_date': fields.function(get_min_max_date, fnct_inv=_set_minimum_date, multi="min_max_date",
                                    method=True, store=True, type='datetime', string='Expected Date', select=1, help="Expected date for the picking to be processed"),
        'date': fields.datetime('Order Date', help="Date of Order", select=True),
        'date_done': fields.datetime('Date Done', help="Date of Completion"),
        'max_date': fields.function(get_min_max_date, fnct_inv=_set_maximum_date, multi="min_max_date",
                                    method=True, store=True, type='datetime', string='Max. Expected Date', select=2),
        'move_lines': fields.one2many('stock.move', 'picking_id', 'Internal Moves', states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}),
        'auto_picking': fields.boolean('Auto-Picking'),
        'address_id': fields.many2one('res.partner.address', 'Address', help="Address of partner"),
        'partner_id': fields.related('address_id','partner_id',type='many2one',relation='res.partner',string='Partner',store=True),
        'invoice_state': fields.selection([
            ("invoiced", "Invoiced"),
            ("2binvoiced", "To Be Invoiced"),
            ("none", "Not Applicable")], "Invoice Control",
            select=True, required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'company_id': fields.many2one('res.company', 'Company', required=True, select=True),
        'claim': fields.boolean('Claim'),
        'claim_name': fields.char(string='Claim name', size=512),
        'physical_reception_date': fields.datetime('Physical Reception Date', states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}),
        'location_dest_active_ok': fields.function(_get_location_dest_active_ok, method=True, type='boolean', string='Dest location is inactive ?', store=False),
        'packing_list': fields.char('Supplier Packing List', size=30),
        'is_subpick': fields.boolean('Main or Sub PT'),
    }
    _defaults = {
        'name': lambda self, cr, uid, context: '/',
        'state': 'draft',
        'move_type': 'direct',
        'type': 'in',
        'is_subpick': False,
        'invoice_state': 'none',
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.picking', context=c)
    }

    def _stock_picking_action_process_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_process method from stock>stock.py>stock_picking

        - allow to modify the data for wizard display
        '''
        if context is None:
            context = {}
        res = kwargs['res']
        return res

    def action_process(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None: context = {}
        partial_id = self.pool.get("stock.partial.picking").create(
            cr, uid, {}, context=dict(context, active_ids=ids))
        res = {
            'name':_("Products to Process"),
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'stock.partial.picking',
            'res_id': partial_id,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': dict(context, active_ids=ids)
        }
        # hook on view dic
        res = self._stock_picking_action_process_hook(cr, uid, ids, context=context, res=res,)
        return res

    def _erase_prodlot_hook(self, cr, uid, id, context=None, *args, **kwargs):
        '''
        hook to keep the production lot when a stock move is copied
        '''
        res = kwargs.get('res')
        assert res is not None, 'missing res'
        return res and not context.get('keep_prodlot', False)

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        if context is None:
            context = {}
        default = default.copy()
        default.update({
            'claim': False,
            'claim_name': '',
            'from_manage_expired': False,
        })

        if 'is_subpick' not in default:
            default['is_subpick'] = False

        fields_to_read = ['name', 'type']

        if not context.get('keep_prodlot'):
            fields_to_read += ['move_lines']

        picking_obj = self.read(cr, uid, id, fields_to_read, context=context)
        move_obj = self.pool.get('stock.move')

        if not context.get('keep_prodlot') and picking_obj.get('move_lines') and not context.get('allow_copy'):
            move_obj._check_locations_active(cr, uid, picking_obj['move_lines'], context=context)
        if ('name' not in default) or (picking_obj['name'] == '/'):
            seq_obj_name =  ''.join(('stock.picking.', picking_obj['type']))
            default['name'] = self.pool.get('ir.sequence').get(cr, uid, seq_obj_name)
            default['origin'] = ''
            default['backorder_id'] = False
        res = super(stock_picking, self).copy(cr, uid, id, default, context)
        if self._erase_prodlot_hook(cr, uid, id, context=context, res=res):
            picking_obj = self.read(cr, uid, res, ['move_lines'], context=context)
            move_obj.write(cr, uid, picking_obj['move_lines'], {'tracking_id': False,'prodlot_id':False})
        return res

    def onchange_partner_in(self, cr, uid, context=None, partner_id=None):
        return {}

    def action_explode(self, cr, uid, moves, context=None):
        return moves

    def action_confirm(self, cr, uid, ids, context=None):
        """ Confirms picking.
        @return: True
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.write(cr, uid, ids, {'state': 'confirmed'})
        todo = []
        todo_set = set()
        move_obj = self.pool.get('stock.move')
        for pick in self.read(cr, uid, ids, ['move_lines'], context=context):
            move_ids = move_obj.search(cr, uid,
                                       [('id', 'in', pick['move_lines']),
                                        ('state', '=', 'draft')])
            todo_set.update(move_ids)

        self.log_picking(cr, uid, ids, context=context)
        todo = self.action_explode(cr, uid, list(todo_set), context)
        if len(todo):
            self.pool.get('stock.move').action_confirm(cr, uid, todo, context=context)
        return True

    def test_auto_picking(self, cr, uid, ids):
        # TODO: Check locations to see if in the same location ?
        return True

    def action_assign(self, cr, uid, ids, context=None, *args):
        """ Changes state of picking to available if all moves are confirmed.
        @return: True
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        for pick in self.read(cr, uid, ids, ['name']):
            move_ids = move_obj.search(cr, uid, [('picking_id', '=', pick['id']),
                                                 ('state', 'in', ('waiting', 'confirmed'))], order='prodlot_id, product_qty desc')
            move_obj.action_assign(cr, uid, move_ids)
            self.infolog(cr, uid, 'Check availability ran on stock.picking id:%s (%s)' % (
                pick['id'], pick['name'],
            ))
        return True

    def force_assign(self, cr, uid, ids, *args):
        """ Changes state of picking to available if moves are confirmed or waiting.
        @return: True
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")
        move_obj = self.pool.get('stock.move')
        for pick in self.read(cr, uid, ids, ['move_lines']):
            move_ids = move_obj.search(cr, uid,
                                       [('id', 'in', pick['move_lines']),
                                        ('state', 'in', ('confirmed','waiting'))],
                                       order='NO_ORDER')
            if move_ids:
                move_obj.force_assign(cr, uid, move_ids)
            wf_service.trg_write(uid, 'stock.picking', pick['id'], cr)
        return True

    def draft_force_assign(self, cr, uid, ids, *args):
        """ Confirms picking directly from draft state.
        @return: True
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")
        for pick in self.read(cr, uid, ids, ['move_lines']):
            if not pick['move_lines']:
                raise osv.except_osv(_('Error !'),_('You can not process picking without stock moves'))
            wf_service.trg_validate(uid, 'stock.picking', pick['id'],
                                    'button_confirm', cr)
        return True

    def draft_validate(self, cr, uid, ids, context=None):
        """ Validates picking directly from draft state.
        @return: True
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")
        move_obj = self.pool.get('stock.move')
        self.draft_force_assign(cr, uid, ids)
        for pick in self.read(cr, uid, ids, ['move_lines'], context=context):
            move_obj.force_assign(cr, uid, pick['move_lines'])
            wf_service.trg_write(uid, 'stock.picking', pick.id, cr)
        return self.action_process(
            cr, uid, ids, context=context)

    def cancel_assign(self, cr, uid, ids, *args):
        """ Cancels picking and moves.
        @return: True
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")
        move_obj = self.pool.get('stock.move')
        for pick in self.browse(cr, uid, ids):
            move_ids = [x.id for x in pick.move_lines if x.state == 'assigned']
            move_obj.cancel_assign(cr, uid, move_ids)
            wf_service.trg_write(uid, 'stock.picking', pick.id, cr)
        return True

    def action_assign_wkf(self, cr, uid, ids, context=None):
        """ Changes picking state to assigned.
        @return: True
        """
        self.write(cr, uid, ids, {'state': 'assigned'})
        self.log_picking(cr, uid, ids, context=context)
        return True

    def test_finished(self, cr, uid, ids):
        """ Tests whether the move is in done or cancel state or not.
        @return: True or False
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        move_obj = self.pool.get('stock.move')
        move_to_write = []
        move_ids = move_obj.search(cr, uid,
                                   [('picking_id', 'in', ids),
                                    ('state', 'not in', ('done', 'cancel'))],
                                   order='NO_ORDER')
        for move in move_obj.read(cr, uid, move_ids, ['state', 'product_qty']):
            if move['product_qty'] != 0.0:
                if move_to_write:
                    move_obj.write(cr, uid, move_to_write, {'state': 'done'})
                return False
            else:
                move_to_write.append(move['id'])
        if move_to_write:
            move_obj.write(cr, uid, move_to_write, {'state': 'done'})
        return True

    def test_assigned(self, cr, uid, ids):
        """ Tests whether the move is in assigned state or not.
        @return: True or False
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        ok = True
        for pick in self.browse(cr, uid, ids):
            mt = pick.move_type
            for move in pick.move_lines:
                if (move.state in ('confirmed', 'draft')) and (mt == 'one'):
                    return False
                if (mt == 'direct') and (move.state == 'assigned') and (move.product_qty):
                    return True
                ok = ok and (move.state in ('cancel', 'done', 'assigned'))
        return ok

    def action_cancel(self, cr, uid, ids, context=None):
        """ 
        Changes picking state to cancel.
        @return: True
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        context['cancel_type'] = 'update_out'
        move_obj = self.pool.get('stock.move')
        for pick in self.read(cr, uid, ids, ['move_lines'], context=context):
            move_obj.action_cancel(cr, uid, pick['move_lines'], context)
        self.write(cr, uid, ids, {'state': 'cancel', 'invoice_state': 'none'})
        self.log_picking(cr, uid, ids, context=context)

        return True

    #
    # TODO: change and create a move if not parents
    #
    def action_done(self, cr, uid, ids, context=None):
        """ Changes picking state to done.
        @return: True
        """
        if isinstance(ids, (int, long)):
            ids = [ids]

        for sp in self.browse(cr, uid, ids, fields_to_fetch=['type', 'physical_reception_date']):
            if sp.type == 'in' and not sp.physical_reception_date:
                self.write(cr, uid, [sp.id], {'physical_reception_date': time.strftime('%Y-%m-%d %H:%M:%S')})

        self.write(cr, uid, ids, {
            'state': 'done',
            'date_done': time.strftime('%Y-%m-%d %H:%M:%S'),
        })
        self.log_picking(cr, uid, ids, context=context)
        return True

    def action_move(self, cr, uid, ids, return_goods=None, context=None):
        """ Changes move state to assigned.
        @return: True
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        move_obj = self.pool.get('stock.move')
        for pick in self.browse(cr, uid, ids, context=context):
            todo = []
            for move in pick.move_lines:
                if move.state == 'assigned':
                    todo.append(move.id)
            if len(todo):
                move_obj.action_done(cr, uid, todo,
                                     return_goods=return_goods, context=context)
        return True

    def get_currency_id(self, cr, uid, picking):
        return False

    def _get_payment_term(self, cr, uid, picking):
        """ Gets payment term from partner.
        @return: Payment term
        """
        partner = picking.address_id.partner_id
        return partner.property_payment_term and partner.property_payment_term.id or False

    def _get_address_invoice(self, cr, uid, picking):
        """ Gets invoice address of a partner
        @return {'contact': address, 'invoice': address} for invoice
        """
        partner_obj = self.pool.get('res.partner')
        partner = picking.address_id.partner_id
        return partner_obj.address_get(cr, uid, [partner.id],
                                       ['contact', 'invoice'])

    def _get_comment_invoice(self, cr, uid, picking):
        """
        @return: comment string for invoice
        """
        return picking.note or ''

    def _get_price_unit_invoice(self, cr, uid, move_line, type, context=None):
        """ Gets price unit for invoice
        @param move_line: Stock move lines
        @param type: Type of invoice
        @return: The price unit for the move line
        """
        if context is None:
            context = {}

        if type in ('in_invoice', 'in_refund'):
            # Take the user company and pricetype
            context['currency_id'] = move_line.company_id.currency_id.id
            amount_unit = move_line.product_id.price_get('standard_price', context)[move_line.product_id.id]
            return amount_unit
        else:
            return move_line.product_id.list_price

    def _get_discount_invoice(self, cr, uid, move_line):
        '''Return the discount for the move line'''
        return 0.0

    def _get_taxes_invoice(self, cr, uid, move_line, type):
        """ Gets taxes on invoice
        @param move_line: Stock move lines
        @param type: Type of invoice
        @return: Taxes Ids for the move line
        """
        if type in ('in_invoice', 'in_refund'):
            taxes = move_line.product_id.supplier_taxes_id
        else:
            taxes = move_line.product_id.taxes_id

        if move_line.picking_id and move_line.picking_id.address_id and move_line.picking_id.address_id.partner_id:
            return self.pool.get('account.fiscal.position').map_tax(
                cr,
                uid,
                move_line.picking_id.address_id.partner_id.property_account_position,
                taxes
            )
        else:
            return map(lambda x: x.id, taxes)

    def _get_account_analytic_invoice(self, cr, uid, picking, move_line):
        return False

    def _invoice_line_hook(self, cr, uid, move_line, invoice_line_id, account_id):
        """
        Create a link between invoice_line and purchase_order_line. This piece of information is available on move_line.order_line_id
        """
        if invoice_line_id and move_line:
            vals = {}
            # FROM PO
            if move_line.purchase_line_id:
                vals.update({'order_line_id': move_line.purchase_line_id.id})
                if move_line.purchase_line_id.notes:
                    vals['note'] = move_line.purchase_line_id.notes

            # FROM FO
            if move_line.sale_line_id:
                ana_obj = self.pool.get('analytic.distribution')
                vals.update({'sale_order_line_id': move_line.sale_line_id.id})
                distrib_id = move_line.sale_line_id.analytic_distribution_id and move_line.sale_line_id.analytic_distribution_id.id or False
                if distrib_id:
                    new_invl_distrib_id = ana_obj.copy(cr, uid, distrib_id, {})
                    if not new_invl_distrib_id:
                        raise osv.except_osv(_('Error'), _('An error occurred for analytic distribution copy for invoice.'))
                    ana_obj.create_funding_pool_lines(cr, uid, [new_invl_distrib_id], account_id)
                    vals['analytic_distribution_id'] = new_invl_distrib_id

                vals['sale_order_lines'] = [(4, move_line.sale_line_id.id)]

                self.pool.get('sale.order.line').write(cr, uid, [move_line.sale_line_id.id], {'invoiced': True})
            if vals:
                self.pool.get('account.invoice.line').write(cr, uid, [invoice_line_id], vals)
        return True

    def _invoice_hook(self, cr, uid, picking, invoice_id):
        '''Call after the creation of the invoice'''
        return

    def _get_invoice_type(self, pick):
        src_usage = dest_usage = None
        inv_type = None
        if pick.invoice_state == '2binvoiced':
            if pick.move_lines:
                src_usage = pick.move_lines[0].location_id.usage
                dest_usage = pick.move_lines[0].location_dest_id.usage
            if pick.type == 'out' and dest_usage == 'supplier':
                inv_type = 'in_refund'
            elif pick.type == 'out' and dest_usage == 'customer':
                inv_type = 'out_invoice'
            elif pick.type == 'in' and src_usage == 'supplier':
                inv_type = 'in_invoice'
            elif pick.type == 'in' and src_usage == 'customer':
                inv_type = 'out_refund'
            else:
                inv_type = 'out_invoice'
        return inv_type

    def _hook_invoice_vals_before_invoice_creation(self, cr, uid, ids, invoice_vals, picking):
        """
        Update journal by an inkind journal if we come from an inkind donation PO.
        Update partner account
        BE CAREFUL : For FO with PICK/PACK/SHIP, the invoice is not created on picking but on shipment
        """

        return invoice_vals

    def action_invoice_create_header(self, cr, uid, picking, journal_id, invoices_group, type, use_draft=False, context=None):
        """
        Create Invoice Header from picking
        picking is a browse record

        returns: invoice_id, invoice_type
        """


        assert(isinstance(picking, browse_record))
        if picking.invoice_state != '2binvoiced':
            return False, False

        if context is None:
            context = {}

        invoice_obj = self.pool.get('account.invoice')
        address_obj = self.pool.get('res.partner.address')
        po_obj = self.pool.get('purchase.order')
        fo_obj = self.pool.get('sale.order')
        inv_type = type
        intermission = False
        payment_term_id = False
        partner =  picking.address_id and picking.address_id.partner_id

        if picking.partner_id.partner_type in ('esc', 'internal'):
            return False, False

        if picking.claim:
            # don't invoice claim
            return False, False

        if not partner:
            raise osv.except_osv(_('Error, no partner !'),
                                 _('Please put a partner on the picking list if you want to generate invoice.'))

        if not inv_type:
            inv_type = self._get_invoice_type(picking)

        if inv_type in ('out_invoice', 'out_refund'):
            account_id = partner.property_account_receivable.id
            payment_term_id = self._get_payment_term(cr, uid, picking)
        else:
            account_id = partner.property_account_payable.id

        address_contact_id, address_invoice_id = \
            self._get_address_invoice(cr, uid, picking).values()
        if not address_contact_id:
            raise osv.except_osv(
                _('Error'),
                _('Please define an address on the partner if you want to generate invoice.'),
            )
        address = address_obj.browse(cr, uid, address_contact_id, context=context)

        comment = self._get_comment_invoice(cr, uid, picking)
        if invoices_group and partner.id in invoices_group:
            invoice_id = invoices_group[partner.id]
            invoice = invoice_obj.browse(cr, uid, invoice_id)
            invoice_vals = {
                'name': (invoice.name or '') + ', ' + (picking.name or ''),
                'origin': (invoice.origin or '') + ', ' + (picking.name or '') + (picking.origin and (':' + picking.origin) or ''),
                'comment': (comment and (invoice.comment and invoice.comment+"\n"+comment or comment)) or (invoice.comment and invoice.comment or ''),
                'date_invoice':context.get('date_inv',False),
                'user_id':uid
            }
            invoice_obj.write(cr, uid, [invoice_id], invoice_vals, context=context)
        else:
            invoice_vals = {
                'name': picking.name,
                'origin': (picking.name or '') + (picking.origin and (':' + picking.origin) or ''),
                'type': inv_type,
                'account_id': account_id,
                'partner_id': address.partner_id.id,
                'address_invoice_id': address_invoice_id,
                'address_contact_id': address_contact_id,
                'comment': comment,
                'payment_term': payment_term_id,
                'fiscal_position': partner.property_account_position.id,
                'date_invoice': context.get('date_inv', time.strftime('%Y-%m-%d',time.localtime())),
                'company_id': picking.company_id.id,
                'user_id':uid,
                'picking_id': picking.id,
            }
            if picking.sale_id:
                if not partner.property_account_position.id:
                    invoice_vals['fiscal_position'] = picking.sale_id.fiscal_position.id
                invoice_vals['name'] = (picking.sale_id.client_order_ref or '' )+ " : " + picking.name


            if picking.purchase_id and picking.purchase_id.order_type and picking.purchase_id.order_type == 'purchase_list':
                invoice_vals['purchase_list'] = True

            cur_id = self.get_currency_id(cr, uid, picking)
            if cur_id:
                invoice_vals['currency_id'] = cur_id
            if journal_id:
                invoice_vals['journal_id'] = journal_id

            # From US-2391 Donations before expiry and Standard donations linked to an intersection partner generate a Donation
            donation_intersection = picking and picking.purchase_id and picking.purchase_id.order_type in ['donation_exp', 'donation_st'] \
                and picking.partner_id and picking.partner_id.partner_type == 'section'
            if picking and picking.purchase_id and picking.purchase_id.order_type == "in_kind" or donation_intersection:
                journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'inkind'), ('is_current_instance', '=', True)])
                if not journal_ids:
                    raise osv.except_osv(_('Error'), _('No In-kind donation journal found!'))
                account_id = picking.partner_id and picking.partner_id.donation_payable_account and picking.partner_id.donation_payable_account.id or False
                if not account_id:
                    raise osv.except_osv(_('Error'), _('No Donation Payable account for this partner: %s') % (picking.partner_id.name or '',))

                invoice_vals.update({'journal_id': journal_ids[0], 'account_id': account_id, 'is_inkind_donation': True})

            if picking and picking.partner_id and picking.partner_id.partner_type == 'intermission':
                intermission_journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'intermission'),
                                                                                             ('is_current_instance', '=', True)])
                intermission_default_account = picking.company_id.intermission_default_counterpart
                if not intermission_journal_ids:
                    raise osv.except_osv(_('Error'), _('No Intermission journal found!'))
                if not intermission_default_account or not intermission_default_account.id:
                    raise osv.except_osv(_('Error'), _('Please configure a default intermission account in Company configuration.'))

                invoice_vals.update({'is_intermission': True, 'journal_id': intermission_journal_ids[0], 'account_id': intermission_default_account.id})
                intermission = True

            if picking and picking.type == 'in' and picking.partner_id and (not picking.partner_id.property_account_payable or not picking.partner_id.property_account_receivable):
                raise osv.except_osv(_('Error'), _('Partner of this incoming shipment has no account set. Please set appropriate accounts (receivable and payable) in order to process this IN'))

            if 'journal_id' not in invoice_vals:
                invoice_vals['journal_id'] = invoice_obj._get_journal(cr, uid, {'type': invoice_vals['type']})

            if use_draft:
                existing_ids = invoice_obj.search(cr, uid, [
                    ('state', '=', 'draft'),
                    ('type', '=', invoice_vals['type']),
                    ('partner_id', '=', invoice_vals['partner_id']),
                    ('picking_id', '=', invoice_vals['picking_id']),
                    ('journal_id', '=', invoice_vals['journal_id']),
                ], context=context)
                if existing_ids:
                    return existing_ids[0], invoice_vals['type']


            # US-1669 Add the Supplier Reference (partner + FOC2) to the description in the following use cases:
            # "IVI from Supply" and "SI with an intersection supplier"
            in_invoice = inv_type == 'in_invoice'
            di = 'is_direct_invoice' in invoice_vals and invoice_vals['is_direct_invoice']
            inkind_donation = 'is_inkind_donation' in invoice_vals and invoice_vals['is_inkind_donation']
            debit_note = 'is_debit_note' in invoice_vals and invoice_vals['is_debit_note']
            is_si = in_invoice and not di and not inkind_donation and not debit_note and not intermission
            is_ivi = in_invoice and not debit_note and not inkind_donation and intermission
            po = picking and picking.purchase_id
            intersection_partner = po and po.partner_type and po.partner_type == 'section'
            external_partner = po and po.partner_type and po.partner_type == 'external'
            new_name = False
            if (is_si and intersection_partner) or is_ivi:
                partner_ref = po and po.partner_ref or ''
                name_inv = 'name' in invoice_vals and invoice_vals['name'] or False
                new_name = partner_ref and name_inv and "%s : %s" % (partner_ref, name_inv) or False
            elif is_si and external_partner:
                # US-2562 Use case "SI from Supply (external supplier): C1 provides and ships to P1 (internal)"
                # => if it's a one to one order (FO = PO), add the FO Customer Reference to the SI Description
                fo_ids = po and po_obj.get_so_ids_from_po_ids(cr, uid, [po.id], context=context)
                if fo_ids and len(fo_ids) == 1:
                    fo = fo_obj.browse(cr, uid, fo_ids[0], fields_to_fetch=['partner_type', 'client_order_ref'], context=context)
                    if fo.partner_type and fo.partner_type == 'internal' and fo.client_order_ref:
                        name_inv = 'name' in invoice_vals and invoice_vals['name'] or False
                        new_name = name_inv and "%s : %s" % (fo.client_order_ref, name_inv) or False
            if new_name:
                invoice_vals.update({'name': new_name})
            # US-1669 Use case IVI from C1 to C2, don't display FOC2 (display only INXXX + POC1)
            origin_ivi = False
            if is_ivi:
                origin_ivi = picking.name and po and "%s:%s" % (picking.name, po.name) or False
            if origin_ivi:
                invoice_vals.update({'origin': origin_ivi})

            # Update Payment terms and due date for the Supplier Invoices and Refunds
            if is_si or inv_type == 'in_refund':
                si_payment_term = self._get_payment_term(cr, uid, picking)
                if si_payment_term:
                    invoice_vals.update({'payment_term': si_payment_term})
                    due_date = invoice_obj.get_due_date(cr, uid, si_payment_term, context.get('date_inv', False), context)
                    due_date and invoice_vals.update({'date_due': due_date})

            invoice_id = invoice_obj.create(cr, uid, invoice_vals, context=context)
        return invoice_id, inv_type

    def action_invoice_create_line(self, cr, uid, picking, move_line, invoice_id, group, inv_type, partner, context):
        """
        pickingn move_line, partner are a browse records
        it will create an invoice line for this stock.move
        """

        assert(isinstance(move_line, browse_record))
        assert(isinstance(picking, browse_record))
        assert(isinstance(partner, browse_record))
        assert(move_line.picking_id.id == picking.id)
        if move_line.state == 'cancel':
            return False

        # US-2041 - Do not invoice Picking Ticket / Delivery Order lines that are not linked to a DPO when
        # invoice creation was requested at DPO confirmation
        if picking.type == 'out' and context.get('invoice_dpo_confirmation') and move_line.dpo_id.id != context.get('invoice_dpo_confirmation'):
            return False

        if not inv_type:
            inv_type = self.pool.get('account.invoice').read(cr, uid, invoice_id, ['type'], context=context)['type']

        invoice_line_obj = self.pool.get('account.invoice.line')

        origin = move_line.picking_id.name or ''
        if move_line.picking_id.origin:
            origin += ':' + move_line.picking_id.origin
        if group:
            name = (picking.name or '') + '-' + move_line.name
        else:
            name = move_line.name

        if inv_type in ('out_invoice', 'out_refund'):
            account_id = move_line.product_id.product_tmpl_id.\
                property_account_income.id
            if not account_id:
                account_id = move_line.product_id.categ_id.\
                    property_account_income_categ.id
        else:
            account_id = move_line.product_id.product_tmpl_id.\
                property_account_expense.id
            if not account_id:
                account_id = move_line.product_id.categ_id.\
                    property_account_expense_categ.id

        price_unit = self._get_price_unit_invoice(cr, uid,
                                                  move_line, inv_type)
        discount = self._get_discount_invoice(cr, uid, move_line)
        tax_ids = self._get_taxes_invoice(cr, uid, move_line, inv_type)
        account_analytic_id = self._get_account_analytic_invoice(cr, uid, picking, move_line)

        #set UoS if it's a sale and the picking doesn't have one
        uos_id = move_line.product_uos and move_line.product_uos.id or False
        if not uos_id and inv_type in ('out_invoice', 'out_refund'):
            uos_id = move_line.product_uom.id
        account_id = self.pool.get('account.fiscal.position').map_account(cr, uid, partner.property_account_position, account_id)
        invoice_line_id = invoice_line_obj.create(cr, uid, {
            'name': name,
            'origin': origin,
            'invoice_id': invoice_id,
            'uos_id': uos_id,
            'product_id': move_line.product_id.id,
            'account_id': account_id,
            'price_unit': price_unit,
            'discount': discount,
            'quantity': move_line.product_uos_qty or move_line.product_qty,
            'invoice_line_tax_id': [(6, 0, tax_ids)],
            'account_analytic_id': account_analytic_id,
        }, context=context)
        self._invoice_line_hook(cr, uid, move_line, invoice_line_id, account_id)

        if picking.sale_id:
            for sale_line in picking.sale_id.order_line:
                if sale_line.product_id.type == 'service' and sale_line.invoiced == False:
                    if group:
                        name = picking.name + '-' + sale_line.name
                    else:
                        name = sale_line.name
                    if type in ('out_invoice', 'out_refund'):
                        account_id = sale_line.product_id.product_tmpl_id.\
                            property_account_income.id
                        if not account_id:
                            account_id = sale_line.product_id.categ_id.\
                                property_account_income_categ.id
                    else:
                        account_id = sale_line.product_id.product_tmpl_id.\
                            property_account_expense.id
                        if not account_id:
                            account_id = sale_line.product_id.categ_id.\
                                property_account_expense_categ.id
                    price_unit = sale_line.price_unit
                    discount = sale_line.discount
                    tax_ids = sale_line.tax_id
                    tax_ids = map(lambda x: x.id, tax_ids)

                    account_analytic_id = self._get_account_analytic_invoice(cr, uid, picking, sale_line)

                    account_id = self.pool.get('account.fiscal.position').map_account(cr, uid, picking.sale_id.partner_id.property_account_position, account_id)
                    invoice_line_id = invoice_line_obj.create(cr, uid, {
                        'name': name,
                        'invoice_id': invoice_id,
                        'uos_id': sale_line.product_uos.id or sale_line.product_uom.id,
                        'product_id': sale_line.product_id.id,
                        'account_id': account_id,
                        'price_unit': price_unit,
                        'discount': discount,
                        'quantity': sale_line.product_uos_qty,
                        'invoice_line_tax_id': [(6, 0, tax_ids)],
                        'account_analytic_id': account_analytic_id,
                        'notes':sale_line.notes
                    }, context=context)
                    self.pool.get('sale.order.line').write(cr, uid, [sale_line.id], {'invoiced': True,
                                                                                     'invoice_lines': [(6, 0, [invoice_line_id])],
                                                                                     })
        return True



    def action_invoice_create(self, cr, uid, ids, journal_id=False,
                              group=False, type='out_invoice', context=None):
        """ Creates invoice based on the invoice state selected for picking.
        @param journal_id: Id of journal
        @param group: Whether to create a group invoice or not
        @param type: Type invoice to be created
        @return: Ids of created invoices for the pickings
        """
        if context is None:
            context = {}

        invoice_obj = self.pool.get('account.invoice')
        invoices_group = {}
        res = {}
        for picking in self.browse(cr, uid, ids, context=context):
            invoice_id, inv_type = self.action_invoice_create_header(cr, uid, picking, journal_id, invoices_group, type, use_draft=False, context=context)
            if not invoice_id:
                continue

            partner = picking.address_id.partner_id
            if group:
                invoices_group[partner.id] = invoice_id

            res[picking.id] = invoice_id

            for move_line in picking.move_lines:
                self.action_invoice_create_line(cr, uid, picking, move_line, invoice_id, group, inv_type, partner, context)

            invoice_obj.button_compute(cr, uid, [invoice_id], context=context,
                                       set_total=(inv_type in ('in_invoice', 'in_refund')))
            self.write(cr, uid, [picking.id], {
                'invoice_state': 'invoiced',
            }, context=context)
            self._invoice_hook(cr, uid, picking, invoice_id)

            if partner.partner_type == 'intermission':
                if not picking.company_id or not picking.company_id.currency_id:
                    raise osv.except_osv(_('Warning'), _('No company currency found!'))

                wiz_account_change = self.pool.get('account.change.currency').create(cr, uid, {'currency_id': picking.company_id.currency_id.id}, context=context)
                self.pool.get('account.change.currency').change_currency(cr, uid, [wiz_account_change], context={'active_id': invoice_id})

        return res

    def test_done(self, cr, uid, ids, context=None):
        """ Test whether the move lines are done or not.
        @return: True or False
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        ok = False

        move_obj = self.pool.get('stock.move')

        moves = move_obj.search(cr, uid, [('picking_id', 'in', ids)],
                                order='NO_ORDER')
        if not moves:
            return True

        if move_obj.search(cr, uid, [('id', 'in', moves), ('state', 'not in',
                                                           ['cancel', 'done'])], limit=1, order='NO_ORDER'):
            return False

        if move_obj.search(cr, uid, [('id', 'in', moves), ('state', '=',
                                                           'done')], limit=1, order='NO_ORDER'):
            ok = True

        return ok

    def test_cancel(self, cr, uid, ids, context=None):
        """ Test whether the move lines are canceled or not.
        @return: True or False
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if self.pool.get('stock.move').search_exist(cr, uid, [('picking_id', 'in', ids), ('state', '!=', 'cancel')]):
            return False
        return True

    def allow_cancel(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for pick in self.browse(cr, uid, ids, context=context):
            if not pick.move_lines:
                return True
            for move in pick.move_lines:
                if move.state == 'done':
                    raise osv.except_osv(_('Error'), _('You cannot cancel picking because stock move is in done state !'))
        return True

    def unlink(self, cr, uid, ids, context=None):
        move_obj = self.pool.get('stock.move')
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        for pick in self.read(cr, uid, ids, ['state', 'move_lines'], context=context):
            if pick['state'] in ['done','cancel']:
                raise osv.except_osv(_('Error'), _('You cannot remove the picking which is in %s state !')%(pick['state'],))
            elif pick['state'] in ['confirmed','assigned', 'draft']:
                ctx = context.copy()
                ctx.update({'call_unlink':True, 'skipResequencing': True})
                if pick['state'] != 'draft':
                    #Cancelling the move in order to affect Virtual stock of product
                    move_obj.action_cancel(cr, uid, pick['move_lines'], ctx)
                #Removing the move
                move_obj.unlink(cr, uid, pick['move_lines'], ctx)

        return super(stock_picking, self).unlink(cr, uid, ids, context=context)

    # FIXME: needs refactoring, this code is partially duplicated in stock_move.do_partial()!
    def do_partial(self, cr, uid, ids, partial_datas, context=None):
        """ Makes partial picking and moves done.
        @param partial_datas : Dictionary containing details of partial picking
                          like partner_id, address_id, delivery_date,
                          delivery moves with product_id, product_qty, uom
        @return: Dictionary of values
        """
        if context is None:
            context = {}
        else:
            context = dict(context)
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        move_obj = self.pool.get('stock.move')
        product_obj = self.pool.get('product.product')
        currency_obj = self.pool.get('res.currency')
        uom_obj = self.pool.get('product.uom')
        sequence_obj = self.pool.get('ir.sequence')
        wf_service = netsvc.LocalService("workflow")
        for pick in self.browse(cr, uid, ids, context=context):
            new_picking = None
            complete, too_many, too_few = [], [], []
            move_product_qty = {}
            prodlot_ids = {}
            product_avail = {}
            for move in pick.move_lines:
                if move.state in ('done', 'cancel'):
                    continue
                partial_data = partial_datas.get('move%s'%(move.id), {})
                #Commented in order to process the less number of stock moves from partial picking wizard
                #assert partial_data, _('Missing partial picking data for move #%s') % (move.id)
                product_qty = partial_data.get('product_qty') or 0.0
                move_product_qty[move.id] = product_qty
                product_uom = partial_data.get('product_uom') or False
                product_price = partial_data.get('product_price') or 0.0
                product_currency = partial_data.get('product_currency') or False
                prodlot_id = partial_data.get('prodlot_id') or False
                prodlot_ids[move.id] = prodlot_id
                if move.product_qty == product_qty:
                    complete.append(move)
                elif move.product_qty > product_qty:
                    too_few.append(move)
                else:
                    too_many.append(move)

                # Average price computation
                if (pick.type == 'in') and (move.product_id.cost_method == 'average'):
                    product = product_obj.read(cr, uid, move.product_id.id, ['uom_id', 'qty_available'])
                    move_currency_id = move.company_id.currency_id.id
                    context['currency_id'] = move_currency_id
                    qty = uom_obj._compute_qty(cr, uid, product_uom, product_qty, product['uom_id'][0])

                    if product['id'] in product_avail:
                        product_avail[product['id']] += qty
                    else:
                        product_avail[product['id']] = product['qty_available']

                    if qty > 0:
                        new_price = currency_obj.compute(cr, uid, product_currency,
                                                         move_currency_id, product_price)
                        new_price = uom_obj._compute_price(cr, uid, product_uom, new_price,
                                                           product['uom_id'][0])
                        if product['qty_available'] <= 0:
                            new_std_price = new_price
                        else:
                            # Get the standard price
                            amount_unit = product_obj.price_get(cr, uid, [product['id']], 'standard_price', context)[product['id']]
                            new_std_price = ((amount_unit * product_avail[product['id']])\
                                             + (new_price * qty))/(product_avail[product['id']] + qty)
                        # Write the field according to price type field
                        product_obj.write(cr, uid, [product['id']], {'standard_price': new_std_price})

                        # Record the values that were chosen in the wizard, so they can be
                        # used for inventory valuation if real-time valuation is enabled.
                        move_obj.write(cr, uid, [move.id],
                                       {'price_unit': product_price,
                                        'price_currency_id': product_currency})


            for move in too_few:
                product_qty = move_product_qty[move.id]

                if not new_picking:
                    new_picking = self.copy(cr, uid, pick.id,
                                            {
                                                'name': sequence_obj.get(cr, uid, 'stock.picking.%s'%(pick.type)),
                                                'move_lines' : [],
                                                'state':'draft',
                                            })
                if product_qty != 0:
                    defaults = {
                        'product_qty' : product_qty,
                        'product_uos_qty': product_qty, #TODO: put correct uos_qty
                        'picking_id' : new_picking,
                        'state': 'assigned',
                        'move_dest_id': False,
                        'price_unit': move.price_unit,
                    }
                    prodlot_id = prodlot_ids[move.id]
                    if prodlot_id:
                        defaults.update(prodlot_id=prodlot_id)
                    move_obj.copy(cr, uid, move.id, defaults)

                move_obj.write(cr, uid, [move.id],
                               {
                    'product_qty' : move.product_qty - product_qty,
                    'product_uos_qty':move.product_qty - product_qty, #TODO: put correct uos_qty
                })

            if new_picking:
                move_obj.write(cr, uid, [c.id for c in complete], {'picking_id': new_picking})
            for move in complete:
                if prodlot_ids.get(move.id):
                    move_obj.write(cr, uid, [move.id], {'prodlot_id': prodlot_ids[move.id]})
            for move in too_many:
                product_qty = move_product_qty[move.id]
                defaults = {
                    'product_qty' : product_qty,
                    'product_uos_qty': product_qty, #TODO: put correct uos_qty
                }
                prodlot_id = prodlot_ids.get(move.id)
                if prodlot_ids.get(move.id):
                    defaults.update(prodlot_id=prodlot_id)
                if new_picking:
                    defaults.update(picking_id=new_picking)
                move_obj.write(cr, uid, [move.id], defaults)

            # At first we confirm the new picking (if necessary)
            if new_picking:
                wf_service.trg_validate(uid, 'stock.picking', new_picking, 'button_confirm', cr)
                # Then we finish the good picking
                self.write(cr, uid, [pick.id], {'backorder_id': new_picking})
                self.action_move(cr, uid, [new_picking])
                wf_service.trg_validate(uid, 'stock.picking', new_picking, 'button_done', cr)
                wf_service.trg_write(uid, 'stock.picking', pick.id, cr)
                delivered_pack_id = new_picking
            else:
                self.action_move(cr, uid, [pick.id])
                wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)
                delivered_pack_id = pick.id

            res[pick.id] = {'delivered_picking': delivered_pack_id or False}

        return res

    def _hook_picking_get_view(self, cr, uid, ids, context=None, *args, **kwargs):

        pick = kwargs['pick']
        action_list = {
            'standard': 'stock.action_picking_tree',
            'picking': 'msf_outgoing.action_picking_ticket',
            'ppl': 'msf_outgoing.action_ppl',
            'packing': 'msf_outgoing.action_packing_form',
            'out': 'stock.action_picking_tree',
            'in': 'stock.action_picking_tree4',
            'internal': 'stock.action_picking_tree6',
        }
        if pick.type == 'out' and pick.subtype:
            return action_list.get(pick.subtype, pick.type)

        return action_list.get(pick.type, 'stock.action_picking_tree6')


    def _hook_log_picking_modify_message(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        stock>stock.py>log_picking
        update the message to be displayed by the function
        '''
        message = kwargs['message']
        return message

    def _hook_state_list(self, cr, uid, *args, **kwargs):
        '''
        Change terms into states list
        '''
        return kwargs['state_list']


    def log_picking(self, cr, uid, ids, context=None):
        """ This function will create log messages for picking.
        @param cr: the database cursor
        @param uid: the current user's ID for security checks,
        @param ids: List of Picking Ids
        @param context: A standard dictionary for contextual values
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        user_obj = self.pool.get('res.users')
        lang_obj = self.pool.get('res.lang')
        user_lang = user_obj.read(cr, uid, uid, ['context_lang'], context=context)['context_lang']
        lang_id = lang_obj.search(cr, uid, [('code','=',user_lang)])
        date_format = lang_id and lang_obj.read(cr, uid, lang_id[0], ['date_format'], context=context)['date_format'] or '%m/%d/%Y'
        for pick in self.browse(cr, uid, ids, context=context):
            msg=''
            if pick.auto_picking:
                continue
            type_list = {
                'out':_("Delivery Order"),
                'in':_('Reception'),
                'internal': _('Internal picking'),
            }
            # modify the list of views
            message = ''.join((type_list.get(pick.type, _('Document')), " '", (pick.name or '?'), "' "))
            infolog_message = None
            if pick.state == 'assigned':
                infolog_message = ''.join((type_list.get(pick.type, _('Document')), " id:", str(pick.id) or 'False', " '", (pick.name or '?'), "' "))
            if pick.min_date:
                msg = ''.join((_(' for the '), datetime.strptime(pick.min_date, '%Y-%m-%d %H:%M:%S').strftime(date_format).decode('utf-8')))
            state_list = {
                'confirmed': _("is scheduled") + msg +'.',
                'assigned': _('is ready to process.'),
                'cancel': _('is cancelled.'),
                'done': _('is done.'),
                'draft':_('is in draft state.'),
            }
            state_list = self._hook_state_list(cr, uid, state_list=state_list, msg=msg)
            action_xmlid = self._hook_picking_get_view(cr, uid, ids, context=context, pick=pick)
            message += state_list[pick.state]
            if infolog_message:
                infolog_message += state_list[pick.state]
            # modify the message to be displayed
            message = self._hook_log_picking_modify_message(cr, uid, ids, context=context, message=message, pick=pick)
            if infolog_message:
                infolog_message = self._hook_log_picking_modify_message(cr, uid, ids, context=context, message=infolog_message, pick=pick)
            if pick.type != 'out' or pick.subtype != 'packing':
                # we dont log info on PACK/
                self.log(cr, uid, pick.id, message, action_xmlid=action_xmlid, context=context)

            if infolog_message:
                self.infolog(cr, uid, message)
        return True

    def copy_all(self, cr, uid, ids, context=None):
        cr.execute("update stock_move set qty_to_process=product_qty where state = 'assigned' and picking_id in %s and product_qty!=0", (tuple(ids),))
        return True

    def uncopy_all(self, cr, uid, ids, context=None):
        cr.execute("update stock_move set qty_to_process=0 where state in ('confirmed', 'assigned') and picking_id in %s and product_qty!=0", (tuple(ids),))
        return True

    def reset_all(self, cr, uid, ids, context=None):
        move_obj = self.pool.get('stock.move')
        cr.execute("select id, picking_id, product_id, line_number, purchase_line_id, sale_line_id, product_qty from stock_move where state in ('confirmed', 'assigned') and picking_id in %s and product_qty!=0", (tuple(ids),))
        data = {}
        to_del = []
        for x in cr.fetchall():
            key = (x[1], x[2], x[3], x[4], x[5])
            if key not in data:
                data[key] =  {'product_qty': 0, 'master': x[0]}
            else:
                to_del.append(x[0])
            data[key]['product_qty'] += x[6]
        to_check = []
        for key in data:
            to_check.append(data[key]['master'])
            move_obj.write(cr, uid, data[key]['master'], {'product_qty': data[key]['product_qty'], 'product_uos_qty': data[key]['product_qty'], 'prodlot_id': False, 'expired_date': False}, context=context)
        move_obj.unlink(cr, uid, to_del, force=True, context=context)
        move_obj.cancel_assign(cr, uid, to_check, context=context)
        self.check_availability_manually(cr, uid, ids, context=context)
        return True

    def quick_flow(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'flow_type': 'quick'}, context=context)
        return True

    def standard_flow(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'flow_type': 'full'}, context=context)
        return True

stock_picking()

class stock_production_lot(osv.osv):

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        reads = self.read(cr, uid, ids, ['name', 'prefix', 'ref'], context)
        res = []
        for record in reads:
            name = record['name']
            prefix = record['prefix']
            if prefix:
                name = prefix + '/' + name
            if record['ref']:
                name = '%s [%s]' % (name, record['ref'])
            res.append((record['id'], name))
        return res

    _name = 'stock.production.lot'
    _description = 'Production lot'

    def _get_stock(self, cr, uid, ids, field_name, arg, context=None):
        """ Gets stock of products for locations
        @return: Dictionary of values
        """
        if context is None:
            context = {}
        # when the location_id = False results now in showing stock for all internal locations
        # *previously*, was showing the location of no location (= 0.0 for all prodlot)
        if 'location_id' not in context or not context['location_id']:
            locations = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'internal')],
                                                               order='NO_ORDER', context=context)
        else:
            locations = context['location_id'] or []

        if isinstance(locations, (int, long)):
            locations = [locations]

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}.fromkeys(ids, 0.0)
        if locations:
            cr.execute('''select
                    prodlot_id,
                    sum(qty)
                from
                    stock_report_prodlots
                where
                    location_id IN %s and prodlot_id IN %s group by prodlot_id''',(tuple(locations),tuple(ids),))
            res.update(dict(cr.fetchall()))

        return res

    def _stock_search(self, cr, uid, obj, name, args, context=None):
        """ Searches Ids of products
        @return: Ids of locations
        """
        if context is None:
            context = {}
        # when the location_id = False results now in showing stock for all internal locations
        # *previously*, was showing the location of no location (= 0.0 for all prodlot)
        if 'location_id' not in context or not context['location_id']:
            locations = self.pool.get('stock.location').search(cr, uid,
                                                               [('usage', '=', 'internal')], order='NO_ORDER', context=context)
        else:
            locations = context['location_id'] or []

        if isinstance(locations, (int, long)):
            locations = [locations]

        ids = [('id', 'in', [])]
        if locations:
            cr.execute('''select
                    prodlot_id,
                    sum(qty)
                from
                    stock_report_prodlots
                where
                    location_id IN %s group by prodlot_id
                having  sum(qty) '''+ str(args[0][1]) + str(args[0][2]),(tuple(locations),))  # not_a_user_entry
            res = cr.fetchall()
            ids = [('id', 'in', map(lambda x: x[0], res))]
        return ids

    _columns = {
        'name': fields.char('Production Lot', size=64, required=True, help="Unique production lot, will be displayed as: PREFIX/SERIAL [INT_REF]"),
        'ref': fields.char('Internal Reference', size=256, help="Internal reference number in case it differs from the manufacturer's serial number"),
        'prefix': fields.char('Prefix', size=64, help="Optional prefix to prepend when displaying this serial number: PREFIX/SERIAL [INT_REF]"),
        'product_id': fields.many2one('product.product', 'Product', required=True, domain=[('type', '<>', 'service')]),
        'uom_id': fields.related('product_id', 'uom_id', type='many2one', relation='product.uom', readonly=1, write_relate=False, string='UoM'),
        'date': fields.datetime('Creation Date', required=True),
        'stock_available': fields.function(_get_stock, fnct_search=_stock_search, method=True, type="float", string="Available", select=True,
                                           help="Current quantity of products with this Production Lot Number available in company warehouses",
                                           digits_compute=dp.get_precision('Product UoM'), related_uom='uom_id'),
        'revisions': fields.one2many('stock.production.lot.revision', 'lot_id', 'Revisions'),
        'company_id': fields.many2one('res.company', 'Company', select=True),
        'move_ids': fields.one2many('stock.move', 'prodlot_id', 'Moves for this production lot', readonly=True),
    }
    _defaults = {
        'date':  lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'name': lambda x, y, z, c: x.pool.get('ir.sequence').get(y, z, 'stock.lot.serial'),
        'product_id': lambda x, y, z, c: c.get('product_id', False),
    }
    _sql_constraints = [
        ('name_ref_uniq', 'unique (name, ref)', 'The combination of serial number and internal reference must be unique !'),
    ]
    def action_traceability(self, cr, uid, ids, context=None):
        """ It traces the information of a product
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: List of IDs selected
        @param context: A standard dictionary
        @return: A dictionary of values
        """
        value = self.pool.get('action.traceability').action_traceability(cr,uid,ids,context)
        return value
stock_production_lot()

class stock_production_lot_revision(osv.osv):
    _name = 'stock.production.lot.revision'
    _description = 'Production lot revisions'

    _columns = {
        'name': fields.char('Revision Name', size=64, required=True),
        'description': fields.text('Description'),
        'date': fields.date('Revision Date'),
        'indice': fields.char('Revision Number', size=16),
        'author_id': fields.many2one('res.users', 'Author'),
        'lot_id': fields.many2one('stock.production.lot', 'Production lot', select=True, ondelete='cascade'),
        'company_id': fields.related('lot_id','company_id',type='many2one',relation='res.company',string='Company', store=True, readonly=True),
    }

    _defaults = {
        'author_id': lambda x, y, z, c: z,
        'date': lambda *a: time.strftime('%Y-%m-%d'),
    }

stock_production_lot_revision()

# ----------------------------------------------------
# Move
# ----------------------------------------------------

#
# Fields:
#   location_dest_id is only used for predicting futur stocks
#
class stock_move(osv.osv):

    def _getSSCC(self, cr, uid, context=None):
        cr.execute('select id from stock_tracking where create_uid=%s order by id desc limit 1', (uid,))
        res = cr.fetchone()
        return (res and res[0]) or False
    _name = "stock.move"
    _description = "Stock Move"
    _order = 'date_expected desc, id'
    _log_create = False

    def action_partial_move(self, cr, uid, ids, context=None):
        if context is None: context = {}
        partial_id = self.pool.get("stock.partial.move").create(
            cr, uid, {}, context=context)
        return {
            'name':_("Products to Process"),
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'stock.partial.move',
            'res_id': partial_id,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': context
        }


    def name_get(self, cr, uid, ids, context=None):
        res = []
        for line in self.browse(cr, uid, ids, context=context):
            res.append((line.id, (line.product_id.code or '/')+': '+line.location_id.name+' > '+line.location_dest_id.name))
        return res

    def _check_tracking(self, cr, uid, ids, context=None):
        """ Checks if production lot is assigned to stock move or not.
        @return: True or False
        """
        for move in self.browse(cr, uid, ids, context=context):
            if not move.prodlot_id and \
               (move.state == 'done' and \
                    ( \
                        (move.product_id.track_production and move.location_id.usage == 'production') or \
                        (move.product_id.track_production and move.location_dest_id.usage == 'production') or \
                        (move.product_id.track_incoming and move.location_id.usage == 'supplier') or \
                        (move.product_id.track_outgoing and move.location_dest_id.usage == 'customer') \
                    )):
                return False
        return True

    def _check_product_lot(self, cr, uid, ids, context=None):
        """ Checks whether move is done or not and production lot is assigned to that move.
        @return: True or False
        """
        for move in self.browse(cr, uid, ids, context=context):
            if move.prodlot_id and move.state == 'done' and (move.prodlot_id.product_id.id != move.product_id.id):
                return False
        return True

    _columns = {
        'name': fields.char('Name', size=64, required=True, select=True),
        'priority': fields.selection([('0', 'Not urgent'), ('1', 'Urgent')], 'Priority'),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'date': fields.datetime('Date', required=True, select=True, help="Move date: scheduled date until move is done, then date of actual move processing", readonly=True),
        'date_expected': fields.datetime('Scheduled Date', states={'done': [('readonly', True)]},required=True, select=True, help="Scheduled date for the processing of this move"),
        'product_id': fields.many2one('product.product', 'Product', required=True, select=True, domain=[('type','<>','service')],states={'done': [('readonly', True)]}),

        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product UoM'), required=True,states={'done': [('readonly', True)]}, related_uom='product_uom'),
        'product_uom': fields.many2one('product.uom', 'Unit of Measure', required=True,states={'done': [('readonly', True)]}),
        'product_uos_qty': fields.float('Quantity (UOS)', digits_compute=dp.get_precision('Product UoM'), states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}, related_uom='product_uos_qty'),
        'product_uos': fields.many2one('product.uom', 'Product UOS', states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}),
        'product_packaging': fields.many2one('product.packaging', 'Packaging', help="It specifies attributes of packaging like type, quantity of packaging,etc."),

        'location_id': fields.many2one('stock.location', 'Source Location', required=True, select=True,states={'done': [('readonly', True)]}, help="Sets a location if you produce at a fixed location. This can be a partner location if you subcontract the manufacturing operations."),
        'location_dest_id': fields.many2one('stock.location', 'Destination Location', required=True,states={'done': [('readonly', True)]}, select=True, help="Location where the system will stock the finished products."),
        'address_id': fields.many2one('res.partner.address', 'Destination Address', help="Optional address where goods are to be delivered, specifically used for allotment"),

        'prodlot_id': fields.many2one('stock.production.lot', 'Production Lot', states={'done': [('readonly', True)]}, help="Production lot is used to put a serial number on the production", select=True),
        'tracking_id': fields.many2one('stock.tracking', 'Pack', select=True, states={'done': [('readonly', True)]}, help="Logistical shipping unit: pallet, box, pack ..."),

        'auto_validate': fields.boolean('Auto Validate'),

        'move_dest_id': fields.many2one('stock.move', 'Destination Move', help="Optional: next stock move when chaining them", select=True),
        'move_history_ids': fields.many2many('stock.move', 'stock_move_history_ids', 'parent_id', 'child_id', 'Move History (child moves)'),
        'move_history_ids2': fields.many2many('stock.move', 'stock_move_history_ids', 'child_id', 'parent_id', 'Move History (parent moves)'),
        'picking_id': fields.many2one('stock.picking', 'Reference', select=True,states={'done': [('readonly', True)]}),
        'note': fields.text('Notes'),
        'state': fields.selection([('draft', 'Draft'), ('waiting', 'Waiting'), ('confirmed', 'Not Available'), ('assigned', 'Available'), ('done', 'Done'), ('cancel', 'Cancelled')], 'State', readonly=True, select=True,
                                  help='When the stock move is created it is in the \'Draft\' state.\n After that, it is set to \'Not Available\' state if the scheduler did not find the products.\n When products are reserved it is set to \'Available\'.\n When the picking is done the state is \'Done\'.\
              \nThe state is \'Waiting\' if the move is waiting for another one.'),
        'price_unit': fields.float('Unit Price', digits_compute= dp.get_precision('Account'), help="Technical field used to record the product cost set by the user during a picking confirmation (when average price costing method is used)"),
        'price_currency_id': fields.many2one('res.currency', 'Currency for average price', help="Technical field used to record the currency chosen by the user during a picking confirmation (when average price costing method is used)"),
        'company_id': fields.many2one('res.company', 'Company', required=True, select=True),
        'partner_id': fields.related('picking_id','address_id','partner_id',type='many2one', relation="res.partner", string="Partner", store=True, select=True),
        'backorder_id': fields.related('picking_id','backorder_id',type='many2one', relation="stock.picking", string="Back Order", select=True),
        'origin': fields.related('picking_id','origin',type='char', size=512, relation="stock.picking", string="Origin", store=True),

        # used for colors in tree views:
        'scrapped': fields.related('location_dest_id','scrap_location',type='boolean',relation='stock.location',string='Scrapped', readonly=True),

        'qty_to_process': fields.float('Qty to Process', digits_compute=dp.get_precision('Product UoM'), related_uom='product_uom'),
        'qty_processed': fields.float('Qty Processed', help="Main pick, resgister sum of qties processed"),
    }
    _constraints = [
        (_check_tracking,
            'You must assign a production lot for this product',
            ['prodlot_id']),
        (_check_product_lot,
            'You try to assign a lot which is not from the same product',
            ['prodlot_id'])]

    def _default_location_destination(self, cr, uid, context=None):
        """ Gets default address of partner for destination location
        @return: Address id or False
        """
        if context is None:
            context = {}
        if context.get('move_line', []):
            if context['move_line'][0]:
                if isinstance(context['move_line'][0], (tuple, list)):
                    return context['move_line'][0][2] and context['move_line'][0][2].get('location_dest_id',False)
                else:
                    move_list = self.pool.get('stock.move').read(cr, uid, context['move_line'][0], ['location_dest_id'])
                    return move_list and move_list['location_dest_id'][0] or False
        if context.get('address_out_id', False):
            property_out = self.pool.get('res.partner.address').browse(cr, uid, context['address_out_id'], context).partner_id.property_stock_customer
            return property_out and property_out.id or False
        return False

    def _default_location_source(self, cr, uid, context=None):
        """ Gets default address of partner for source location
        @return: Address id or False
        """
        if context is None:
            context = {}

        if context.get('ext_cu', False):
            return context['ext_cu']

        if context.get('move_line', []):
            try:
                return context['move_line'][0][2]['location_id']
            except:
                pass
        if context.get('address_in_id', False):
            part_obj_add = self.pool.get('res.partner.address').browse(cr, uid, context['address_in_id'], context=context)
            if part_obj_add.partner_id:
                return part_obj_add.partner_id.property_stock_supplier.id
        return False

    _defaults = {
        'location_id': _default_location_source,
        'location_dest_id': _default_location_destination,
        'state': 'draft',
        'priority': '1',
        'product_qty': 1.0,
        'scrapped' :  False,
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.move', context=c),
        'date_expected': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        if vals.get('from_pack') or vals.get('to_pack'):
            vals['integrity_error'] = 'empty'
        return  super(stock_move, self).write(cr, uid, ids, vals, context=context)

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        if 'qty_processed' not in default:
            default['qty_processed'] = 0

        return super(stock_move, self).copy(cr, uid, id, default, context=context)

    def _auto_init(self, cursor, context=None):
        res = super(stock_move, self)._auto_init(cursor, context=context)
        cursor.execute('SELECT indexname FROM pg_indexes WHERE indexname = \'stock_move_location_id_location_dest_id_product_id_state\'')
        if not cursor.fetchone():
            cursor.execute('CREATE INDEX stock_move_location_id_location_dest_id_product_id_state ON stock_move (location_id, location_dest_id, product_id, state)')
        return res

    def onchange_lot_processor(self, cr, uid, ids, lot_id, qty, location_id, uom_id, context=None):
        ret = self.pool.get('stock.move.processor').change_lot(cr, uid, ids, lot_id, qty, location_id, uom_id, context)
        if 'expiry_date' in ret.get('value', {}):
            ret['value']['expired_date'] = ret['value']['expiry_date']
        return ret

    def onchange_expiry_processor(self, cr, uid, ids, expiry_date=False, product_id=False, type_check=False, context=None):
        ret = self.pool.get('stock.move.processor').change_expiry(cr, uid, ids, expiry_date, product_id, type_check, context)
        if 'expiry_date' in ret.get('value', {}):
            ret['value']['expired_date'] = ret['value']['expiry_date']
        return ret

    def onchange_qty_to_process(self, cr, uid, ids, qty_to_process, product_qty, uom_id, context=None):
        if qty_to_process > product_qty:
            return {
                'value': {'qty_to_process': 0},
                'warning': {
                    'title': _('Warning'),
                    'message': _("Processing Qty can't be larger than move qty.")
                }
            }
        return self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, qty_to_process, fields_q=['qty_to_process'], context=context)

    def onchange_lot_id(self, cr, uid, ids, prodlot_id=False, product_qty=False,
                        loc_id=False, product_id=False, uom_id=False, context=None):
        """ On change of production lot gives a warning message.
        @param prodlot_id: Changed production lot id
        @param product_qty: Quantity of product
        @param loc_id: Location id
        @param product_id: Product id
        @return: Warning message
        """
        if not prodlot_id or not loc_id:
            return {}
        ctx = context and context.copy() or {}
        ctx['location_id'] = loc_id
        ctx.update({'raise-exception': True})

        uom_obj = self.pool.get('product.uom')
        product_obj = self.pool.get('product.product')


        product_uom = product_obj.browse(cr, uid, product_id, fields_to_fetch=['uom_id'], context=ctx).uom_id
        prodlot = self.pool.get('stock.production.lot').browse(cr, uid, prodlot_id, fields_to_fetch=['stock_available'],  context=ctx)
        location = self.pool.get('stock.location').browse(cr, uid, loc_id, context=ctx)
        uom = uom_obj.browse(cr, uid, uom_id, context=ctx)
        amount_actual = uom_obj._compute_qty_obj(cr, uid, product_uom, prodlot.stock_available, uom, context=ctx)
        warning = {}
        if (location.usage == 'internal') and (product_qty > (amount_actual or 0.0)):
            warning = {
                'title': _('Insufficient Stock in Lot !'),
                'message': _('You are moving %.2f %s products but only %.2f %s available in this lot.') % (product_qty, uom.name, amount_actual, uom.name)
            }
        return {'warning': warning}

    def onchange_quantity(self, cr, uid, ids, product_id, product_qty,
                          product_uom, product_uos):
        """ On change of product quantity finds UoM and UoS quantities
        @param product_id: Product id
        @param product_qty: Changed Quantity of product
        @param product_uom: Unit of measure of product
        @param product_uos: Unit of sale of product
        @return: Dictionary of values
        """
        result = {
            'value' : {'product_uos_qty': 0.00}
        }

        if (not product_id) or (product_qty <=0.0):
            return result

        return self.pool.get('product.uom')._change_round_up_qty(cr, uid, product_uom, product_qty, ['product_qty', 'product_uos_qty'], result)

    def onchange_uos_quantity(self, cr, uid, ids, product_id, product_uos_qty,
                              product_uos, product_uom):
        """ On change of product quantity finds UoM and UoS quantities
        @param product_id: Product id
        @param product_uos_qty: Changed UoS Quantity of product
        @param product_uom: Unit of measure of product
        @param product_uos: Unit of sale of product
        @return: Dictionary of values
        """
        result = {
            'product_qty': 0.00
        }

        if (not product_id) or (product_uos_qty <=0.0):
            return {'value': result}

        product_obj = self.pool.get('product.product')
        uos_coeff = product_obj.read(cr, uid, product_id, ['uos_coeff'])

        if product_uos and product_uom and (product_uom != product_uos):
            result['product_qty'] = product_uos_qty / uos_coeff['uos_coeff']
        else:
            result['product_qty'] = product_uos_qty

        return {'value': result}

    def onchange_product_id(self, cr, uid, ids, prod_id=False, loc_id=False,
                            loc_dest_id=False, address_id=False, parent_type=False, purchase_line_id=False, out=False, context=None):
        """ On change of product id, if finds UoM, UoS, quantity and UoS quantity.
        @param prod_id: Changed Product id
        @param loc_id: Source location id
        @param loc_id: Destination location id
        @param address_id: Address id of partner
        @return: Dictionary of values
        """

        result = {
            'value': {
                'product_type': False,
                'hidden_batch_management_mandatory': False,
                'hidden_perishable_mandatory': False,
                'prodlot_id': False,
                'expired_date': False,
                'expiry_date': False,
            },
            'warning': {}}
        if not prod_id:
            if parent_type == 'in':
                result['value']['location_dest_id'] = False
            elif parent_type == 'out':
                result['value']['location_id'] = False
            else:
                result['value']['location_dest_id'] = False
                result['value']['location_id'] = False
            return result

        if context is None:
            context = {}

        prod_obj = self.pool.get('product.product')
        location_obj = self.pool.get('stock.location')


        product = prod_obj.browse(cr, uid, [prod_id], context=context)[0]
        uos_id  = product.uos_id and product.uos_id.id or False
        result['value'] = {
            'product_uom': product.uom_id.id,
            'product_uos': uos_id,
            'subtype': product.product_tmpl_id.subtype,
            'asset_id': False,
            'hidden_batch_management_mandatory': product.batch_management,
            'hidden_perishable_mandatory': product.perishable,
            'lot_check': product.batch_management,
            'exp_check': product.perishable,
            'product_qty': 0,
            'product_uos_qty': 0,
            'product_type': product.type,
        }
        if not ids:
            result['value']['name'] = product.partner_ref
        if loc_id:
            result['value']['location_id'] = loc_id
        if loc_dest_id:
            result['value']['location_dest_id'] = loc_dest_id

        if parent_type and parent_type == 'internal' and loc_dest_id:
            # Test the compatibility of the product with the location
            result, test = self.pool.get('product.product')._on_change_restriction_error(cr, uid, prod_id, field_name='product_id', values=result, vals={'location_id': loc_dest_id}, context=context)
            if test:
                return result
        elif parent_type in ('in', 'out'):
            # Test the compatibility of the product with a stock move
            result, test = prod_obj._on_change_restriction_error(cr, uid, prod_id, field_name='product_id', values=result, vals={'constraints': ['picking']})

        if product.batch_management:
            result['warning'] = {'title': _('Info'), 'message': _('The selected product is Batch Management.')}
        elif product.perishable:
            result['warning'] = {'title': _('Info'), 'message': _('The selected product is Perishable.')}


        location_id = loc_id and location_obj.browse(cr, uid, loc_id) or False
        location_dest_id = loc_dest_id and location_obj.browse(cr, uid, loc_dest_id) or False
        service_loc = location_obj.get_service_location(cr, uid)
        non_stockable_loc = location_obj.search(cr, uid, [('non_stockable_ok', '=', True)])
        if non_stockable_loc:
            non_stockable_loc = non_stockable_loc[0]
        id_cross = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        input_id = location_obj.search(cr, uid, [('input_ok', '=', True)])
        if input_id:
            input_id = input_id[0]
        po = purchase_line_id and self.pool.get('purchase.order.line').browse(cr, uid, purchase_line_id) or False
        cd = po and po.order_id.cross_docking_ok or False
        packing_ids = []
        stock_ids = []

        wh_ids = self.pool.get('stock.warehouse').search(cr, uid, [])
        for wh in self.pool.get('stock.warehouse').browse(cr, uid, wh_ids):
            packing_ids.append(wh.lot_packing_id.id)
            stock_ids.append(wh.lot_stock_id.id)


        if product.type and parent_type == 'in':
            # Set service location as destination for service products
            if product.type in ('service_recep', 'service'):
                if service_loc:
                    result['value'].update(location_dest_id=service_loc)
            # Set cross-docking as destination for non-stockable with cross-docking context
            elif product.type == 'consu' and cd and loc_dest_id not in (id_cross, service_loc):
                result['value'].update(location_dest_id=id_cross)
            # Set non-stockable as destination for non-stockable without cross-docking context
            elif product.type == 'consu' and not cd and loc_dest_id not in (id_cross, service_loc):
                result['value'].update(location_dest_id=non_stockable_loc)
            # Set input for standard products
            elif product.type == 'product' and not (loc_dest_id and (not location_dest_id.non_stockable_ok and (location_dest_id.usage == 'internal' or location_dest_id.virtual_ok))):
                result['value'].update(location_dest_id=input_id)
        elif product.type and parent_type == 'internal':
            # Source location
            # Only cross-docking is available for Internal move for non-stockable products
            if product.type == 'consu' and not (loc_id and (location_id.cross_docking_location_ok or location_id.quarantine_location)):
                result['value'].update(location_id=id_cross)
            elif product.type == 'product' and not (loc_id and (location_id.usage == 'internal' or location_dest_id.virtual_ok)):
                result['value'].update(location_id=stock_ids and stock_ids[0] or False)
            elif product.type == 'service_recep':
                result['value'].update(location_id=id_cross)
            # Destination location
            if product.type == 'consu' and not (loc_dest_id and (location_dest_id.usage == 'inventory' or location_dest_id.destruction_location or location_dest_id.quarantine_location)):
                result['value'].update(location_dest_id=non_stockable_loc)
            elif product.type == 'product' and not (loc_dest_id and (not location_dest_id.non_stockable_ok and (location_dest_id.usage == 'internal' or location_dest_id.virtual_ok))):
                result['value'].update(location_dest_id=False)
            elif product.type == 'service_recep':
                result['value'].update(location_dest_id=service_loc)
        # Case when outgoing delivery or picking ticket
        elif product.type and parent_type == 'out':
            # Source location
            # Only cross-docking is available for Outgoing moves for non-stockable products
            if product.type == 'consu' and not (loc_id and location_id.cross_docking_location_ok):
                result['value'].update(location_id=id_cross)
            elif product.type == 'product' and not (loc_id and (location_id.usage == 'internal' or not location_id.quarantine_location or not location_id.output_ok or not location_id.input_ok)):
                result['value'].update(location_id=stock_ids and stock_ids[0] or False)
            elif product.type == 'service_recep':
                result['value'].update(location_id=id_cross)
            # Destinatio location
            if product.type == 'consu' and not (loc_dest_id and (location_dest_id.output_ok or location_dest_id.usage == 'customer')):
                # If we are not in Picking ticket and the dest. loc. is not output or customer, unset the dest.
                if loc_id and loc_id not in packing_ids:
                    result['value'].update(location_dest_id=False)

        return result

    def _create_chained_picking_move_values_hook(self, cr, uid, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_process method from stock>stock.py>stock_picking

        - allow to modify the data for chained move creation
        '''
        if context is None:
            context = {}
        move_data = kwargs['move_data']
        # set the line number from original stock move
        move = kwargs['move']
        move_data.update({'line_number': move.line_number})
        return move_data

    def _get_location_for_internal_request(self, cr, uid, context=None, **kwargs):
        '''
        Get the requestor_location_id in case of IR to update the location_dest_id of each move
        '''
        return False

    def _create_chained_picking_internal_request(self, cr, uid, context=None, *args, **kwargs):
        '''
        Overrided in delivery_mechanism to create an OUT instead of or in plus of the INT at reception
        '''
        pickid = kwargs['picking']
        picking_obj = self.pool.get('stock.picking')
        wf_service = netsvc.LocalService("workflow")
        if kwargs['return_goods']:
            # Cancel the INT in case of Claim return/surplus processed from IN
            wf_service.trg_validate(uid, 'stock.picking', pickid, 'action_cancel', cr)
            picking_obj.action_cancel(cr, uid, [pickid], context=context)
        else:
            wf_service.trg_validate(uid, 'stock.picking', pickid, 'button_confirm', cr)
            wf_service.trg_validate(uid, 'stock.picking', pickid, 'action_assign', cr)
            # Make the stock moves available
            picking_obj.action_assign(cr, uid, [pickid], context=context)
        picking_obj.log_picking(cr, uid, [pickid], context=context)
        return

    def create_chained_picking(self, cr, uid, moves, return_goods=None, context=None):
        res_obj = self.pool.get('res.company')
        location_obj = self.pool.get('stock.location')
        move_obj = self.pool.get('stock.move')
        picking_obj = self.pool.get('stock.picking')
        new_moves = []
        if context is None:
            context = {}
        seq_obj = self.pool.get('ir.sequence')
        for picking, todo in self._chain_compute(cr, uid, moves, context=context).items():
            ptype = todo[0][1][5] and todo[0][1][5] or location_obj.picking_type_get(cr, uid, todo[0][0].location_dest_id, todo[0][1][0])
            if picking:
                # name of new picking according to its type
                new_pick_name = seq_obj.get(cr, uid, 'stock.picking.' + ptype)
                pickid = self._create_chained_picking(cr, uid, new_pick_name, picking, ptype, todo, context=context)

                # Need to check name of old picking because it always considers picking as "OUT" when created from Sale Order
                old_ptype = location_obj.picking_type_get(cr, uid, picking.move_lines[0].location_id, picking.move_lines[0].location_dest_id)
                picking_vals = {}
                if old_ptype != picking.type and not picking.claim:
                    picking_vals['name'] = seq_obj.get(cr, uid, 'stock.picking.' + old_ptype)
                if ptype == 'internal':
                    picking_vals['associate_pick_name'] = new_pick_name  # save the INT name into this original IN
                if picking_vals:
                    picking_obj.write(cr, uid, [picking.id], picking_vals, context=context)
            else:
                pickid = False
            for move, (loc, dummy, delay, dummy, company_id, ptype) in todo:
                location_dest_id = self._get_location_for_internal_request(cr, uid, context=context, move=move)
                if not location_dest_id:
                    location_dest_id = loc.id
                move_data = {'location_id': move.location_dest_id.id,
                             'location_dest_id': location_dest_id,
                             'date_moved': time.strftime('%Y-%m-%d'),
                             'picking_id': pickid,
                             'state': 'waiting',
                             'company_id': company_id or res_obj._company_default_get(cr, uid, 'stock.company', context=context),
                             'move_history_ids': [],
                             'date': (datetime.strptime(move.date, '%Y-%m-%d %H:%M:%S') + relativedelta(days=delay or 0)).strftime('%Y-%m-%d'),
                             'move_history_ids2': [],
                             }
                move_data = self._create_chained_picking_move_values_hook(cr, uid, context=context, move_data=move_data, move=move)
                new_id = move_obj.copy(cr, uid, move.id, move_data)
                move_obj.write(cr, uid, [move.id], {
                    'move_dest_id': new_id,
                    'move_history_ids': [(4, new_id)]
                })
                # UF-2424: If it's an internal move, just remove the asset_id
                if ptype == 'internal' and move.product_id.subtype == 'asset':
                    move_obj.write(cr, uid, [new_id], {'asset_id': False})

                new_moves.append(self.browse(cr, uid, [new_id])[0])
            if pickid:
                self._create_chained_picking_internal_request(cr, uid, context=context, picking=pickid, return_goods=return_goods)
        if new_moves:
            new_moves += self.create_chained_picking(cr, uid, new_moves, context)
        return new_moves

    def prepare_action_confirm(self, cr, uid, ids, context=None):
        '''
        split in smaller methods to ease the reusing of the code in other parts
        '''
        moves = self.browse(cr, uid, ids, context=context)
        ctx = context.copy()
        ctx.update({'action_confirm': True})
        self.create_chained_picking(cr, uid, moves, context=ctx)

    def action_confirm(self, cr, uid, ids, context=None, vals=None):
        """ Confirms stock move.
        @return: List of ids.
        """
        if not context:
            context = {}
        if vals is None:
            vals = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # check qty > 0 or raise
        self.check_product_quantity(cr, uid, ids, context=context)

        vals.update({'state': 'confirmed', 'already_confirmed': True})
        self.write(cr, uid, ids, vals)
        self.prepare_action_confirm(cr, uid, ids, context=context)
        return []


    def action_assign(self, cr, uid, ids, *args):
        """ Changes state to confirmed or waiting.
        @return: List of values
        """
        todo = []
        for move in self.browse(cr, uid, ids, fields_to_fetch=['state', 'already_confirmed']):
            if not move.already_confirmed:
                self.action_confirm(cr, uid, [move.id])
            if move.state in ('confirmed', 'waiting'):
                todo.append(move.id)
        res = self.check_assign(cr, uid, todo)
        return res

    def force_assign(self, cr, uid, ids, context=None):
        """ Changes the state to assigned.
        @return: True
        """
        self.write(cr, uid, ids, {'state': 'assigned'})
        return True

    def _hook_cancel_assign_batch(self, cr, uid, ids, context=None):
        '''
        Please copy this to your module's method also.
        This hook belongs to the cancel_assign method from stock>stock.py>stock_move class

        -  it erases the batch number associated if any and reset the source location to the original one.
        '''
        return True

    def cancel_assign(self, cr, uid, ids, context=None):
        """ Changes the state to confirmed.
        @return: True
        """
        self._hook_cancel_assign_batch(cr, uid, ids, context=context)
        self.write(cr, uid, ids, {'qty_to_process': 0,'state': 'confirmed'})
        return True

    #
    # Duplicate stock.move
    #
    def check_assign(self, cr, uid, ids, context=None):
        """ Checks the product type and accordingly writes the state.
        @return: No. of moves done
        """
        done = []
        move_to_assign = []
        count = 0
        pickings = {}
        if context is None:
            context = {}

        for move in self.browse(cr, uid, ids, context=context):
            if move.location_id.usage == 'supplier' or (move.location_id.usage == 'customer' and move.location_id.location_category == 'consumption_unit'):
                if move.state in ('confirmed', 'waiting'):
                    if move.location_id.id == move.location_dest_id.id:
                        done.append(move.id)
                    else:
                        move_to_assign.append(move.id)
                pickings.setdefault(move.picking_id.id, 0)
                pickings[move.picking_id.id] += 1
                continue
            if move.state in ('confirmed', 'waiting'):
                bn_needed =  move.product_id.perishable
                # Important: we must pass lock=True to _product_reserve() to avoid race conditions and double reservations
                prod_lot = False
                if bn_needed and move.prodlot_id:
                    prod_lot = move.prodlot_id.id
                res = self.pool.get('stock.location')._product_reserve_lot(cr, uid, [move.location_id.id], move.product_id.id,  move.product_qty, move.product_uom.id, lock=True, prod_lot=prod_lot)
                if res:
                    if move.location_id.id == move.location_dest_id.id:
                        state = 'done'
                        done.append(move.id)
                    else:
                        state = 'assigned'
                        move_to_assign.append(move.id)

                    pickings.setdefault(move.picking_id.id, 0)
                    pickings[move.picking_id.id] += 1
                    r = res.pop(0)
                    prodlot_id = None
                    expired_date = None
                    if bn_needed:
                        prodlot_id = r[3] or None
                        expired_date = r[2] or None
                    cr.execute("update stock_move set location_id=%s, product_qty=%s, product_uos_qty=%s, prodlot_id=%s, expired_date=%s, state=%s, qty_to_process=%s where id=%s", (r[1], r[0], r[0] * move.product_id.uos_coeff, prodlot_id, expired_date, state, r[0], move.id))
                    while res:
                        r = res.pop(0)
                        prodlot_id = False
                        expired_date = False
                        if bn_needed and r[1]:
                            prodlot_id = r[3]
                            expired_date = r[2]
                        if r[1]:
                            if r[1] == move.location_dest_id.id:
                                state = 'done'
                                qty_to_process = r[1]
                            else:
                                state = 'assigned'
                                qty_to_process = r[1]
                        else:
                            state = 'confirmed'
                            qty_to_process = 0

                        self.copy(cr, uid, move.id, {'qty_to_process': qty_to_process, 'line_number': move.line_number, 'product_qty': r[0], 'product_uos_qty': r[0] * move.product_id.uos_coeff, 'location_id': r[1] or move.location_id.id, 'prodlot_id': prodlot_id, 'expired_date': expired_date, 'state': state})

        if done:
            cr.execute('update stock_move set qty_to_process=product_qty where id in %s', (tuple(done),))
            self.write(cr, uid, done, {'state': 'done'})
        if move_to_assign:
            cr.execute('update stock_move set qty_to_process=product_qty where id in %s', (tuple(move_to_assign),))
            self.write(cr, uid, move_to_assign, {'state': 'assigned'})

        count = 0
        for pick_id in pickings:
            count += pickings[pick_id]
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_write(uid, 'stock.picking', pick_id, cr)
        return count

    def setlast_tracking(self, cr, uid, ids, context=None):
        tracking_obj = self.pool.get('stock.tracking')
        picking = self.browse(cr, uid, ids, context=context)[0].picking_id
        if picking:
            last_track = [line.tracking_id.id for line in picking.move_lines if line.tracking_id]
            if not last_track:
                last_track = tracking_obj.create(cr, uid, {}, context=context)
            else:
                last_track.sort()
                last_track = last_track[-1]
            self.write(cr, uid, ids, {'tracking_id': last_track})
        return True

    def _hook_move_cancel_state(self, cr, uid, *args, **kwargs):
        '''
        Change the state of the chained move
        '''
        return {'state': 'confirmed'}, kwargs['context']

    #
    # Cancel move => cancel others move and pickings
    #
    def action_cancel(self, cr, uid, ids, context=None):
        """ Cancels the moves and if all moves are cancelled it cancels the picking.
        @return: True
        """
        if not len(ids):
            return True
        if context is None:
            context = {}
        wf_service = netsvc.LocalService("workflow")
        picking_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')

        pickings = {}
        for move in self.browse(cr, uid, ids, context=context):
            if move.state in ('confirmed', 'waiting', 'assigned', 'draft'):
                if move.picking_id:
                    pickings[move.picking_id.id] = True
            if move.move_dest_id and move.move_dest_id.state == 'waiting':
                state, c = self._hook_move_cancel_state(cr, uid, context=context)
                context.update(c)
                self.write(cr, uid, [move.move_dest_id.id], state)
                if context.get('call_unlink',False) and move.move_dest_id.picking_id:
                    wf_service.trg_write(uid, 'stock.picking', move.move_dest_id.picking_id.id, cr)
            # cancel linked internal move if has, to keep the virtual stock consistent:
            internal_move = self.search(cr, uid, [('linked_incoming_move', '=', move.id)], context=context)
            if internal_move:
                self.action_cancel(cr, uid, internal_move, context=context)

        self.write(cr, uid, ids, {'state': 'cancel', 'move_dest_id': False})

        if not context.get('call_unlink',False):
            picking_to_write = []
            for pick in picking_obj.read(cr, uid, pickings.keys(), ['move_lines']):
                # if all movement are in cancel state:
                if not move_obj.search_exist(cr, uid, [('id', 'in', pick['move_lines']), ('state', '!=', 'cancel'),]):
                    picking_to_write.append(pick['id'])
            if picking_to_write:
                picking_obj.write(cr, uid, picking_to_write, {'state': 'cancel'})

        for id in ids:
            wf_service.trg_trigger(uid, 'stock.move', id, cr)
        return True

    def _get_accounting_data_for_valuation(self, cr, uid, move, context=None):
        """
        Return the accounts and journal to use to post Journal Entries for the real-time
        valuation of the move.

        :param context: context dictionary that can explicitly mention the company to consider via the 'force_company' key
        :raise: osv.except_osv() is any mandatory account or journal is not defined.
        """
        product_obj=self.pool.get('product.product')
        accounts = product_obj.get_product_accounts(cr, uid, move.product_id.id, context)
        if move.location_id.valuation_out_account_id:
            acc_src = move.location_id.valuation_out_account_id.id
        else:
            acc_src = accounts['stock_account_input']

        if move.location_dest_id.valuation_in_account_id:
            acc_dest = move.location_dest_id.valuation_in_account_id.id
        else:
            acc_dest = accounts['stock_account_output']

        acc_variation = accounts.get('property_stock_variation', False)
        journal_id = accounts['stock_journal']

        if acc_dest == acc_variation:
            raise osv.except_osv(_('Error!'),  _('Can not create Journal Entry, Output Account defined on this product and Variant account on category of this product are same.'))

        if acc_src == acc_variation:
            raise osv.except_osv(_('Error!'),  _('Can not create Journal Entry, Input Account defined on this product and Variant account on category of this product are same.'))

        if not acc_src:
            raise osv.except_osv(_('Error!'),  _('There is no stock input account defined for this product or its category: "%s" (id: %d)') % \
                                 (move.product_id.name, move.product_id.id,))
        if not acc_dest:
            raise osv.except_osv(_('Error!'),  _('There is no stock output account defined for this product or its category: "%s" (id: %d)') % \
                                 (move.product_id.name, move.product_id.id,))
        if not journal_id:
            raise osv.except_osv(_('Error!'), _('There is no journal defined on the product category: "%s" (id: %d)') % \
                                 (move.product_id.categ_id.name, move.product_id.categ_id.id,))
        if not acc_variation:
            raise osv.except_osv(_('Error!'), _('There is no inventory variation account defined on the product category: "%s" (id: %d)') % \
                                 (move.product_id.categ_id.name, move.product_id.categ_id.id,))
        return journal_id, acc_src, acc_dest, acc_variation

    def _get_reference_accounting_values_for_valuation(self, cr, uid, move, context=None):
        """
        Return the reference amount and reference currency representing the inventory valuation for this move.
        These reference values should possibly be converted before being posted in Journals to adapt to the primary
        and secondary currencies of the relevant accounts.
        """
        product_uom_obj = self.pool.get('product.uom')

        # by default the reference currency is that of the move's company
        reference_currency_id = move.company_id.currency_id.id

        default_uom = move.product_id.uom_id.id
        qty = product_uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, default_uom)

        # if product is set to average price and a specific value was entered in the picking wizard,
        # we use it
        if move.product_id.cost_method == 'average' and move.price_unit:
            reference_amount = qty * move.price_unit
            reference_currency_id = move.price_currency_id.id or reference_currency_id

        # Otherwise we default to the company's valuation price type, considering that the values of the
        # valuation field are expressed in the default currency of the move's company.
        else:
            if context is None:
                context = {}
            currency_ctx = dict(context, currency_id = move.company_id.currency_id.id)
            amount_unit = move.product_id.price_get('standard_price', currency_ctx)[move.product_id.id]
            reference_amount = amount_unit * qty or 1.0

        return reference_amount, reference_currency_id


    def _create_product_valuation_moves(self, cr, uid, move, context=None):
        """
        Generate the appropriate accounting moves if the product being moves is subject
        to real_time valuation tracking, and the source or destination location is
        a transit location or is outside of the company.
        """
        if move.product_id.valuation == 'real_time': # FIXME: product valuation should perhaps be a property?
            if context is None:
                context = {}
            src_company_ctx = dict(context,force_company=move.location_id.company_id.id)
            dest_company_ctx = dict(context,force_company=move.location_dest_id.company_id.id)
            account_moves = []
            # Outgoing moves (or cross-company output part)
            if move.location_id.company_id \
                and (move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal'\
                     or move.location_id.company_id != move.location_dest_id.company_id):
                journal_id, acc_src, acc_dest, acc_variation = self._get_accounting_data_for_valuation(cr, uid, move, src_company_ctx)
                reference_amount, reference_currency_id = self._get_reference_accounting_values_for_valuation(cr, uid, move, src_company_ctx)
                account_moves += [(journal_id, self._create_account_move_line(cr, uid, move, acc_variation, acc_dest, reference_amount, reference_currency_id, context))]

            # Incoming moves (or cross-company input part)
            if move.location_dest_id.company_id \
                and (move.location_id.usage != 'internal' and move.location_dest_id.usage == 'internal'\
                     or move.location_id.company_id != move.location_dest_id.company_id):
                journal_id, acc_src, acc_dest, acc_variation = self._get_accounting_data_for_valuation(cr, uid, move, dest_company_ctx)
                reference_amount, reference_currency_id = self._get_reference_accounting_values_for_valuation(cr, uid, move, src_company_ctx)
                account_moves += [(journal_id, self._create_account_move_line(cr, uid, move, acc_src, acc_variation, reference_amount, reference_currency_id, context))]

            move_obj = self.pool.get('account.move')
            for j_id, move_lines in account_moves:
                move_obj.create(cr, uid,
                                {'name': move.name,
                                 'journal_id': j_id,
                                 'line_id': move_lines,
                                 'ref': move.picking_id and move.picking_id.name})

    def _hook_action_done_update_out_move_check(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        choose if the corresponding out stock move must be updated
        '''
        move = kwargs['move']
        result = move.move_dest_id.id and (move.state != 'done')
        return result

    def action_done(self, cr, uid, ids, return_goods=None, context=None):
        """ Makes the move done and if all moves are done, it will finish the picking.
        @return:
        """
        partial_datas=''
        picking_ids = []
        move_ids = []
        partial_obj=self.pool.get('stock.partial.picking')
        wf_service = netsvc.LocalService("workflow")
        partial_id=partial_obj.search(cr,uid,[], order='NO_ORDER')
        if partial_id:
            partial_datas = partial_obj.read(cr, uid, partial_id, context=context)[0]
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        todo = self.search(cr, uid,
                           [('id', 'in', ids),
                            ('state', '=', 'draft')],
                           order='NO_ORDER', context=context)
        if todo:
            self.action_confirm(cr, uid, todo, context=context)
            todo = []

        move_ids = self.search(cr, uid,
                               [('id', 'in', ids),
                                ('state', 'not in', ('done', 'cancel'))],
                               order='NO_ORDER', context=context)

        for move in self.browse(cr, uid, move_ids, context=context):
            vals = {}
            if move.picking_id:
                picking_ids.append(move.picking_id.id)
            if self._hook_action_done_update_out_move_check(cr, uid, ids, context=context, move=move,):
                vals.update({'move_history_ids': [(4, move.move_dest_id.id)]})
                #cr.execute('insert into stock_move_history_ids (parent_id,child_id) values (%s,%s)', (move.id, move.move_dest_id.id))
                if move.move_dest_id.state in ('waiting', 'confirmed'):
                    if move.prodlot_id.id and move.product_id.id == move.move_dest_id.product_id.id:
                        self.write(cr, uid, [move.move_dest_id.id], {'prodlot_id':move.prodlot_id.id})
                    self.force_assign(cr, uid, [move.move_dest_id.id], context=context)
                    if move.move_dest_id.picking_id:
                        wf_service.trg_write(uid, 'stock.picking', move.move_dest_id.picking_id.id, cr)
                    if move.move_dest_id.auto_validate:
                        self.action_done(cr, uid, [move.move_dest_id.id], context=context)

            self._create_product_valuation_moves(cr, uid, move, context=context)
            prodlot_id = partial_datas and partial_datas.get('move%s_prodlot_id' % (move.id), False)
            if prodlot_id:
                vals.update({'prodlot_id': prodlot_id})
            if vals:
                self.write(cr, uid, [move.id], vals)
            if move.state not in ('confirmed', 'done', 'assigned'):
                todo.append(move.id)

        if todo:
            self.action_confirm(cr, uid, todo, context=context)

        if move_ids:
            self.write(cr, uid, move_ids, {'state': 'done', 'date': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
            wf_service.trg_trigger(uid, 'stock.move', move_ids, cr)

        pick_id_to_write = set()
        for pick in self.pool.get('stock.picking').read(cr, uid, picking_ids,
                                                        ['state', 'type'], context=context):
            wf_service.trg_write(uid, 'stock.picking', pick['id'], cr)
            ##### UF-2378 For some reason, the RW code from OpenERP kept the IN always in Available, even its lines are closed!!!
            if pick['state'] != 'done' and pick['type'] == 'in':
                pick_id_to_write.add(pick['id'])
        if pick_id_to_write:
            self.pool.get('stock.picking').write(cr, uid, list(pick_id_to_write),
                                                 {'state': 'done', 'date_done': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)

        moves = self.browse(cr, uid, move_ids, context=context)
        self.create_chained_picking(cr, uid, moves, return_goods, context)

        return True

    def _create_account_move_line(self, cr, uid, move, src_account_id, dest_account_id, reference_amount, reference_currency_id, context=None):
        """
        Generate the account.move.line values to post to track the stock valuation difference due to the
        processing of the given stock move.
        """
        # prepare default values considering that the destination accounts have the reference_currency_id as their main currency
        partner_id = (move.picking_id.address_id and move.picking_id.address_id.partner_id and move.picking_id.address_id.partner_id.id) or False
        debit_line_vals = {
            'name': move.name,
            'product_id': move.product_id and move.product_id.id or False,
            'quantity': move.product_qty,
            'ref': move.picking_id and move.picking_id.name or False,
            'date': time.strftime('%Y-%m-%d'),
            'partner_id': partner_id,
            'debit': reference_amount,
            'account_id': dest_account_id,
        }
        credit_line_vals = {
            'name': move.name,
            'product_id': move.product_id and move.product_id.id or False,
            'quantity': move.product_qty,
            'ref': move.picking_id and move.picking_id.name or False,
            'date': time.strftime('%Y-%m-%d'),
            'partner_id': partner_id,
            'credit': reference_amount,
            'account_id': src_account_id,
        }

        # if we are posting to accounts in a different currency, provide correct values in both currencies correctly
        # when compatible with the optional secondary currency on the account.
        # Financial Accounts only accept amounts in secondary currencies if there's no secondary currency on the account
        # or if it's the same as that of the secondary amount being posted.
        account_obj = self.pool.get('account.account')
        src_acct, dest_acct = account_obj.browse(cr, uid, [src_account_id, dest_account_id], context=context)
        src_main_currency_id = src_acct.company_id.currency_id.id
        dest_main_currency_id = dest_acct.company_id.currency_id.id
        cur_obj = self.pool.get('res.currency')
        if reference_currency_id != src_main_currency_id:
            # fix credit line:
            credit_line_vals['credit'] = cur_obj.compute(cr, uid, reference_currency_id, src_main_currency_id, reference_amount, context=context)
            if (not src_acct.currency_id) or src_acct.currency_id.id == reference_currency_id:
                credit_line_vals.update(currency_id=reference_currency_id, amount_currency=reference_amount)
        if reference_currency_id != dest_main_currency_id:
            # fix debit line:
            debit_line_vals['debit'] = cur_obj.compute(cr, uid, reference_currency_id, dest_main_currency_id, reference_amount, context=context)
            if (not dest_acct.currency_id) or dest_acct.currency_id.id == reference_currency_id:
                debit_line_vals.update(currency_id=reference_currency_id, amount_currency=reference_amount)

        return [(0, 0, debit_line_vals), (0, 0, credit_line_vals)]

    def unlink(self, cr, uid, ids, context=None, force=False):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        tools_obj = self.pool.get('sequence.tools')
        if not context.get('skipResequencing', False):
            # re sequencing only happen if purchase order is draft (behavior 1)
            draft_not_wkf_ids = self.allow_resequencing(cr, uid, ids, context=context)
            tools_obj.reorder_sequence_number_from_unlink(
                cr,
                uid,
                draft_not_wkf_ids,
                'stock.picking',
                'move_sequence_id',
                'stock.move',
                'picking_id',
                'line_number',
                context=context,
            )

        ctx = context.copy()
        for move in self.read(cr, uid, ids, ['state'], context=context):
            if move['state'] != 'draft' and not ctx.get('call_unlink',False)\
                    and not ctx.get('sync_update_execution')\
                    and not force:
                raise osv.except_osv(_('UserError'),
                                     _('You can only delete draft moves.'))
        return super(stock_move, self).unlink(cr, uid, ids, context=ctx)

    def _create_lot(self, cr, uid, ids, product_id, prefix=False):
        """ Creates production lot
        @return: Production lot id
        """
        prodlot_obj = self.pool.get('stock.production.lot')
        prodlot_id = prodlot_obj.create(cr, uid, {'prefix': prefix, 'product_id': product_id})
        return prodlot_id


    def open_split_wizard(self, cr, uid, ids, context=None):
        """
        Open the split line wizard: the user can select the quantity for the new move
        """
        wiz_obj = self.pool.get('split.move.processor')

        if isinstance(ids, (int, long)):
            ids = [ids]

        line = self.browse(cr, uid, ids[0], fields_to_fetch=['product_uom', 'product_qty'], context=context)
        split_wiz_id = wiz_obj.create(cr, uid, {
            'processor_line_id': ids[0],
            'processor_type': self._name,
            'uom_id': line.product_uom.id,
            'quantity': line.product_qty,
        }, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': wiz_obj._name,
            'view_type': 'form',
            'view_mode': 'form',
            'nodestroy': True,
            'target': 'new',
            'res_id': split_wiz_id,
            'context': context,
        }


    def split(self, cr, uid, id, quantity, uom_id, context=None):
        if context is None:
            context = {}
        keepLineNumber = context.get('keepLineNumber')
        context['keepLineNumber'] = True
        init_data = self.browse(cr, uid, id, fields_to_fetch=['product_qty', 'state', 'qty_to_process', 'pt_created'], context=context)
        if quantity >= init_data.product_qty:
            raise osv.except_osv(_('Warning'), _('Qty to split %s is more or equal to original qty %s') % (quantity, init_data.product_qty))

        copy_data = {'product_qty': quantity, 'product_uos_qty': quantity, 'state': init_data.state, 'qty_to_process': 0, 'pt_created': init_data.pt_created}
        new_id = self.copy(cr, uid, id, copy_data, context=context)

        new_qty = init_data.product_qty - quantity
        new_data = {'product_qty': new_qty, 'product_uos_qty': new_qty}
        if init_data.qty_to_process > new_qty:
            new_data['qty_to_process'] = new_qty

        self.write(cr, uid, id, new_data, context=context)
        context['keepLineNumber'] = keepLineNumber
        return new_id


stock_move()


class stock_inventory(osv.osv):
    _name = "stock.inventory"
    _description = "Inventory"
    _columns = {
        'name': fields.char('Inventory Reference', size=64, required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'date': fields.datetime('Creation Date', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'date_done': fields.datetime('Date done'),
        'inventory_line_id': fields.one2many('stock.inventory.line', 'inventory_id', 'Inventories', states={'done': [('readonly', True)]}),
        'move_ids': fields.many2many('stock.move', 'stock_inventory_move_rel', 'inventory_id', 'move_id', 'Created Moves'),
        'state': fields.selection( (('draft', 'Draft'), ('done', 'Done'), ('confirm','Validated'),('cancel','Cancelled')), 'State', readonly=True, select=True),
        'company_id': fields.many2one('res.company', 'Company', required=True, select=True, readonly=True, states={'draft':[('readonly',False)]}),

    }
    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'state': 'draft',
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.inventory', context=c)
    }

    def _inventory_line_hook(self, cr, uid, inventory_line, move_vals):
        """ Creates a stock move from an inventory line
        @param inventory_line:
        @param move_vals:
        @return:
        """
        return self.pool.get('stock.move').create(cr, uid, move_vals)

    def action_done(self, cr, uid, ids, context=None):
        """ Finish the inventory
        @return: True
        """
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        for inv in self.read(cr, uid, ids, ['move_ids'], context=context):
            move_obj.action_done(cr, uid, inv['move_ids'], context=context)
        self.write(cr, uid, ids, {'state':'done', 'date_done': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
        return True

    def _hook_dont_move(self, cr, uid, *args, **kwargs):
        return True

    def action_confirm(self, cr, uid, ids, context=None):
        """ Confirm the inventory and writes its finished date
        @return: True
        """
        if context is None:
            context = {}
        # to perform the correct inventory corrections we need analyze stock location by
        # location, never recursively, so we use a special context
        product_context = dict(context, compute_child=False)

        location_obj = self.pool.get('stock.location')
        product_obj = self.pool.get('product.product')
        product_tmpl_obj = self.pool.get('product.template')
        product_dict = {}
        product_tmpl_dict = {}

        for inv in self.read(cr, uid, ids, ['inventory_line_id', 'date', 'name'], context=context):
            move_ids = []

            # gather all information needed for the lines treatment first to do
            # less requests
            if self._name == 'initial.stock.inventory':
                inv_line_obj = self.pool.get('initial.stock.inventory.line')
            else:
                inv_line_obj = self.pool.get('stock.inventory.line')

            line_read = inv_line_obj.read(cr, uid, inv['inventory_line_id'],
                                          ['product_id', 'product_uom', 'prod_lot_id', 'location_id',
                                           'product_qty', 'inventory_id', 'dont_move', 'comment',
                                           'reason_type_id', 'average_cost'],
                                          context=context)
            product_id_list = [x['product_id'][0] for x in line_read if
                               x['product_id'][0] not in product_dict]
            product_id_list = list(set(product_id_list))
            product_read = product_obj.read(cr, uid, product_id_list,
                                            ['product_tmpl_id'], context=context)
            for product in product_read:
                product_id = product['id']
                product_dict[product_id] = {}
                product_dict[product_id]['p_tmpl_id'] = product['product_tmpl_id'][0]
            tmpl_ids = [x['p_tmpl_id'] for x in product_dict.values()]

            product_tmpl_id_list = [x for x in tmpl_ids if x not in
                                    product_tmpl_dict]
            product_tmpl_id_list = list(set(product_tmpl_id_list))
            product_tmpl_read = product_tmpl_obj.read(cr, uid,
                                                      product_tmpl_id_list, ['property_stock_inventory'],
                                                      context=context)
            product_tmpl_dict = dict((x['id'], x['property_stock_inventory'][0]) for x in product_tmpl_read)

            for product_id in product_id_list:
                product_tmpl_id = product_dict[product_id]['p_tmpl_id']
                stock_inventory = product_tmpl_dict[product_tmpl_id]
                product_dict[product_id]['stock_inventory'] = stock_inventory

            for line in line_read:
                pid = line['product_id'][0]
                lot_id = line['prod_lot_id'] and line['prod_lot_id'][0] or False
                product_context.update(uom=line['product_uom'][0],
                                       date=inv['date'], prodlot_id=lot_id)
                amount = location_obj._product_get(cr, uid,
                                                   line['location_id'][0], [pid], product_context)[pid]

                change = line['product_qty'] - amount
                if change and self._hook_dont_move(cr, uid, dont_move=line['dont_move']):
                    location_id = product_dict[line['product_id'][0]]['stock_inventory']
                    value = {
                        'name': 'INV:' + str(inv['id']) + ':' + inv['name'],
                        'product_id': line['product_id'][0],
                        'product_uom': line['product_uom'][0],
                        'prodlot_id': lot_id,
                        'date': inv['date'],
                    }
                    if change > 0:
                        value.update( {
                            'product_qty': change,
                            'location_id': location_id,
                            'location_dest_id': line['location_id'][0],
                        })
                    else:
                        value.update( {
                            'product_qty': -change,
                            'location_id': line['location_id'][0],
                            'location_dest_id': location_id,
                        })
                    value.update({
                        'comment': line['comment'],
                        'reason_type_id': line['reason_type_id'][0],
                    })

                    if self._name == 'initial.stock.inventory':
                        value.update({'price_unit': line['average_cost']})
                    move_ids.append(self._inventory_line_hook(cr, uid, None, value))
                elif not change:
                    inv_line_obj.write(cr, uid, [line['id']], {'dont_move': True}, context=context)
            message = _('Inventory') + " '" + inv['name'] + "' "+ _("is validated.")
            self.log(cr, uid, inv['id'], message)
            self.write(cr, uid, [inv['id']], {'state': 'confirm', 'move_ids': [(6, 0, move_ids)]})
        return True

    def action_cancel_draft(self, cr, uid, ids, context=None):
        """ Cancels the stock move and change inventory state to draft.
        @return: True
        """
        inv_to_write = set()
        for inv in self.read(cr, uid, ids, ['move_ids'], context=context):
            self.pool.get('stock.move').action_cancel(cr, uid, inv['move_ids'], context=context)
            inv_to_write.add(inv['id'])

        self.write(cr, uid, list(inv_to_write), {'state':'draft'}, context=context)
        return True

    def action_cancel_inventary(self, cr, uid, ids, context=None):
        """ Cancels both stock move and inventory
        @return: True
        """
        move_obj = self.pool.get('stock.move')
        account_move_obj = self.pool.get('account.move')
        for inv in self.browse(cr, uid, ids, context=context):
            move_obj.action_cancel(cr, uid, [x.id for x in inv.move_ids], context=context)
            for move in inv.move_ids:
                account_move_ids = account_move_obj.search(cr, uid, [('name',
                                                                      '=', move.name)], order='NO_ORDER')
                if account_move_ids:
                    account_move_data_l = account_move_obj.read(cr, uid, account_move_ids, ['state'], context=context)
                    for account_move in account_move_data_l:
                        if account_move['state'] == 'posted':
                            raise osv.except_osv(_('UserError'),
                                                 _('You can not cancel inventory which has any account move with posted state.'))
                        account_move_obj.unlink(cr, uid, [account_move['id']], context=context)
            line_ids = [x.id for x in inv.inventory_line_id]
            if line_ids and self._name != 'initial.stock.inventory':
                self.pool.get('stock.inventory.line').write(cr, uid, line_ids, {'dont_move': False}, context=context)
            self.write(cr, uid, [inv.id], {'state': 'cancel'}, context=context)
            if self._name == 'initial.stock.inventory':
                self.infolog(cr, uid, "The Initial Stock inventory id:%s (%s) has been canceled" % (inv.id, inv.name))
            else:
                self.infolog(cr, uid, "The Physical inventory id:%s (%s) has been canceled" % (inv.id, inv.name))
        return True

stock_inventory()

class stock_inventory_line(osv.osv):
    _name = "stock.inventory.line"
    _description = "Inventory Line"
    _columns = {
        'inventory_id': fields.many2one('stock.inventory', 'Inventory', ondelete='cascade', select=True),
        'location_id': fields.many2one('stock.location', 'Location', required=True),
        'product_id': fields.many2one('product.product', 'Product', required=True, select=True),
        'product_uom': fields.many2one('product.uom', 'Product UOM', required=True),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product UoM'), related_uom='product_uom'),
        'company_id': fields.related('inventory_id','company_id',type='many2one',relation='res.company',string='Company',store=True, select=True, readonly=True),
        'prod_lot_id': fields.many2one('stock.production.lot', 'Production Lot', domain="[('product_id','=',product_id)]"),
        'state': fields.related('inventory_id','state',type='char',string='State',readonly=True),
    }

    def on_change_product_id(self, cr, uid, ids, location_id, product, uom=False, to_date=False):
        """ Changes UoM and name if product_id changes.
        @param location_id: Location id
        @param product: Changed product_id
        @param uom: UoM product
        @return:  Dictionary of changed values
        """
        if not product:
            return {'value': {'product_qty': 0.0, 'product_uom': False}}
        obj_product = self.pool.get('product.product').browse(cr, uid, product)
        uom = uom or obj_product.uom_id.id
        amount = self.pool.get('stock.location')._product_get(cr, uid, location_id, [product], {'uom': uom, 'to_date': to_date})[product]
        result = {'product_qty': amount, 'product_uom': uom}
        return {'value': result}

stock_inventory_line()

#----------------------------------------------------------
# Stock Warehouse
#----------------------------------------------------------
class stock_warehouse(osv.osv):
    _name = "stock.warehouse"
    _description = "Warehouse"
    _columns = {
        'name': fields.char('Name', size=128, required=True, select=True),
        'company_id': fields.many2one('res.company', 'Company', required=True, select=True),
        'partner_address_id': fields.many2one('res.partner.address', 'Owner Address'),
        'lot_input_id': fields.many2one('stock.location', 'Location Input', required=True, domain=[('usage','<>','view')]),
        'lot_stock_id': fields.many2one('stock.location', 'Location Stock', required=True, domain=[('usage','<>','view')]),
        'lot_output_id': fields.many2one('stock.location', 'Location Output', required=True, domain=[('usage','<>','view')]),
    }
    _defaults = {
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.inventory', context=c),
    }

stock_warehouse()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
