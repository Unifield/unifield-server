# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF 
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

from tools.translate import _
from mx.DateTime import DateFrom
from mx.DateTime import RelativeDate
from mx.DateTime import now

import time

class stock_warehouse_order_cycle(osv.osv):
    _name = 'stock.warehouse.order.cycle'
    _description = 'Order Cycle'
    _order = 'name, id'

    def create(self, cr, uid, data, context=None):
        '''
        Checks if a frequence was choosen for the cycle
        '''
        if context is None:
            context = {}
        if not 'button' in context and (not 'frequence_id' in data or not data.get('frequence_id', False)):
            raise osv.except_osv(_('Error'), _('You should choose a frequence for this rule !'))

        return super(stock_warehouse_order_cycle, self).create(cr, uid, data, context=context)

    def write(self, cr, uid, ids, data, context=None):
        '''
        Checks if a frequence was choosen for the cycle
        '''
        if not ids:
            return True
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if data.get('sublist_id', False):
            data.update({'nomen_manda_0': False, 'nomen_manda_1': False, 'nomen_manda_2': False, 'nomen_manda_3': False})
        if data.get('nomen_manda_0', False):
            data.update({'sublist_id': False})
        if not 'button' in context and (not 'frequence_id' in data or not data.get('frequence_id', False)):
            for proc in self.browse(cr, uid, ids):
                if not proc.frequence_id:
                    raise osv.except_osv(_('Error'), _('You should choose a frequence for this rule !')) 

        return super(stock_warehouse_order_cycle, self).write(cr, uid, ids, data, context=context)


    def _get_frequence_change(self, cr, uid, ids, context=None):
        '''
        Returns ids when the frequence change
        '''
        res = {}
        for frequence in self.pool.get('stock.frequence').browse(cr, uid, ids, context=context):
            for cycle in frequence.order_cycle_ids:
                res[cycle.id] = True

        return res.keys()

    def _get_frequence_name(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns the name_get value of the frequence
        '''
        res = {}
        for proc in self.browse(cr, uid, ids):
            if proc.frequence_id:
                res[proc.id] = self.pool.get('stock.frequence').name_get(cr, uid, [proc.frequence_id.id], context=context)[0][1]

        return res

    def _get_product_ids(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns a list of products for the rule
        '''
        res = {}

        for rule in self.browse(cr, uid, ids, context=context):
            res[rule.id] = []
            for line in rule.product_ids:
                res[rule.id].append(line.product_id.id)

        return res

    def _src_product_ids(self, cr, uid, obj, name, args, context=None):
        if not context:
            context = {}

        res = []

        for arg in args:
            if arg[0] == 'product_line_ids':
                rule_ids = []
                line_ids = self.pool.get('stock.warehouse.order.cycle.line').search(cr, uid, [('product_id', arg[1], arg[2])])
                for l in self.pool.get('stock.warehouse.order.cycle.line').browse(cr, uid, line_ids):
                    if l.order_cycle_id.id not in rule_ids:
                        rule_ids.append(l.order_cycle_id.id)
                res.append(('id', 'in', rule_ids))

        return res

    _columns = {
        'sequence': fields.integer(string='Order', required=False, help='A higher order value means a low priority'),
        'name': fields.char(size=64, string='Reference', required=True),
        'category_id': fields.many2one('product.category', string='Category'),
        'product_id': fields.many2one('product.product', string='Specific product'),
        'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse', required=True),
        'location_id': fields.many2one('stock.location', 'Location', ondelete="cascade", required=True, 
                                       domain="[('is_replenishment', '=', warehouse_id)]",
                                       help='Location where the computation is made'),
        'frequence_name': fields.function(_get_frequence_name, method=True, string='Frequency', type='char', 
                                          help='Define the time between two replenishments'),
        'frequence_id': fields.many2one('stock.frequence', string='Frequency', help='It\'s the time between two replenishments'),
        'product_ids': fields.one2many('stock.warehouse.order.cycle.line', 'order_cycle_id', string='Products'),
        'company_id': fields.many2one('res.company','Company',required=True),
        'active': fields.boolean('Active', help="If the active field is set to False, it will allow you to hide the automatic supply without removing it."),
        # Parameters for quantity calculation
        'leadtime': fields.float(digits=(16,2), string='Delivery lead time to consider', help='Delivery lead time in month'),
        'order_coverage': fields.float(digits=(16,2), string='Order coverage', help='In months. \
Define the time between two replenishments. \
Time used to compute the quantity of products to order according to the monthly consumption.'),
        'safety_stock_time': fields.float(digits=(16,2), string='Safety stock in time', help='In months. \
Define the time while the stock is not negative but should be replenished. \
Time used to compute the quantity of products to order according to the monthly consumption.'),
        'past_consumption': fields.boolean(string='Average monthly consumption', 
                                           help='If checked, the system will used the average monthly consumption to compute the quantity to order'),
        'consumption_period_from': fields.date(string='Period of calculation', 
                                               help='This period is a number of past months the system has to consider for AMC calculation.'\
                                               'By default this value is equal to the order coverage of the rule.'),
        'consumption_period_to': fields.date(string='-'),
        'reviewed_consumption': fields.boolean(string='Forecasted monthly consumption', 
                                               help='If checked, the system will used the forecasted monthly consumption to compute the quantity to order'),
        'manual_consumption': fields.float(digits=(16,2), string='Manual monthly consumption',
                                           help='If not 0.00, the system will used the entered monthly consumption to compute the quantity to order'),
        'next_date': fields.related('frequence_id', 'next_date', string='Next scheduled date', readonly=True, type='date',
                                    help='As this date is not in the past, no new replenishment will be run', 
                                    store={'stock.warehouse.order.cycle': (lambda self, cr, uid, ids, context=None: ids, ['frequence_id'], 20),
                                           'stock.frequence': (_get_frequence_change, None, 20)}),
        'product_line_ids': fields.function(_get_product_ids, fnct_search=_src_product_ids, 
                                            type='many2many', relation='product.product', method=True, string='Products'),
        'sublist_id': fields.many2one('product.list', string='List/Sublist', ondelete='set null'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type', ondelete='set null'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group', ondelete='set null'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family', ondelete='set null'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root', ondelete='set null'),
    }

    _defaults = {
        'past_consumption': lambda *a: 1,
        'active': lambda *a: 1,
        'name': lambda x,y,z,c: x.pool.get('ir.sequence').get(y,z,'stock.order.cycle') or '',
        'order_coverage': lambda *a: 3,
    }

    def default_get(self, cr, uid, fields, context=None):
        '''
        Get the default values for the replenishment rule
        '''
        res = super(stock_warehouse_order_cycle, self).default_get(cr, uid, fields, context=context)

        company_id = res.get('company_id')
        warehouse_id = res.get('warehouse_id')

        if not 'company_id' in res:
            company_id = self.pool.get('res.company')._company_default_get(cr, uid, 'stock.warehouse.automatic.supply', context=context)
            res.update({'company_id': company_id})

        if not 'warehouse_id' in res:
            warehouse_id = self.pool.get('stock.warehouse').search(cr, uid, [('company_id', '=', company_id)], context=context)[0]
            res.update({'warehouse_id': warehouse_id})

        if not 'location_id' in res:
            location_id = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context).lot_stock_id.id
            res.update({'location_id': location_id})

        if not 'consumption_period_from' in res:
            res.update({'consumption_period_from': (DateFrom(now()) + RelativeDate(day=1)).strftime('%Y-%m-%d')})

        if not 'consumption_period_to' in res:
            res.update({'consumption_period_to': (DateFrom(now()) + RelativeDate(months=1, day=1, days=-1)).strftime('%Y-%m-%d')})

        return res

    def on_change_period(self, cr, uid, ids, from_date, to_date):
        '''
        Check if the from date is younger than the to date
        '''
        warn = {}
        val = {}

        if from_date and to_date and from_date > to_date:
            warn = {'title': 'Issue on date',
                    'message': 'The start date must be younger than end date'}

        # Set the from date to the first day of the month            
        if from_date:
            val.update({'consumption_period_from': (DateFrom(from_date) + RelativeDate(day=1)).strftime('%Y-%m-%d')})

        # Set the to date to the last day of the month
        if to_date:
            val.update({'consumption_period_to': (DateFrom(to_date) + RelativeDate(months=1, day=1, days=-1)).strftime('%Y-%m-%d')})

        return {'value': val, 'warning': warn}

    def onChangeSearchNomenclature(self, cr, uid, ids, position, n_type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, 0, position, n_type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False, context={'withnum': 1})

    def fill_lines(self, cr, uid, ids, context=None):
        '''
        Fill all lines according to defined nomenclature level and sublist
        '''
        line_obj = self.pool.get('stock.warehouse.order.cycle.line')
        product_obj = self.pool.get('product.product')

        if context is None:
            context = {}

        for report in self.browse(cr, uid, ids, context=context):
            product_ids = []

            nom = False
            field = False
            # Get all products for the defined nomenclature
            if report.nomen_manda_3:
                nom = report.nomen_manda_3.id
                field = 'nomen_manda_3'
            elif report.nomen_manda_2:
                nom = report.nomen_manda_2.id
                field = 'nomen_manda_2'
            elif report.nomen_manda_1:
                nom = report.nomen_manda_1.id
                field = 'nomen_manda_1'
            elif report.nomen_manda_0:
                nom = report.nomen_manda_0.id
                field = 'nomen_manda_0'
            if nom:
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [(field, '=', nom)], context=context))

            # Get all products for the defined list
            if report.sublist_id:
                for line in report.sublist_id.product_ids:
                    product_ids.append(line.name.id)

            for product in product_obj.browse(cr, uid, product_ids, context=context):
                # Check if the product is not already in the list
                if product.type not in ('consu', 'service', 'service_recep') and \
                        not line_obj.search(cr, uid, [('order_cycle_id', '=', report.id), 
                                                      ('product_id', '=', product.id),
                                                      ('uom_id', '=', product.uom_id.id)], context=context):
                    line_obj.create(cr, uid, {'order_cycle_id': report.id,
                                              'product_id': product.id, 
                                              'safety_stock': 0.00,
                                              'uom_id': product.uom_id.id}, context=context)

        return True

    def get_nomen(self, cr, uid, ids, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, ids, field, context={'withnum': 1})

    def consumption_method_change(self, cr, uid, ids, past_consumption, reviewed_consumption, manual_consumption, order_coverage, field='past'):
        '''
        Uncheck a box when the other is checked
        '''
        v = {}
        w = {}
        date_from = now() + RelativeDate(day=1, months=-round(order_coverage, 1)+1)
        date_to = now() + RelativeDate(days=-1, day=1, months=1)
        dates = self.on_change_period(cr, uid, ids, date_from, date_to)
        if field == 'past' and past_consumption:
            v.update({'reviewed_consumption': 0, 'manual_consumption': 0.00,
                      'consumption_period_from': dates.get('value', {}).get('consumption_period_from'),
                      'consumption_period_to': dates.get('value', {}).get('consumption_period_to'),})
        elif field == 'past' and not past_consumption:
            v.update({'reviewed_consumption': 1, 'manual_consumption': 0.00,})
            v.update({'consumption_period_from': False, 'consumption_period_to': False})
        elif field == 'review' and reviewed_consumption:
            v.update({'past_consumption': 0, 'manual_consumption': 0.00})
            v.update({'consumption_period_from': False, 'consumption_period_to': False})
        elif field == 'review' and not reviewed_consumption:
            v.update({'past_consumption': 1, 'manual_consumption': 0.00, 
                      'consumption_period_from': dates.get('value', {}).get('consumption_period_from'),
                      'consumption_period_to': dates.get('value', {}).get('consumption_period_to'),})
        elif field == 'manual' and manual_consumption < 0.00:
            v.update({'manual_consumption': 0.00})
            w.update({'title': 'Negative consumption',
                      'message': 'You mustn\'t have a negative consumption'})
        elif field == 'manual' and manual_consumption != 0.00 :
            v.update({'reviewed_consumption': 0, 'past_consumption': 0})
            v.update({'consumption_period_from': False, 'consumption_period_to': False})
        elif field == 'manual' and (manual_consumption == 0.00 ):
            v.update({'past_consumption': 1,
                      'consumption_period_from': dates.get('value', {}).get('consumption_period_from'),
                      'consumption_period_to': dates.get('value', {}).get('consumption_period_to'),})

        return {'value': v, 'warning': w}

    def choose_change_frequence(self, cr, uid, ids, context=None):
        '''
        Open a wizard to define a frequency for the order cycle
        or open a wizard to modify the frequency if frequency already exists
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        frequence_id = False
        res_id = False
        res_ok = False

        for proc in self.browse(cr, uid, ids):
            res_id = proc.id
            if proc.frequence_id and proc.frequence_id.id:
                frequence_id = proc.frequence_id.id
                res_ok = True
            else:
                frequence_data = {'name': 'monthly',
                                  'monthly_choose_freq': 1,
                                  'monthly_choose_day': 'monday',
                                  'monthly_frequency': 1,
                                  'monthly_one_day': True,
                                  'no_end_date': True,
                                  'start_date': time.strftime('%Y-%m-%d'),}
                frequence_id = self.pool.get('stock.frequence').create(cr, uid, frequence_data, context=context)
                self.write(cr, uid, proc.id, {'frequence_id': frequence_id}, context=context)
                res_ok = True

        context.update({'active_id': res_id, 
                        'active_model': 'stock.warehouse.order.cycle',
                        'res_ok': res_ok})

        return {'type': 'ir.actions.act_window',
                'target': 'new',
                'res_model': 'stock.frequence',
                'view_type': 'form',
                'view_model': 'form',
                'context': context,
                'res_id': frequence_id}

    def onchange_warehouse_id(self, cr, uid, ids, warehouse_id, context=None):
        """ Finds location id for changed warehouse.
        @param warehouse_id: Changed id of warehouse.
        @return: Dictionary of values.
        """
        if warehouse_id:
            w = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context)
            v = {'location_id': w.lot_stock_id.id}
            return {'value': v}
        return {}

    def unlink(self, cr, uid, ids, context=None):
        '''
        When remove an order cycle rule, delete the attached frequency
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        freq_ids = []
        for auto in self.read(cr, uid, ids, ['frequence_id']):
            if auto['frequence_id']:
                freq_ids.append(auto['frequence_id'][0])
        if freq_ids:
            self.pool.get('stock.frequence').unlink(cr, uid, freq_ids, context)
        return super(stock_warehouse_order_cycle, self).unlink(cr, uid, ids, context=context)

    def copy(self, cr, uid, ids, default=None, context=None):
        '''
        When duplicate an order cycle rule, duplicate the frequency
        '''
        if not default:
            default = {}
        obj = self.read(cr, uid, ids, ['frequence_id'])
        if obj['frequence_id']:
            default['frequence_id'] = self.pool.get('stock.frequence').copy(cr, uid, obj['frequence_id'][0], context=context)

        default.update({
            'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.order.cycle') or '',
        })
        return super(stock_warehouse_order_cycle, self).copy(cr, uid, ids, default, context=context)

stock_warehouse_order_cycle()

class stock_warehouse_order_cycle_line(osv.osv):
    _name = 'stock.warehouse.order.cycle.line'
    _rec_name = 'product_id'
    _description = 'Products to replenish'

    def _get_data(self, cr, uid, ids, field_name, args, context=None):
        '''
        Compute some data
        '''
        product_obj = self.pool.get('product.product')
        proc_obj = self.pool.get('procurement.order')
        prodlot_obj = self.pool.get('stock.production.lot')

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            # Stock values
            location_id = line.order_cycle_id.location_id.id
            stock_product = product_obj.browse(cr, uid, line.product_id.id, context=dict(context, location=location_id))
            # Consumption values
            from_date = line.order_cycle_id.consumption_period_from
            to_date = line.order_cycle_id.consumption_period_to
            consu_product = product_obj.browse(cr, uid, line.product_id.id, context=dict(context, from_date=from_date, to_date=to_date))
            consu = 0.00
            if line.order_cycle_id.past_consumption:
                consu = consu_product.product_amc
            elif line.order_cycle_id.reviewed_consumption:
                consu = consu_product.reviewed_consumption
            else:
                consu = line.order_cycle_id.manual_consumption

            # Expiry values
            d_values = {'reviewed_consumption': False,
                        'past_consumption': False,
                        'manual_consumption': consu,
                        'consumption_period_from': line.order_cycle_id.consumption_period_from,
                        'consumption_period_to': line.order_cycle_id.consumption_period_to,
                        'leadtime': line.order_cycle_id.leadtime,
                        'coverage': line.order_cycle_id.order_coverage,
                        'safety_stock': line.safety_stock,
                        'safety_time': line.order_cycle_id.safety_stock_time}
            expiry_product_qty = product_obj.get_expiry_qty(cr, uid, line.product_id.id, location_id, False, d_values, context=dict(context, location=location_id, compute_child=True))
            expiry_product_qty = expiry_product_qty or 0.00

            qty_to_order, req_date = proc_obj._compute_quantity(cr, uid, False, line.product_id, line.order_cycle_id.location_id.id, d_values, context=dict(context, from_date=from_date, to_date=to_date, get_data=True))

            consumed_in_period = (consu * d_values['coverage']) + (consu * d_values['safety_time']) + d_values['safety_stock'] + expiry_product_qty
            if stock_product.perishable and stock_product.virtual_available < consumed_in_period:
                prodlot_ids = prodlot_obj.search(cr, uid, [('product_id', '=', stock_product.id)], order='life_date desc', limit=1, context=context)
                if prodlot_ids:
                    life_date = prodlot_obj.read(cr, uid, prodlot_ids[0], ['life_date'], context=context)['life_date']
                    if life_date < req_date:
                        req_date = life_date

            res[line.id] = {'consumption': consu,
                            'real_stock': stock_product.qty_available,
                            'available_stock': stock_product.virtual_available,
                            'expiry_before': expiry_product_qty,
                            'qty_to_order': qty_to_order >= 0.00 and qty_to_order or 0.00,
                            'supplier_id': stock_product.seller_id and stock_product.seller_id.id or False,
                            'required_date': req_date,
                            }

        return res

    _columns = {
        'product_id': fields.many2one('product.product', required=True, string='Product'),
        'uom_id': fields.many2one('product.uom', string='UoM', required=True),
        'order_cycle_id': fields.many2one('stock.warehouse.order.cycle', string='Order cycle', required=True, ondelete='cascade'),
        'safety_stock': fields.float(digits=(16,2), string='Safety stock (Qty)', required=True, related_uom='uom_id'),
        'consumption': fields.function(_get_data, method=True, type='float', digits=(16,3), string='AMC/FMC', multi='data', readonly=True),
        'real_stock': fields.function(_get_data, method=True, type='float', digits=(16,3), string='Real stock', multi='data', readonly=True, related_uom='uom_id'),
        'available_stock': fields.function(_get_data, method=True, type='float', digits=(16,3), string='Available stock', multi='data', readonly=True, related_uom='uom_id'),
        'expiry_before': fields.function(_get_data, method=True, type='float', digits=(16,3), string='Exp. before consumption', multi='data', readonly=True, related_uom='uom_id'),
        'qty_to_order': fields.function(_get_data, method=True, type='float', digits=(16,3), string='Qty. to order', multi='data', readonly=True, related_uom='uom_id'),
        'supplier_id': fields.function(_get_data, method=True, type='many2one', relation='res.partner', string='Supplier', multi='data', readonly=True),
        'required_date': fields.function(_get_data, method=True, type='date', string='Required by date', multi='data', readonly=True),
    }

    _defaults = {
        'safety_stock': 0.00,
    }

    def _check_uniqueness(self, cr, uid, ids, context=None):
        '''
        Check if the product is not already in the current rule
        '''
        for line in self.browse(cr, uid, ids, context=context):
            lines = self.search(cr, uid, [('id', '!=', line.id), 
                                          ('product_id', '=', line.product_id.id),
                                          ('order_cycle_id', '=', line.order_cycle_id.id)], context=context)
            if lines:
                return False

        return True

    _constraints = [
        (_check_uniqueness, 'You cannot have two times the same product on the same order cycle rule', ['product_id'])
    ]

    def onchange_uom_qty(self, cr, uid, ids, uom_id, qty):
        res = {}

        if qty:
            res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, qty, 'safety_stock', result=res)

        return res

    def product_change(self, cr, uid, ids, product_id=False, context=None):
        '''
        Set the UoM as the default UoM of the product
        '''
        v = {}

        if not product_id:
            v.update({'product_uom': False, 'safety_stock': 0.00})
        else:
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            if product.uom_id:
                v.update({'uom_id': product.uom_id.id})

        return {'value': v}

stock_warehouse_order_cycle_line()

class stock_frequence(osv.osv):
    _name = 'stock.frequence'
    _inherit = 'stock.frequence'

    _columns = {
        'order_cycle_ids': fields.one2many('stock.warehouse.order.cycle', 'frequence_id', string='Order Cycle'),
    }

    def copy(self, cr, uid, ids, default=None, context=None):
        '''
        When the frequence is duplicate, remove the attached order cycle rules
        '''
        if not default:
            default = {}
        default['order_cycle_ids'] = False
        return super(stock_frequence, self).copy(cr, uid, ids, default, context)

    def choose_frequency(self, cr, uid, ids, context=None):
        '''
        Adds the support of order cycles on choose frequency method
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        if not context.get('res_ok', False) and 'active_id' in context and 'active_model' in context and \
                context.get('active_model') == 'stock.warehouse.order.cycle':
            self.pool.get('stock.warehouse.order.cycle').write(cr, uid, [context.get('active_id')], {'frequence_id': ids[0]})

        return super(stock_frequence, self).choose_frequency(cr, uid, ids, context=context)

stock_frequence()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
