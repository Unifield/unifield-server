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
import time
from operator import itemgetter
from itertools import groupby

from osv import fields, osv
from tools.translate import _
import netsvc
import tools
import decimal_precision as dp
import logging
import math
from osv.orm import browse_record

# Common method used on stock.location.instance and stock.location
def _get_used_in_config(self, cr, uid, ids, field_names, arg, context=None):
    ret = {}

    for _id in ids:
        ret[_id] =  False

    instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)
    if ids and instance_id:
        if self._name == 'stock.location':
            rel_table = 'local_location_configuration_rel'
        else:
            rel_table = 'remote_location_configuration_rel'
        cr.execute('''select rel.location_id from
                ''' + rel_table + ''' rel, replenishment_location_config config
                where
                    config.id = rel.config_id and
                    config.active and
                    config.main_instance = %s and
                    rel.location_id in %s
        ''', (instance_id, tuple(ids))) # not_a_user_entry
        for x in cr.fetchall():
            ret[x[0]] = True

    return ret

def _search_used_in_config(self, cr, uid, obj, name, args, context):
    for arg in args:
        if arg[1] != '=' or arg[2] is not False:
            raise osv.except_osv(_('Error'), _('Filter on %s not implemented') % (name,))

    instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)
    if instance_id:
        if self._name == 'stock.location':
            rel_table = 'local_location_configuration_rel'
        else:
            rel_table = 'remote_location_configuration_rel'
        cr.execute('''select rel.location_id from
                ''' + rel_table + ''' rel, replenishment_location_config config
                where
                    config.id = rel.config_id and
                    config.active and
                    config.main_instance = %s
        ''', (instance_id, )) # not_a_user_entry
        return [('id', 'not in', [x[0] for x in cr.fetchall()])]
    return []

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

        lang_obj = self.pool.get('res.lang')
        lang_ids = lang_obj.search(cr, uid, [('code', '=', context.get('lang', 'en_US'))])
        lang = lang_obj.browse(cr, uid, lang_ids[0])

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
            for prod in product_product_obj.browse(cr, uid, product_ids,
                                                   fields_to_fetch=['qty_available', 'virtual_available',
                                                                    'standard_price', 'uom_id'], context=c):

                if prod.uom_id:
                    digits = int(abs(math.log10(prod.uom_id.rounding)))
                else:
                    digits = 2

                for f in field_names:
                    if f in ['stock_real', 'stock_real_uom_rounding']:
                        if loc_id not in result:
                            result[loc_id] = {}
                        result[loc_id][f] += prod.qty_available
                    elif f in ['stock_virtual', 'stock_virtual_uom_rounding']:
                        result[loc_id][f] += prod.virtual_available
                    elif f == 'stock_real_value':
                        amount = prod.qty_available * prod.standard_price
                        amount = currency_obj.round(cr, uid, currency.rounding, amount)
                        result[loc_id][f] += amount
                    elif f == 'stock_virtual_value':
                        amount = prod.virtual_available * prod.standard_price
                        amount = currency_obj.round(cr, uid, currency.rounding, amount)
                        result[loc_id][f] += amount

                # Format the stock using the product's rounding
                if 'stock_real_uom_rounding' in field_names:
                    result[loc_id]['stock_real_uom_rounding'] = lang.format('%.' + str(digits) + 'f', result[loc_id]['stock_real_uom_rounding'] or 0, True)
                if 'stock_virtual_uom_rounding' in field_names:
                    result[loc_id]['stock_virtual_uom_rounding'] = lang.format('%.' + str(digits) + 'f', result[loc_id]['stock_virtual_uom_rounding'] or 0, True)

        return result

    def _get_coordo_db_id(self, cr, uid, ids, field_names, arg, context=None):
        ret = {}
        coordo_id = False
        company = self.pool.get('res.users').browse(cr, uid, uid).company_id
        if company and company.instance_id and company.instance_id.level == 'project':
            coordo_id = company.instance_id.parent_id.id
        for _id in ids:
            ret[_id] =  {'coordo_id': coordo_id, 'db_id': _id}
        return ret

    def _search_coordo_id(self, cr, uid, obj, name, args, context):
        for arg in args:
            if arg[1] != '=' or arg[2] is not True:
                raise osv.except_osv(_('Error'), _('Filter on %s not implemented') % (name,))

        company = self.pool.get('res.users').browse(cr, uid, uid).company_id
        if not company or not company.instance_id or company.instance_id.level != 'project':
            return [('id', '=', 0)]

        return [('active', 'in', ['t', 'f']), ('usage', '=', 'internal'), ('location_category', 'in', ['stock', 'consumption_unit', 'eprep'])]


    def _get_loc_ids_to_hide(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        loc_to_hide = [
            'msf_cross_docking_stock_location_input',
            'stock_stock_location_stock',
            'stock_stock_location_output',
            'msf_outgoing_stock_location_packing',
            'msf_outgoing_stock_location_dispatch',
            'msf_outgoing_stock_location_distribution',
            'stock_location_quarantine_view',
        ]

        data_domain = [('model', '=', 'stock.location'), ('name', 'in', loc_to_hide)]
        if ids:
            data_domain.append(('res_id', 'in', ids))
        loc_ids_to_hide = self.pool.get('ir.model.data').search(cr, uid, data_domain, context=context)

        return [x.get('res_id') for x in self.pool.get('ir.model.data').read(cr, uid, loc_ids_to_hide, ['res_id'], context=context)]

    def _get_initial_stock_inv_display(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}

        res = {}

        loc_ids_to_hide = self._get_loc_ids_to_hide(cr, uid, ids, context=context)
        for _id in ids:
            res[_id] = True
            if _id in loc_ids_to_hide:
                res[_id] = False

        return res

    def _search_initial_stock_inv_display(self, cr, uid, obj, name, args, context=None):
        '''
        Returns locations allowed in the Initial Stock Inventory
        '''
        if context is None:
            context = {}

        return [('id', 'not in', self._get_loc_ids_to_hide(cr, uid, [], context=context))]

    def _search_from_config(self, cr, uid, obj, name, args, context=None):
        for arg in args:
            if arg[1] != '=' or not isinstance(arg[2], (int, long)):
                raise osv.except_osv(_('Error'), _('Filter on %s not implemented') % (name,))

            retrict = []
            loc_config = self.pool.get('replenishment.location.config').browse(cr, uid, arg[2], fields_to_fetch=['local_location_ids'], context=context)
            for loc in loc_config.local_location_ids:
                retrict.append(loc.id)

            return [('id', 'in', retrict)]

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
        'stock_real_uom_rounding': fields.function(_product_value, method=True, type='char', size=32, string='Real Stock', multi="stock"),
        'stock_virtual_uom_rounding': fields.function(_product_value, method=True, type='char', size=32, string='Virtual Stock', multi="stock"),

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
        'coordo_id': fields.function(_get_coordo_db_id, type='many2one', relation='msf.instance', method=True, fnct_search=_search_coordo_id, string='Destination of sync', internal=True, multi='coordo_db_id'),
        'db_id': fields.function(_get_coordo_db_id, type='integer', method=True, string='DB id for sync', internal=True, multi='coordo_db_id'),
        'used_in_config': fields.function(_get_used_in_config, method=True, fnct_search=_search_used_in_config, string="Used in Loc.Config"),
        'from_config': fields.function(tools.misc.get_fake, method=True, fnct_search=_search_from_config, string='Set in Loc. Config', internal=1),
        'initial_stock_inv_display': fields.function(_get_initial_stock_inv_display, method=True, type='boolean', store=False, fnct_search=_search_initial_stock_inv_display, string='Display in Initial stock inventory', readonly=True),
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
        if vals.get('type') == 'in' and not vals.get('customers'):
            # manual creation
            vals['customers'] = self.pool.get('res.company')._get_instance_record(cr, user).instance

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
        ret = {}
        for pick in self.read(cr, uid, ids, ['is_subpick', 'subtype', 'flow_type'], context=context):
            flow_type = dict(self.fields_get(cr, uid, context=context)['flow_type']['selection']).get(pick['flow_type'])
            if pick['subtype'] == 'picking':
                if pick['is_subpick']:
                    ret[pick['id']] = _('Picking Ticket - %s Flow') % (flow_type,)
                else:
                    ret[pick['id']] = _('Picking List - %s Flow') % (flow_type,)
            else:
                ret[pick['id']] = False
        return ret

    def _get_destinations_list(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns a list of Destinations
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        res = {}
        for pick in self.browse(cr, uid, ids, fields_to_fetch=['type', 'subtype', 'location_dest_id', 'move_lines'], context=context):
            res[pick.id] = pick.location_dest_id and pick.location_dest_id.name or ''
            if pick.type == 'out' and pick.subtype == 'standard' and pick.move_lines:
                destinations = []
                for move in pick.move_lines:
                    if move.location_dest_id:
                        if move.location_dest_id.name not in destinations:
                            destinations.append(move.location_dest_id.name)
                if destinations:
                    res[pick.id] = '; '.join(destinations)

        return res

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
            ('delivered', 'Delivered'),
            ('cancel', 'Cancelled'),
        ], 'State', readonly=True, select=True,
            help="* Draft: not confirmed yet and will not be scheduled until confirmed\n"\
                 "* Confirmed: still waiting for the availability of products\n"\
                 "* Available: products reserved, simply waiting for confirmation.\n"\
                 "* Waiting: waiting for another move to proceed before it becomes automatically available (e.g. in Make-To-Order flows)\n"\
                 "* Done: has been processed, can't be modified or cancelled anymore. Can be processed to Delivered if the document is an OUT\n"\
                 "* Delivered: has been delivered, only for a closed OUT\n"\
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
        'destinations_list': fields.function(_get_destinations_list, method=True, type='char', size=512, string='Destination Location', store=False),
        'customers': fields.char('Customers', size=1026),
        'customer_ref': fields.char('Customer Ref.', size=1026),
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

    def _erase_prodlot_hook(self, cr, uid, id, context=None, *args, **kwargs):
        '''
        hook to keep the production lot when a stock move is copied
        '''
        res = kwargs.get('res')
        assert res is not None, 'missing res'
        return res and not context.get('keep_prodlot', False)

    def copy_web(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default.update({'customers': False, 'customer_ref': False})
        return self.copy(cr, uid, id, default=default, context=context)

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        if context is None:
            context = {}
        default = default.copy()
        to_reset = {
            'claim': False,
            'claim_name': '',
            'from_manage_expired': False,
        }
        for reset_f in to_reset:
            if reset_f not in default:
                default[reset_f] = to_reset[reset_f]

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

    def action_assign(self, cr, uid, ids, lefo=False, context=None):
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
            move_obj.action_assign(cr, uid, move_ids, lefo=lefo)
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
        for pick in self.read(cr, uid, ids, ['move_lines', 'name']):
            move_ids = move_obj.search(cr, uid,
                                       [('id', 'in', pick['move_lines']),
                                        ('state', 'in', ('confirmed','waiting'))],
                                       order='NO_ORDER')
            if move_ids:
                move_obj.force_assign(cr, uid, move_ids)
            wf_service.trg_write(uid, 'stock.picking', pick['id'], cr)
            self.infolog(cr, uid, 'Force availability ran on stock.picking id:%s (%s)' % (
                pick['id'], pick['name'],
            ))
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
        for pick in self.browse(cr, uid, ids, fields_to_fetch=['move_lines', 'name']):
            move_ids = [x.id for x in pick.move_lines if x.state == 'assigned']
            move_obj.cancel_assign(cr, uid, move_ids)
            wf_service.trg_write(uid, 'stock.picking', pick.id, cr)
            self.infolog(cr, uid, 'Cancel availability ran on stock.picking id:%s (%s)' % (
                pick['id'], pick['name'],
            ))
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
                'from_supply': True,
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

            # Add "synced" tag for STV and IVO created from Supply flow
            out_invoice = inv_type == 'out_invoice'
            is_stv = out_invoice and not di and not inkind_donation and not intermission
            is_ivo = out_invoice and not debit_note and not inkind_donation and intermission
            if is_stv or is_ivo:
                invoice_vals.update({'synced': True, })

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
        state_list = kwargs['state_list']

        state_list['done'] = _('is closed.')
        state_list['shipped'] = _('is shipped.')  # UF-1617: New state for the IN of partial shipment

        return state_list


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
            sub_type = {
                'picking': _('Picking Ticket'),
                'packing': _('Packing List'),
                'ppl': _('Pre-Packing List')
            }

            done_out = False
            if pick.type == 'out' and pick.subtype in sub_type:
                doc_name = sub_type.get(pick.subtype)
            else:
                doc_name = type_list.get(pick.type, _('Document'))
                done_out = pick.state == 'done' and pick.type == 'out' and pick.subtype == 'standard'
            # modify the list of views
            message = ''.join((doc_name, " '", (pick.name or '?'), "' "))
            infolog_message = None
            if pick.state == 'assigned':
                infolog_message = ''.join((doc_name, " id:", str(pick.id) or 'False', " '", (pick.name or '?'), "' "))
            if pick.min_date:
                msg = ''.join((_(' for the '), datetime.strptime(pick.min_date, '%Y-%m-%d %H:%M:%S').strftime(date_format).decode('utf-8')))
            state_list = {
                'confirmed': _("is scheduled") + msg +'.',
                'assigned': _('is ready to process.'),
                'cancel': _('is cancelled.'),
                'done': _('is done.'),
                'delivered': _('is delivered.'),
                'draft': _('is in draft state.'),
                'dispatched': _('is dispatched.'),
            }
            state_list = self._hook_state_list(cr, uid, state_list=state_list, msg=msg)
            action_xmlid = self._hook_picking_get_view(cr, uid, ids, context=context, pick=pick)
            message += done_out and state_list['dispatched'] or state_list[pick.state]
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

    def check_selected(self, context):
        if not context.get('button_selected_ids'):
            raise osv.except_osv(_('Warning'),  _('Please select at least one line'))
        return True

    def copy_all(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        self.check_selected(context)
        cr.execute("update stock_move set qty_to_process=product_qty where state = 'assigned' and picking_id in %s and product_qty!=0 and id in %s", (tuple(ids), tuple(context['button_selected_ids']))) # not_a_user_entry
        return {'type': 'ir.actions.refresh_o2m', 'o2m_refresh': 'move_lines'}

    def uncopy_all(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        self.check_selected(context)
        cr.execute("update stock_move set qty_to_process=0 where state in ('confirmed', 'assigned') and picking_id in %s and product_qty!=0 and id in %s", (tuple(ids), tuple(context['button_selected_ids'])))
        return {'type': 'ir.actions.refresh_o2m', 'o2m_refresh': 'move_lines'}

    def reset_all(self, cr, uid, ids, context=None):
        move_obj = self.pool.get('stock.move')
        cr.execute("select id, picking_id, product_id, line_number, purchase_line_id, sale_line_id, product_qty, in_out_updated from stock_move where state in ('confirmed', 'assigned') and picking_id in %s and product_qty!=0", (tuple(ids),))
        data = {}
        to_del = []
        for x in cr.fetchall():
            key = (x[1], x[2], x[3], x[4], x[5], x[7])
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

    def set_delivered(self, cr, uid, ids, context=None):
        '''
        Set the picking and its moves to delivered
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.write(cr, uid, ids, {'state': 'delivered'}, context=context)

        return True


stock_picking()


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

class stock_location_instance(osv.osv):
    _name = 'stock.location.instance'
    _description = 'Instance Location'


    _columns = {
        'name': fields.char('Name', size=64, required=True, translate=True),
        'active': fields.boolean('Active'),
        'parent_id': fields.many2one('stock.location.instance', 'Parent'),
        'usage': fields.selection([('supplier', 'Supplier Location'), ('view', 'View'), ('internal', 'Internal Location'), ('customer', 'Customer Location'), ('inventory', 'Inventory'), ('procurement', 'Procurement'), ('production', 'Production'), ('transit', 'Transit Location for Inter-Companies Transfers')], string='Usage'),
        'location_category': fields.selection( [('stock', 'Stock'), ('consumption_unit', 'Consumption Unit'), ('transition', 'Transition'), ('eprep', 'EPrep'), ('other', 'Other')], string='Location Category', required=True),
        'instance_id': fields.many2one('msf.instance', 'Instance', select=1),
        'instance_db_id': fields.integer('DB Id in the instance'),
        'full_name': fields.char('Name', size=256, readonly=1),
        'used_in_config': fields.function(_get_used_in_config, method=True, fnct_search=_search_used_in_config, string="Used in Loc.Config"),
    }
    def create_record(self, cr, uid, source, data_obj, context=None):
        data = data_obj.to_dict()
        instance_obj = self.pool.get('msf.instance')
        instance_id = instance_obj.search(cr, uid, [('instance', '=', source)], context=context)[0]
        to_update = self.search(cr, uid, [('instance_db_id', '=', int(data['db_id'])), ('instance_id', '=', instance_id), ('active', 'in', ['t', 'f'])], context=context)
        values = {
            'name': data['name'],
            'active': data['active'],
            'usage': data['usage'],
            'location_category': data['location_category'],
            'instance_id': instance_id,
            'instance_db_id': data['db_id'],
            'full_name': '',
        }
        if data.get('location_id'):
            values['parent_id'] = self.create_record(cr, uid, source, data_obj.location_id, context=context)
            values['full_name'] = '%s/' % (data['location_id']['name'])

        values['full_name'] = '%s-%s%s' % (source, values['full_name'], values['name'])

        if to_update:
            self.write(cr, uid, to_update, values, context=context)
            return to_update[0]

        return self.create(cr, uid, values, context)

    _sql_constraints = [('unique_instance_id_db_id', 'unique(instance_id,instance_db_id)', 'Instance / Db id not unique')]
stock_location_instance()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
