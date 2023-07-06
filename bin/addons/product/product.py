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
import decimal_precision as dp

import math
from _common import rounding
import re
from tools.translate import _
from tools import cache
from tools.safe_eval import safe_eval

def is_pair(x):
    return not x%2

def check_ean(eancode):
    if not eancode:
        return True
    if len(eancode) <> 13:
        return False
    try:
        int(eancode)
    except:
        return False
    oddsum=0
    evensum=0
    total=0
    eanvalue=eancode
    reversevalue = eanvalue[::-1]
    finalean=reversevalue[1:]

    for i in range(len(finalean)):
        if is_pair(i):
            oddsum += int(finalean[i])
        else:
            evensum += int(finalean[i])
    total=(oddsum * 3) + evensum

    check = int(10 - math.ceil(total % 10.0)) %10

    if check != int(eancode[-1]):
        return False
    return True
#----------------------------------------------------------
# UOM
#----------------------------------------------------------

class product_uom_categ(osv.osv):
    _name = 'product.uom.categ'
    _description = 'Product uom categ'
    _columns = {
        'name': fields.char('Name', size=64, required=True, translate=True),
    }
product_uom_categ()

class product_uom(osv.osv):
    _name = 'product.uom'
    _description = 'Product Unit of Measure'

    @cache(skiparg=3)
    def get_rounding(self, cr, uid):
        uom_ids = self.search(cr, 1, [])
        res = {}
        for uom_data in self.read(cr, 1, uom_ids, ['rounding']):
            res[uom_data['id']] = uom_data['rounding']
        return res

    def clear_caches(self, cr):
        self.get_rounding.clear_cache(cr.dbname)
        return self

    def _compute_factor_inv(self, factor):
        return factor and round(1.0 / factor, 6) or 0.0

    def _factor_inv(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for uom in self.browse(cursor, user, ids, context=context):
            res[uom.id] = self._compute_factor_inv(uom.factor)
        return res

    def _factor_inv_write(self, cursor, user, id, name, value, arg, context=None):
        return self.write(cursor, user, id, {'factor': self._compute_factor_inv(value)}, context=context)

    def create(self, cr, uid, data, context=None):
        if 'factor_inv' in data:
            if data['factor_inv'] <> 1:
                data['factor'] = self._compute_factor_inv(data['factor_inv'])
            del(data['factor_inv'])
        self.clear_caches(cr)
        return super(product_uom, self).create(cr, uid, data, context)

    def write(self, cr, uid, ids, data, context=None):
        if 'rounding' in data:
            self.get_rounding.clear_cache(cr.dbname)
        return super(product_uom, self).write(cr, uid, ids, data, context=context)

    def one_reference_by_categ(self, cr, uid, ids, context=None):
        cr.execute("""select count(*), category_id from product_uom where uom_type='reference' group by category_id""")
        for x in cr.fetchall():
            if x[0] != 1:
                categ = self.pool.get('product.uom.categ').read(cr, uid, x[1], context=context)
                raise osv.except_osv(_('Error !'), _('UoM Categ %s, must have one and only one UoM reference, found: %s') % (categ['name'], x[0]))
        return True

    _columns = {
        'name': fields.char('Name', size=64, required=True, translate=True),
        'category_id': fields.many2one('product.uom.categ', 'UoM Category', required=True, ondelete='cascade',
                                       help="Quantity conversions may happen automatically between Units of Measure in the same category, according to their respective ratios."),
        'factor': fields.float('Ratio', required=True,digits=(12, 12),
                               help='How many times this UoM is smaller than the reference UoM in this category:\n'\
                               '1 * (reference unit) = ratio * (this unit)'),
        'factor_inv': fields.function(_factor_inv, digits_compute=dp.get_precision('Product UoM'),
                                      fnct_inv=_factor_inv_write,
                                      method=True, string='Ratio',
                                      help='How many times this UoM is bigger than the reference UoM in this category:\n'\
                                      '1 * (this unit) = ratio * (reference unit)', required=True),
        'rounding': fields.float('Rounding Precision', digits_compute=dp.get_precision('Product UoM'), required=True,
                                 help="The computed quantity will be a multiple of this value. "\
                                 "Use 1.0 for a UoM that cannot be further split, such as a piece."),
        'active': fields.boolean('Active', help="By unchecking the active field you can disable a unit of measure without deleting it."),
        'uom_type': fields.selection([('bigger','Bigger than the reference UoM'),
                                      ('reference','Reference UoM for this category'),
                                      ('smaller','Smaller than the reference UoM')],'UoM Type', required=1),
    }

    _defaults = {
        'active': 1,
        'rounding': 0.01,
        'uom_type': 'reference',
    }

    _constraints = [
        (one_reference_by_categ, 'You must have one and only one reference by UoM Category', [])
    ]

    _sql_constraints = [
        ('factor_gt_zero', 'CHECK (factor!=0)', 'The conversion ratio for a unit of measure cannot be 0!'),
    ]

    def _compute_qty(self, cr, uid, from_uom_id, qty, to_uom_id=False):
        if not from_uom_id or not qty or not to_uom_id:
            return qty
        uoms = self.browse(cr, uid, [from_uom_id, to_uom_id])
        if uoms[0].id == from_uom_id:
            from_unit, to_unit = uoms[0], uoms[-1]
        else:
            from_unit, to_unit = uoms[-1], uoms[0]
        return self._compute_qty_obj(cr, uid, from_unit, qty, to_unit)

    def _compute_qty_obj(self, cr, uid, from_unit, qty, to_unit, context=None):
        if context is None:
            context = {}
        if from_unit.category_id.id <> to_unit.category_id.id:
            if context.get('raise-exception', True):
                raise osv.except_osv(_('Error !'), _('Conversion from Product UoM m to Default UoM PCE is not possible as they both belong to different Category!.'))
            else:
                return qty
        amount = qty / from_unit.factor
        if to_unit:
            amount = rounding(amount * to_unit.factor, to_unit.rounding)
        return amount

    def _compute_price(self, cr, uid, from_uom_id, price, to_uom_id=False):
        if not from_uom_id or not price or not to_uom_id:
            return price
        uoms = self.browse(cr, uid, [from_uom_id, to_uom_id])
        if uoms[0].id == from_uom_id:
            from_unit, to_unit = uoms[0], uoms[-1]
        else:
            from_unit, to_unit = uoms[-1], uoms[0]
        if from_unit.category_id.id <> to_unit.category_id.id:
            return price
        amount = price * from_unit.factor
        if to_uom_id:
            amount = amount / to_unit.factor
        return amount

    def onchange_type(self, cursor, user, ids, value):
        if value == 'reference':
            return {'value': {'factor': 1, 'factor_inv': 1}}
        return {}

product_uom()


class product_ul(osv.osv):
    _name = "product.ul"
    _description = "Shipping Unit"
    _columns = {
        'name' : fields.char('Name', size=64,select=True, required=True, translate=True),
        'type' : fields.selection([('unit','Unit'),('pack','Pack'),('box', 'Box'), ('pallet', 'Pallet')], 'Type', required=True),
    }
product_ul()


#----------------------------------------------------------
# Categories
#----------------------------------------------------------
class product_category(osv.osv):

    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        reads = self.read(cr, uid, ids, ['name','parent_id'], context=context)
        res = []
        for record in reads:
            name = record['name']
            if record['parent_id']:
                name = record['parent_id'][1]+' / '+name
            res.append((record['id'], name))
        return res

    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    _name = "product.category"
    _description = "Product Category"
    _columns = {
        'name': fields.char('Name', size=64, required=True, translate=True),
        'complete_name': fields.function(_name_get_fnc, method=True, type="char", string='Name'),
        'parent_id': fields.many2one('product.category','Parent Category', select=True),
        'child_id': fields.one2many('product.category', 'parent_id', string='Child Categories'),
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying a list of product categories."),
        'type': fields.selection([('view','View'), ('normal','Normal')], 'Category Type'),
    }


    _defaults = {
        'type' : lambda *a : 'normal',
    }

    _order = "sequence"
    def _check_recursion(self, cr, uid, ids, context=None):
        level = 100
        while len(ids):
            cr.execute('select distinct parent_id from product_category where id IN %s',(tuple(ids),))
            ids = filter(None, map(lambda x:x[0], cr.fetchall()))
            if not level:
                return False
            level -= 1
        return True

    _constraints = [
        (_check_recursion, 'Error ! You can not create recursive categories.', ['parent_id'])
    ]
    def child_get(self, cr, uid, ids):
        return [ids]

product_category()


#----------------------------------------------------------
# Products
#----------------------------------------------------------
class product_template(osv.osv):
    _name = "product.template"
    _description = "Product Template"

    def _calc_seller(self, cr, uid, ids, fields, arg, context=None):
        result = {}
        for product in self.browse(cr, uid, ids, context=context):
            for field in fields:
                result[product.id] = {field:False}
            result[product.id]['seller_delay'] = 1
            if product.seller_ids:
                partner_list = sorted([(partner_id.sequence, partner_id)
                                       for partner_id in  product.seller_ids
                                       if partner_id and isinstance(partner_id.sequence, (int, long))])
                main_supplier = partner_list and partner_list[0] and partner_list[0][1] or False
                result[product.id]['seller_delay'] =  main_supplier and main_supplier.delay or 1
                result[product.id]['seller_qty'] =  main_supplier and main_supplier.qty or 0.0
                result[product.id]['seller_id'] = main_supplier and main_supplier.name.id or False
        return result

    def _get_list_price(self, cr, uid, ids, fields, arg, context=None):
        '''
        Update the list_price = Field Price according to standard_price = Cost Price and the sale_price of the unifield_setup_configuration
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        setup_obj = self.pool.get('unifield.setup.configuration')
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = False
            standard_price = obj.standard_price
            #US-1035: Fixed the wrong hardcoded id given when calling config setup object
            setup_br = setup_obj and setup_obj.get_config(cr, uid)
            if not setup_br:
                return res
            percentage = setup_br.sale_price
            list_price = standard_price * (1 + (percentage/100.00))
            res[obj.id] = list_price
        return res

    def _get_finance_price_currency_id(self, cr, uid, ids, fields, arg, context=None):
        ret = {}
        cur_id = self.pool.get('res.users').get_company_currency_id(cr, uid)

        for _id in ids:
            ret[_id] = cur_id
        return ret

    _columns = {
        'name': fields.char('Name', size=128, required=True, translate=True, select=True),
        'product_manager': fields.many2one('res.users','Product Manager',help="This is use as task responsible"),
        'description': fields.text('Description',translate=True),
        'description_purchase': fields.text('Purchase Description',translate=True),
        'description_sale': fields.text('Sale Description',translate=True),
        'type': fields.selection([('product','Stockable Product'),('consu', 'Consumable'),('service','Service')], 'Product Type', required=True, help="Will change the way procurements are processed. Consumables are stockable products with infinite stock, or for use when you have no inventory management in the system."),
        'supply_method': fields.selection([('produce','Produce'),('buy','Buy')], 'Supply method', required=True, help="Produce will generate production order or tasks, according to the product type. Purchase will trigger purchase orders when requested."),
        'sale_delay': fields.float('Customer Lead Time', help="This is the average delay in days between the confirmation of the customer order and the delivery of the finished products. It's the time you promise to your customers."),
        'produce_delay': fields.float('Manufacturing Lead Time', help="Average delay in days to produce this product. This is only for the production order and, if it is a multi-level bill of material, it's only for the level of this product. Different lead times will be summed for all levels and purchase orders."),
        'procure_method': fields.selection([('make_to_stock','Make to Stock'),('make_to_order','Make to Order')], 'Procurement Method', required=True, help="'Make to Stock': When needed, take from the stock or wait until re-supplying. 'Make to Order': When needed, purchase or produce for the procurement request."),
        'rental': fields.boolean('Can be Rent'),
        'categ_id': fields.many2one('product.category','Category', required=True, change_default=True, domain="[('type','=','normal')]" ,help="Select category for the current product"),
        'standard_price': fields.float('Cost Price', required=True, digits_compute=dp.get_precision('Account Computation'), help="Price of product calculated according to the selected costing method."),
        'finance_price': fields.float('Finance Cost Price', readonly=1, digits_compute=dp.get_precision('Account Computation')),
        'finance_price_currency_id': fields.function(_get_finance_price_currency_id, 'Finance CP Currency', method=True, type='many2one', relation='res.currency'),
        'list_price': fields.function(_get_list_price, method=True, type='float', string='Sale Price', digits_compute=dp.get_precision('Sale Price Computation'), help="Base price for computing the customer price. Sometimes called the catalog price.",
                                      store = {
            'product.template': (lambda self, cr, uid, ids, c=None: ids, ['standard_price'], 10),
        }),
        'volume': fields.float('Volume', help="The volume in dm3.", digits=(16, 5)),
        'volume_updated': fields.boolean(string='Volume updated (deprecated)', readonly=True),
        'weight': fields.float('Gross weight', help="The gross weight in Kg.", digits=(16,5)),
        'weight_net': fields.float('Net weight', help="The net weight in Kg.", digits=(16,5)),
        'cost_method': fields.selection([('average', 'Average Price'), ('standard','Standard Price')], 'Costing Method', required=True, help="Average Price: the cost price is recomputed at each reception of products."),
        'warranty': fields.float('Warranty (months)'),
        'sale_ok': fields.boolean('Can be Sold', help="Determines if the product can be visible in the list of product within a selection from a sale order line."),
        'purchase_ok': fields.boolean('Can be Purchased', help="Determine if the product is visible in the list of products within a selection from a purchase order line."),
        'state': fields.integer('UniField Status', required=1),
        'uom_id': fields.many2one('product.uom', 'Default Unit Of Measure', required=True, help="Default Unit of Measure used for all stock operation."),
        'uom_po_id': fields.many2one('product.uom', 'Purchase Unit of Measure', required=True, help="Default Unit of Measure used for purchase orders. It must be in the same category than the default unit of measure."),
        'uos_id' : fields.many2one('product.uom', 'Unit of Sale',
                                   help='Used by companies that manage two units of measure: invoicing and inventory management. For example, in food industries, you will manage a stock of ham but invoice in Kg. Keep empty to use the default UOM.'),
        'uos_coeff': fields.float('UOM -> UOS Coeff', digits=(16,4),
                                  help='Coefficient to convert UOM to UOS\n'
                                  ' uos = uom * coeff'),
        'mes_type': fields.selection((('fixed', 'Fixed'), ('variable', 'Variable')), 'Measure Type', required=True),
        'seller_delay': fields.function(_calc_seller, method=True, type='integer', string='Supplier Lead Time', multi="seller_delay", help="This is the average delay in days between the purchase order confirmation and the reception of goods for this product and for the default supplier. It is used by the scheduler to order requests based on reordering delays."),
        'seller_qty': fields.function(_calc_seller, method=True, type='float', string='Supplier Quantity', multi="seller_qty", help="This is minimum quantity to purchase from Main Supplier.", related_uom='uom_id'),
        'seller_id': fields.function(_calc_seller, method=True, type='many2one', relation="res.partner", string='Main Supplier', help="Main Supplier who has highest priority in Supplier List.", multi="seller_id"),
        'seller_ids': fields.one2many('product.supplierinfo', 'product_id', 'Partners'),
        'loc_rack': fields.char('Rack', size=16),
        'loc_row': fields.char('Row', size=16),
        'loc_case': fields.char('Case', size=16),
        'company_id': fields.many2one('res.company', 'Company',select=1),
    }

    def _get_uom_id(self, cr, uid, *args):
        cr.execute('select id from product_uom order by id limit 1')
        res = cr.fetchone()
        return res and res[0] or False

    def _default_category(self, cr, uid, context=None):
        if context is None:
            context = {}
        if 'categ_id' in context and context['categ_id']:
            return context['categ_id']
        md = self.pool.get('ir.model.data')
        res = md.get_object_reference(cr, uid, 'product', 'cat0') or False
        return res and res[1] or False

    def onchange_uom(self, cursor, user, ids, uom_id,uom_po_id):
        res = {
            'value': {
                'soq_quantity': 0.00,
            }
        }
        if uom_id:
            res['value']['uom_po_id'] = uom_id

        return res

    _defaults = {
        'company_id': lambda s,cr,uid,c: s.pool.get('res.company')._company_default_get(cr, uid, 'product.template', context=c),
        'list_price': lambda *a: 1,
        'cost_method': lambda *a: 'average',
        'supply_method': lambda *a: 'buy',
        'standard_price': lambda *a: 1,
        'sale_ok': lambda *a: 1,
        'sale_delay': lambda *a: 7,
        'produce_delay': lambda *a: 1,
        'purchase_ok': lambda *a: 1,
        'procure_method': lambda *a: 'make_to_stock',
        'uom_id': _get_uom_id,
        'uom_po_id': _get_uom_id,
        'uos_coeff' : lambda *a: 1.0,
        'mes_type' : lambda *a: 'fixed',
        'categ_id' : _default_category,
        'type' : lambda *a: 'consu',
        'volume_updated': False,
    }

    def _check_uom(self, cursor, user, ids, context=None):
        for product in self.browse(cursor, user, ids, context=context,
                                   fields_to_fetch=['uom_id', 'uom_po_id']):
            if product.uom_id.category_id.id <> product.uom_po_id.category_id.id:
                return False
        return True

    def _check_uos(self, cursor, user, ids, context=None):
        for product in self.browse(cursor, user, ids, context=context,
                                   fields_to_fetch=['uos_id', 'uom_id']):
            if product.uos_id \
                    and product.uos_id.category_id.id \
                    == product.uom_id.category_id.id:
                return False
        return True

    _constraints = [
        (_check_uom, 'Error: The default UOM and the purchase UOM must be in the same category.', ['uom_id']),
    ]

    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if 'partner_id' in context:
            pass
        return super(product_template, self).name_get(cr, user, ids, context)

product_template()

class product_product(osv.osv):
    def _generate_order_by(self, order_spec, query, context=None):
        if context is None:
            context = {}
        order_by_clause = super(product_product, self)._generate_order_by(order_spec, query, context=context)

        if context.get('history_cons') and context.get('obj_id') and order_spec:
            for order in order_spec.split(','):
                order_detail = order.strip().split(' ')
                if order_detail[0] == 'average' or re.match('[0-9]{2}_[0-9]{4}$', order_detail[0]):
                    if len(order_detail) == 1:
                        spec = 'ASC'
                    else:
                        spec = order_detail[1]
                    query.joins.setdefault('"product_product"', [])
                    query.tables.append('"product_history_consumption_product" phcp')
                    query.joins['"product_product"'] += [('"product_history_consumption_product" phcp', 'id', "product_id", 'LEFT JOIN')]
                    query.where_clause.append(''' phcp.name=%s AND phcp.consumption_id=%s ''')
                    query.where_clause_params += [order_detail[0], context.get('obj_id')]
                    order_by_clause = ('ORDER BY "phcp"."value" %s' % spec, [])
                    if query.having:
                        query.having_group_by = '%s, %s' % (query.having_group_by, '"phcp"."value"')
        return order_by_clause

    def _where_calc(self, cr, uid, domain, active_test=True, context=None):
        if context is None:
            context = {}
        new_dom = []
        location_id = False
        filter_qty = False
        filter_average = False
        cond_average = '>'
        filter_in_any_product_list = False
        filter_in_product_list = False
        filter_in_mml_instance = False
        filter_in_msl_instance = []
        for x in domain:
            if x[0] == 'location_id':
                location_id = x[2]

            elif x[0] == 'postive_qty':
                filter_qty = True

            elif x[0] == 'in_any_product_list':
                filter_in_any_product_list = True

            elif x[0] == 'in_product_list':
                filter_in_product_list = x[2]

            elif x[0] == 'in_mml_instance':
                if x[2] is True:
                    local_instance = self.pool.get('res.company')._get_instance_record(cr, uid)
                    if local_instance.level == 'section':
                        new_dom.append(['id', '=', 0])
                    else:
                        filter_in_mml_instance = [local_instance.id]
                else:
                    if isinstance(x[2], basestring):
                        instance_ids = self.pool.get('msf.instance').search(cr, uid, [('name', 'ilike', x[2])], context=context)
                    elif isinstance(x[2], (int, long)):
                        instance_ids = [x[2]]
                    else:
                        instance_ids = x[2]

                    if self.pool.get('msf.instance').search_exists(cr, uid, [('id', 'in', instance_ids), ('level', '=', 'section')], context=context):
                        new_dom.append(['id', '=', 0])
                    else:
                        filter_in_mml_instance = instance_ids


            elif x[0] == 'in_msl_instance':
                if x[2] is True:
                    t_filter_in_msl_instance = -1
                    instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)
                    ud_project_ids = self.pool.get('unidata.project').search(cr, uid, [('instance_id', '=', instance_id)], context=context)
                    if ud_project_ids:
                        t_filter_in_msl_instance = ud_project_ids[0]
                    if not filter_in_msl_instance:
                        filter_in_msl_instance.append(t_filter_in_msl_instance)
                elif isinstance(x[2], basestring):
                    filter_in_msl_instance = self.pool.get('unidata.project').search(cr, uid, [('instance_id.name', 'ilike', x[2])], context=context)
                    if not filter_in_msl_instance:
                        filter_in_msl_instance = [0]
                else:
                    filter_in_msl_instance = self.pool.get('unidata.project').search(cr, uid, [('unifield_instance_id', '=', x[2])], context=context)

            elif x[0] == 'average':
                if context.get('history_cons') and context.get('obj_id'):
                    filter_average = context['obj_id']
                    if x[1] == '!=':
                        cond_average = '!='
            else:
                new_dom.append(x)

        ret = super(product_product, self)._where_calc(cr, uid, new_dom, active_test=active_test, context=context)
        if filter_qty:
            stock_location_obj = self.pool.get('stock.location')
            if not location_id:
                default_locs_domain = ['|', ('eprep_location', '=', True), '&', ('usage', '=', 'internal'),
                                       ('location_category', 'in', ('stock', 'consumption_unit', 'eprep'))]
                location_id = stock_location_obj.search(cr, uid, default_locs_domain, context=context)

            if isinstance(location_id, basestring):
                location_id = stock_location_obj.search(cr, uid, [('name','ilike', location_id)], context=context)

            if not isinstance(location_id, list):
                location_id = [location_id]

            child_location_ids = stock_location_obj.search(cr, uid, [('location_id', 'child_of', location_id)], order='NO_ORDER')
            location_ids = child_location_ids or location_id
            ret.tables.append('"stock_mission_report_line_location"')
            ret.joins.setdefault('"product_product"', [])
            ret.joins['"product_product"'] += [('"stock_mission_report_line_location"', 'id', 'product_id', 'LEFT JOIN')]
            ret.where_clause.append(' "stock_mission_report_line_location"."remote_instance_id" is NULL AND "stock_mission_report_line_location"."location_id" in %s ')
            ret.where_clause_params.append(tuple(location_ids))
            ret.having_group_by = ' GROUP BY "product_product"."id" '
            ret.having = ' HAVING sum("stock_mission_report_line_location"."quantity") >0 '
        if filter_in_any_product_list:
            ret.tables.append('"product_list_line"')
            ret.joins.setdefault('"product_product"', [])
            ret.joins['"product_product"'] += [('"product_list_line"', 'id', 'name', 'INNER JOIN')]
        if filter_in_product_list:
            ret.tables.append('"product_list_line"')
            ret.joins.setdefault('"product_product"', [])
            ret.joins['"product_product"'] += [('"product_list_line"', 'id', 'name', 'INNER JOIN')]
            ret.where_clause.append(''' "product_list_line"."list_id" = %s  ''')
            ret.where_clause_params.append(filter_in_product_list)
        if filter_average:
            ret.tables.append('"product_history_consumption_product" phc1')
            ret.joins.setdefault('"product_product"', [])
            ret.joins['"product_product"'] += [('"product_history_consumption_product" phc1', 'id', 'product_id', 'INNER JOIN')]
            ret.where_clause.append(''' "phc1"."consumption_id" = %%s and "phc1"."name" = 'average' and "phc1"."value" %s 0 ''' % (cond_average, ))
            ret.where_clause_params.append(filter_average)
        if filter_in_mml_instance:
            ret.tables.append('"product_project_rel" p_rel')
            ret.joins.setdefault('"product_product"', [])
            ret.joins['"product_product"'] += [('"product_project_rel" p_rel', 'id', 'product_id', 'LEFT JOIN')]
            ret.joins['"product_product"'] += ['left join product_country_rel c_rel on p_rel is null and c_rel.product_id = product_product.id']
            ret.joins['"product_product"'] += ['left join unidata_project up1 on up1.id = p_rel.unidata_project_id or up1.country_id = c_rel.unidata_country_id']
            ret.where_clause.append(''' product_product.oc_validation = 't' and ( up1.instance_id in %s or up1 is null) ''')
            ret.where_clause_params.append(tuple(filter_in_mml_instance))
        if filter_in_msl_instance:
            ret.tables.append('"product_msl_rel"')
            ret.joins.setdefault('"product_product"', [])
            ret.joins.setdefault('"product_msl_rel"', [])
            ret.joins['"product_product"'] += [('"product_msl_rel"', 'id', 'product_id', 'INNER JOIN')]
            ret.joins['"product_product"'] += ["inner join unidata_project on unidata_project.id=product_msl_rel.msl_id"]
            ret.where_clause.append(''' "product_msl_rel".creation_date is not null and  "unidata_project".uf_active = 't' and "unidata_project".id in %s  ''')
            ret.where_clause_params.append(tuple(filter_in_msl_instance))
            ret.having_group_by = ' GROUP BY "product_product"."id" '

        return ret

    def view_header_get(self, cr, uid, view_id, view_type, context=None):
        if context is None:
            context = {}
        res = super(product_product, self).view_header_get(cr, uid, view_id, view_type, context)
        if (context.get('categ_id', False)):
            return _('Products: ')+self.pool.get('product.category').browse(cr, uid, context['categ_id'], context=context).name
        return res

    def _product_price(self, cr, uid, ids, name, arg, context=None):
        res = {}
        if context is None:
            context = {}
        quantity = context.get('quantity') or 1.0
        pricelist = context.get('pricelist', False)
        if pricelist:
            for id in ids:
                try:
                    price = self.pool.get('product.pricelist').price_get(cr,uid,[pricelist], id, quantity, context=context)[pricelist]
                except:
                    price = 0.0
                res[id] = price
        for id in ids:
            res.setdefault(id, 0.0)
        return res

    def _get_product_available_func(states, what):
        def _product_available(self, cr, uid, ids, name, arg, context=None):
            return {}.fromkeys(ids, 0.0)
        return _product_available

    _product_qty_available = _get_product_available_func(('done',), ('in', 'out'))
    _product_virtual_available = _get_product_available_func(('confirmed','waiting','assigned','done'), ('in', 'out'))
    _product_outgoing_qty = _get_product_available_func(('confirmed','waiting','assigned'), ('out',))
    _product_incoming_qty = _get_product_available_func(('confirmed','waiting','assigned'), ('in',))

    def _product_lst_price(self, cr, uid, ids, name, arg, context=None):
        res = {}
        product_uom_obj = self.pool.get('product.uom')
        for id in ids:
            res.setdefault(id, 0.0)
        for product in self.browse(cr, uid, ids, context=context,
                                   fields_to_fetch=['uos_id', 'id', 'uom_id', 'list_price',
                                                    'price_margin', 'price_extra']):
            if 'uom' in context:
                uom = product.uos_id or product.uom_id
                res[product.id] = product_uom_obj._compute_price(cr, uid,
                                                                 uom.id, product.list_price, context['uom'])
            else:
                res[product.id] = product.list_price
            res[product.id] =  (res[product.id] or 0.0) * (product.price_margin or 1.0) + product.price_extra
        return res

    def _get_partner_code(self, cr, uid, ids, partner_id, context=None):
        '''
        Get partner code for each product id in ids.
        @param ids: Ids of product.
        @param partner_id: Id of partner.
        :return: dict with ids in keys and partner codes as values
        '''
        res = {}
        if ids is not None:
            fields_to_read = ['default_code']
            if partner_id:
                fields_to_read.append('seller_ids')
            read_result = self.read(cr, uid, ids, fields_to_read, context=context)
            res = dict([(x['id'], x['default_code']) for x in read_result])
            if not partner_id:
                return dict([(x['id'], x['default_code']) for x in read_result])
            for elem in read_result:
                if not elem['seller_ids']:
                    res[elem['id']] = elem['default_code']
                else:
                    supplierinfo_module = self.pool.get('product.supplierinfo')
                    if partner_id in elem['seller_ids']:
                        res[elem['id']] = supplierinfo_module.read(cr, uid, partner_id, ['product_code'], context=context)['product_code'] or elem['default_code']
        return res

    def _get_partner_code_name(self, cr, uid, ids, partner_id, context=None):
        '''
        Get partner code, name and variants for each product id in ids.
        @param ids: Ids of product.
        @param partner_id: Id of partner.
        :return: dict with ids in keys and a dict with code, name and variants
        as values
        '''
        res = {}
        if ids is not None:
            read_result = self.read(cr, uid, ids, ['seller_ids', 'default_code', 'name', 'variants'], context=context)
            for elem in read_result:
                if not elem['seller_ids'] or not partner_id:
                    res[elem['id']] = {
                        'code': elem['default_code'],
                        'name': elem['name'],
                        'variants': elem['variants'],
                    }
                else:
                    supplierinfo_module = self.pool.get('product.supplierinfo')
                    for seller_id in elem['seller_ids']:
                        if seller_id == partner_id:
                            supplierinfo = supplierinfo_module.read(cr, uid, seller_id, ['product_code', 'product_name'], context=context)
                            res[elem['id']] = {
                                'code': supplierinfo and supplierinfo['product_code'] or elem['default_code'],
                                'name': supplierinfo and supplierinfo['product_name'] or elem['name'],
                                'variants': elem['variants'],
                            }
        return res

    def _product_code(self, cr, uid, ids, name, arg, context=None):
        if context is None:
            context = {}
        partner_id = context.get('partner_id', None)
        return self._get_partner_code(cr, uid, ids, partner_id, context=context)

    def _product_partner_ref(self, cr, uid, ids, name, arg, context=None):
        res = {}
        if context is None:
            context = {}
        partner_id = context.get('partner_id', None)
        code_names_dict = self._get_partner_code_name(cr, uid, ids, partner_id, context=context)
        for product_id, data in code_names_dict.items():
            res[product_id] = (data['code'] and ('['+data['code']+'] ') or '') + \
                (data['name'] or '') + (data['variants'] and (' - '+data['variants']) or '')
        return res

    def _get_authorized_creator(self, cr, uid, check_edbn, context=None):
        obj_data = self.pool.get('ir.model.data')
        instance_level = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id.level
        prod_creator = []
        if instance_level == 'section':
            # ITC, ESC, HQ
            prod_creator.append(obj_data.get_object_reference(cr, uid, 'product_attributes', 'int_1')[1])
            prod_creator.append(obj_data.get_object_reference(cr, uid, 'product_attributes', 'int_2')[1])
            prod_creator.append(obj_data.get_object_reference(cr, uid, 'product_attributes', 'int_3')[1])
            if check_edbn:
                # Local, UD
                prod_creator.append(obj_data.get_object_reference(cr, uid, 'product_attributes', 'int_4')[1])
                prod_creator.append(obj_data.get_object_reference(cr, uid, 'product_attributes', 'int_6')[1])
        elif instance_level == 'coordo':
            prod_creator = [obj_data.get_object_reference(cr, uid, 'product_attributes', 'int_4')[1]]
        return prod_creator

    def _get_expected_prod_creator(self, cr, uid, ids, field_names, arg, context=None):
        if context is None:
            context = {}

        res = {}
        prod_creator = self._get_authorized_creator(cr, uid, check_edbn=True, context=context)
        for _id in ids:
            res[_id] = False

        if prod_creator:
            for _id in self.search(cr, uid, [('id', 'in', ids), ('international_status', 'in', prod_creator)], context=context):
                res[_id] = True
        return res

    def _expected_prod_creator_search(self, cr, uid, obj, name, args, context=None):
        '''
        Returns all documents according to the product creator
        '''
        if context is None:
            context = {}

        prod_creator_ids = []
        for arg in args:
            if arg[0] == 'expected_prod_creator':
                prod_creator_ids = self._get_authorized_creator(cr, uid, arg[2]=='bned', context)

        if arg[2]!='bned':
            return [('international_status', 'in', prod_creator_ids), ('replaced_by_product_id', '=', False)]
        return [('international_status', 'in', prod_creator_ids)]

    _defaults = {
        'active': lambda *a: True,
        'price_extra': lambda *a: 0.0,
        'price_margin': lambda *a: 1.0,
    }

    _name = "product.product"
    _description = "Product"
    _table = "product_product"
    _inherits = {'product.template': 'product_tmpl_id'}
    _order = 'default_code,name_template'
    _columns = {
        'qty_available': fields.function(_product_qty_available, method=True, type='float', string='Real Stock', related_uom='uom_id'),
        'virtual_available': fields.function(_product_virtual_available, method=True, type='float', string='Virtual Stock', related_uom='uom_id'),
        'incoming_qty': fields.function(_product_incoming_qty, method=True, type='float', string='Incoming', related_uom='uom_id'),
        'outgoing_qty': fields.function(_product_outgoing_qty, method=True, type='float', string='Outgoing', related_uom='uom_id'),
        'price': fields.function(_product_price, method=True, type='float', string='Pricelist', digits_compute=dp.get_precision('Sale Price')),
        'lst_price' : fields.function(_product_lst_price, method=True, type='float', string='Public Price', digits_compute=dp.get_precision('Sale Price')),
        'code': fields.function(_product_code, method=True, type='char', string='Reference'),
        'partner_ref' : fields.function(_product_partner_ref, method=True, type='char', string='Customer ref'),
        'default_code' : fields.char('Reference', size=64),
        'active': fields.boolean('Active', help="If the active field is set to False, it will allow you to hide the product without removing it.", select=True),
        'variants': fields.char('Variants', size=64),
        'product_tmpl_id': fields.many2one('product.template', 'Product Template', required=True, ondelete="cascade", select=True),
        'ean13': fields.char('EAN13', size=13),
        'packaging' : fields.one2many('product.packaging', 'product_id', 'Logistical Units', help="Gives the different ways to package the same product. This has no impact on the picking order and is mainly used if you use the EDI module."),
        'price_extra': fields.float('Variant Price Extra', digits_compute=dp.get_precision('Sale Price')),
        'price_margin': fields.float('Variant Price Margin', digits_compute=dp.get_precision('Sale Price')),
        'pricelist_id': fields.dummy(string='Pricelist', relation='product.pricelist', type='many2one'),
        'name_template': fields.related('product_tmpl_id', 'name', string="Name", type='char', size=128, store=True, write_relate=False),
        'expected_prod_creator': fields.function(_get_expected_prod_creator, method=True, type='boolean', fnct_search=_expected_prod_creator_search, readonly=True, string='Expected Product Creator for Product Mass Update'),
    }

    def unlink(self, cr, uid, ids, context=None):
        unlink_ids = []
        unlink_product_tmpl_ids = []
        for product in self.browse(cr, uid, ids, context=context,
                                   fields_to_fetch=['product_tmpl_id', 'id']):
            tmpl_id = product.product_tmpl_id.id
            # Check if the product is last product of this template
            other_product_ids = self.search(cr, uid, [('product_tmpl_id', '=',
                                                       tmpl_id), ('id', '!=', product.id)], limit=1, order='NO_ORDER',
                                            context=context)
            if not other_product_ids:
                unlink_product_tmpl_ids.append(tmpl_id)
            unlink_ids.append(product.id)
        self.pool.get('product.template').unlink(cr, uid, unlink_product_tmpl_ids, context=context)
        return super(product_product, self).unlink(cr, uid, unlink_ids, context=context)

    def onchange_uom(self, cursor, user, ids, uom_id,uom_po_id):
        res = {
            'value': {
            },
        }
        if uom_id:
            res['value']['soq_quantity'] = 0.00

        if uom_id and uom_po_id:
            uom_obj=self.pool.get('product.uom')
            uom=uom_obj.browse(cursor,user,[uom_id],
                               fields_to_fetch=['category_id'])[0]
            uom_po=uom_obj.browse(cursor,user,[uom_po_id],
                                  fields_to_fetch=['category_id'])[0]
            if uom.category_id.id != uom_po.category_id.id:
                res['value']['uom_po_id'] = uom_id
        return res

    def _check_ean_key(self, cr, uid, ids, context=None):
        for product in self.read(cr, uid, ids, ['ean13'], context=context):
            res = check_ean(product['ean13'])
        return res

    _constraints = [(_check_ean_key, 'Error: Invalid ean code', ['ean13'])]

    def on_order(self, cr, uid, ids, orderline, quantity):
        pass


    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        if not args:
            args=[]
        if name:
            ids = self.search(cr, user, [('default_code','=',name)]+ args, limit=limit, context=context)
            if not len(ids):
                ids = self.search(cr, user, [('ean13','=',name)]+ args, limit=limit, context=context)
            if not len(ids):
                ids = self.search(cr, user, ['|',('name',operator,name),('default_code',operator,name)] + args, limit=limit, context=context)
            if not len(ids):
                ptrn=re.compile('(\[(.*?)\])')
                res = ptrn.search(name)
                if res:
                    ids = self.search(cr, user, [('default_code','=', res.group(2))] + args, limit=limit, context=context)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context)
        result = self.name_get(cr, user, ids, context=context)
        return result

    #
    # Could be overrided for variants matrices prices
    #
    def price_get(self, cr, uid, ids, ptype='list_price', context=None):
        if context is None:
            context = {}

        if 'currency_id' in context:
            pricetype_obj = self.pool.get('product.price.type')
            price_type_id = pricetype_obj.search(cr, uid, [('field','=',ptype)])[0]
            price_type_currency_id = pricetype_obj.browse(cr,uid,price_type_id,
                                                          fields_to_fetch=['currency_id']).currency_id.id

        res = {}
        product_uom_obj = self.pool.get('product.uom')
        for product in self.browse(cr, uid, ids, fields_to_fetch=['price_margin', 'price_extra', 'uom_id', 'uos_id', ptype], context=context):
            res[product.id] = product[ptype] or 0.0
            if ptype == 'list_price':
                res[product.id] = (res[product.id] * (product.price_margin or 1.0)) + \
                    product.price_extra
            if 'uom' in context:
                uom = product.uos_id or product.uom_id
                res[product.id] = product_uom_obj._compute_price(cr, uid,
                                                                 uom.id, res[product.id], context['uom'])
            # Convert from price_type currency to asked one
            if 'currency_id' in context:
                # Take the price_type currency from the product field
                # This is right cause a field cannot be in more than one currency
                res[product.id] = self.pool.get('res.currency').compute(cr, uid, price_type_currency_id,
                                                                        context['currency_id'], res[product.id], round=False, context=context)

        return res

    def copy(self, cr, uid, id, default=None, context=None):
        if context is None:
            context={}

        product = self.read(cr, uid, id, ['name'], context=context)
        if not default:
            default = {}
        default = default.copy()
        default['name'] = product['name'] + _(' (copy)')

        if context.get('variant',False):
            fields = ['product_tmpl_id', 'active', 'variants', 'default_code',
                      'price_margin', 'price_extra']
            data = self.read(cr, uid, id, fields=fields, context=context)
            for f in fields:
                if f in default:
                    data[f] = default[f]
            data['product_tmpl_id'] = data.get('product_tmpl_id', False) \
                and data['product_tmpl_id'][0]
            del data['id']
            return self.create(cr, uid, data)
        else:
            return super(product_product, self).copy(cr, uid, id, default=default,
                                                     context=context)

    def is_field_translatable(self, cr, uid, context=None):
        if context is None:
            context = {}

        lang_obj = self.pool.get('res.lang')

        active_lang_ids = lang_obj.search(cr, uid, [('active', '=', True), ('translatable', '=', True)], context=context)
        if len(active_lang_ids) > 1:
            return False

        return True

    def onchange_sp(self, cr, uid, ids, standard_price, context=None):
        '''
        On change standard_price, update the list_price = Field Price according to standard_price = Cost Price and the sale_price of the unifield_setup_configuration
        '''
        res = {}
        if standard_price :
            if standard_price < 0.0:
                warn_msg = {
                    'title': _('Warning'),
                    'message': _("The Cost Price must be greater than 0 !")
                }
                res.update({'warning': warn_msg,
                            'value': {'standard_price': 1,
                                      'list_price': self.onchange_sp(cr, uid, ids, standard_price=1, context=context).get('value').get('list_price')}})
            else:
                setup_obj = self.pool.get('unifield.setup.configuration')
                #US-1035: Fixed the wrong hardcoded id given when calling config setup object
                setup_br = setup_obj.get_config(cr, uid)
                if not setup_br:
                    return res

                percentage = setup_br.sale_price
                list_price = standard_price * (1 + (percentage/100.00))
                if 'value' in res:
                    res['value'].update({'list_price': list_price})
                else:
                    res.update({'value': {'list_price': list_price}})
        return res

    def view_docs_with_product(self, cr, uid, ids, menu_action, context=None):
        '''
        Get info from the given menu action to return the right view with the right data
        '''

        if context is None:
            context = {}

        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, menu_action, ['tree', 'form'], new_tab=True, context=context)

        res_context = res.get('context', False) and safe_eval(res['context']) or {}
        for col in res_context:  # Remove the default filters
            if 'search_default_' in col:
                res_context[col] = False
        res_context['search_default_product_id'] = context.get('active_id', False)
        res['context'] = res_context

        return res

    def get_products_mml_status(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if not ids:
            return {}

        ret = {}
        for _id in ids:
            ret[_id] = {'mml_status': 'F', 'msl_status': False}

        local_instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)

        # MSL Checks
        cr.execute('''
            select
                p.id, unidata_project.uf_active, msl_rel.product_id
            from
                product_product p
                left join product_template tmpl on tmpl.id = p.product_tmpl_id
                left join product_international_status creator on creator.id = p.international_status
                left join product_nomenclature nom on tmpl.nomen_manda_0 = nom.id
                left join unidata_project on unidata_project.instance_id = %s
                left join product_msl_rel msl_rel on msl_rel.product_id = p.id and msl_rel.creation_date is not null and unidata_project.id = msl_rel.msl_id
            where
                nom.name='MED'
                and creator.code = 'unidata'
                and p.id in %s
        ''', (local_instance_id, tuple(ids)))

        for x in cr.fetchall():
            if not x[1]:  # unidata_project.uf_active
                ret[x[0]]['msl_status'] = False
            elif x[2]:  # msl_rel.product_id
                ret[x[0]]['msl_status'] = 'T'
            else:
                ret[x[0]]['msl_status'] = 'F'

        cr.execute('''
            select
                p.id
            from
                product_product p
                left join product_template tmpl on tmpl.id = p.product_tmpl_id
                left join product_international_status creator on creator.id = p.international_status
                left join product_nomenclature nom on tmpl.nomen_manda_0 = nom.id
            where
                ( nom.name!='MED' or creator.code != 'unidata' )
                and p.id in %s
        ''', (tuple(ids), ))
        for x in cr.fetchall():
            ret[x[0]]['mml_status'] = False

        # MML Checks
        cr.execute('''
            select
                p.id
            from
                product_product p
                left join product_template tmpl on tmpl.id = p.product_tmpl_id
                left join product_international_status creator on creator.id = p.international_status
                left join product_nomenclature nom on tmpl.nomen_manda_0 = nom.id
                left join product_project_rel p_rel on p_rel.product_id = p.id
                left join product_country_rel c_rel on p_rel is null and c_rel.product_id = p.id
                left join unidata_project up1 on up1.id = p_rel.unidata_project_id or up1.country_id = c_rel.unidata_country_id
            where
                nom.name='MED'
                and creator.code = 'unidata'
                and p.oc_validation = 't'
                and (up1.instance_id = %s or up1 is null)
                and p.id in %s
        ''', (local_instance_id, tuple(ids)))
        for x in cr.fetchall():
            ret[x[0]]['mml_status'] = 'T'
        return ret


product_product()


class product_packaging(osv.osv):
    _name = "product.packaging"
    _description = "Packaging"
    _rec_name = 'ean'
    _order = 'sequence'
    _columns = {
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying a list of packaging."),
        'name' : fields.text('Description', size=64),
        'qty' : fields.float('Quantity by Package',
                             help="The total number of products you can put by pallet or box."),
        'ul' : fields.many2one('product.ul', 'Type of Package', required=True),
        'ul_qty' : fields.integer('Package by layer', help='The number of packages by layer'),
        'rows' : fields.integer('Number of Layers', required=True,
                                help='The number of layers on a pallet or box'),
        'product_id' : fields.many2one('product.product', 'Product', select=1, ondelete='cascade', required=True),
        'ean' : fields.char('EAN', size=14,
                            help="The EAN code of the package unit."),
        'code' : fields.char('Code', size=14,
                             help="The code of the transport unit."),
        'weight': fields.float('Total Package Weight',
                               help='The weight of a full package, pallet or box.'),
        'weight_ul': fields.float('Empty Package Weight',
                                  help='The weight of the empty UL'),
        'height': fields.float('Height', help='The height of the package'),
        'width': fields.float('Width', help='The width of the package'),
        'length': fields.float('Length', help='The length of the package'),
    }


    def _check_ean_key(self, cr, uid, ids, context=None):
        for pack in self.browse(cr, uid, ids, context=context,
                                fields_to_fetch=['ean']):
            res = check_ean(pack.ean)
        return res

    _constraints = [(_check_ean_key, 'Error: Invalid ean code', ['ean'])]

    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        res = []
        for pckg in self.browse(cr, uid, ids, context=context,
                                fields_to_fetch=['ean', 'ul', 'id']):
            p_name = pckg.ean and '[' + pckg.ean + '] ' or ''
            p_name += pckg.ul.name
            res.append((pckg.id,p_name))
        return res

    def _get_1st_ul(self, cr, uid, context=None):
        cr.execute('select id from product_ul order by id asc limit 1')
        res = cr.fetchone()
        return (res and res[0]) or False

    _defaults = {
        'rows' : lambda *a : 3,
        'sequence' : lambda *a : 1,
        'ul' : _get_1st_ul,
    }

    def checksum(ean):
        salt = '31' * 6 + '3'
        sum = 0
        for ean_part, salt_part in zip(ean, salt):
            sum += int(ean_part) * int(salt_part)
        return (10 - (sum % 10)) % 10
    checksum = staticmethod(checksum)

product_packaging()


class product_supplierinfo(osv.osv):
    _name = "product.supplierinfo"
    _description = "Information about a product supplier"
    def _calc_qty(self, cr, uid, ids, fields, arg, context=None):
        result = {}
        product_uom_pool = self.pool.get('product.uom')
        for supplier_info in self.browse(cr, uid, ids, context=context,
                                         fields_to_fetch=['id', 'product_uom', 'min_qty', 'product_id']):
            for field in fields:
                result[supplier_info.id] = {field:False}
            if supplier_info.product_uom.id:
                qty = product_uom_pool._compute_qty(cr, uid, supplier_info.product_uom.id, supplier_info.min_qty, to_uom_id=supplier_info.product_id.uom_id.id)
            else:
                qty = supplier_info.min_qty
            result[supplier_info.id]['qty'] = qty
        return result

    def _get_uom_id(self, cr, uid, *args):
        cr.execute('select id from product_uom order by id limit 1')
        res = cr.fetchone()
        return res and res[0] or False

    def _get_seller_delay(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the supplier lt
        '''
        res = {}
        for price in self.browse(cr, uid, ids, context=context):
            product_id = self.pool.get('product.product').search(cr, uid, [('product_tmpl_id', '=', price.id)])
            product = self.pool.get('product.product').browse(cr, uid, product_id)
            res[price.id] = (price.name and price.name.supplier_lt) or (product_id and int(product[0].procure_delay)) or 1

        return res

    _columns = {
        'name' : fields.many2one('res.partner', 'Supplier', required=True,domain = [('supplier','=',True)], ondelete='cascade', help="Supplier of this product", select=True),
        'product_name': fields.char('Supplier Product Name', size=128, help="This supplier's product name will be used when printing a request for quotation. Keep empty to use the internal one."),
        'product_code': fields.char('Supplier Product Code', size=64, help="This supplier's product code will be used when printing a request for quotation. Keep empty to use the internal one."),
        'sequence' : fields.integer('Sequence', help="Assigns the priority to the list of product supplier."),
        'product_uom': fields.related('product_id', 'uom_id', string="Supplier UoM", type='many2one', relation='product.uom', help="Choose here the Unit of Measure in which the prices and quantities are expressed below.", write_relate=False),
        'min_qty': fields.float('Minimal Quantity', required=False, help="The minimal quantity to purchase to this supplier, expressed in the supplier Product UoM if not empty, in the default unit of measure of the product otherwise.", related_uom='product_uom'),
        'qty': fields.function(_calc_qty, method=True, store=True, type='float', string='Quantity', multi="qty", help="This is a quantity which is converted into Default Uom.", related_uom='product_uom'),
        'product_id' : fields.many2one('product.template', 'Product', required=True, ondelete='cascade', select=True),
        'delay': fields.function(_get_seller_delay, method=True, type='integer', string='Indicative Delivery LT', help='Lead time in days between the confirmation of the purchase order and the reception of the products in your warehouse. Used by the scheduler for automatic computation of the purchase order planning.'),
        'pricelist_ids': fields.one2many('pricelist.partnerinfo', 'suppinfo_id', 'Supplier Pricelist'),
        'company_id':fields.many2one('res.company','Company',select=1),
    }
    _defaults = {
        'qty': lambda *a: 0.0,
        'sequence': lambda *a: 1,
        'delay': lambda *a: 1,
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'product.supplierinfo', context=c),
        'product_uom': _get_uom_id,
    }
    def _check_uom(self, cr, uid, ids, context=None):
        for supplier_info in self.browse(cr, uid, ids, context=context,
                                         fields_to_fetch=['product_uom',
                                                          'product_id']):
            if supplier_info.product_uom and supplier_info.product_uom.category_id.id <> supplier_info.product_id.uom_id.category_id.id:
                return False
        return True

    _constraints = [
        (_check_uom, 'Error: The default UOM and the Supplier Product UOM must be in the same category.', ['product_uom']),
    ]
    _order = 'sequence'
product_supplierinfo()


class pricelist_partnerinfo(osv.osv):
    _name = 'pricelist.partnerinfo'
    _columns = {
        'name': fields.char('Description', size=64),
        'suppinfo_id': fields.many2one('product.supplierinfo', 'Partner Information', required=True, ondelete='cascade', select=True),
        'min_quantity': fields.float('Quantity', required=True, help="The minimal quantity to trigger this rule, expressed in the supplier UoM if any or in the default UoM of the product otherrwise.", related_uom='uom_id'),
        'price': fields.float('Unit Price', required=True, digits_compute=dp.get_precision('Purchase Price'), help="This price will be considered as a price for the supplier UoM if any or the default Unit of Measure of the product otherwise"),
    }
    _order = 'min_quantity asc'
pricelist_partnerinfo()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
