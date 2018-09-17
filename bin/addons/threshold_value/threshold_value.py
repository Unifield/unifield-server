#!/usr/bin/env python
# -*- encoding: utf-8 -*-
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

from osv import osv
from osv import fields
from tools.translate import _

from mx.DateTime import DateFrom
from mx.DateTime import now
from mx.DateTime import RelativeDate

class threshold_value(osv.osv):
    _name = 'threshold.value'
    _description = 'Threshold value'
    
    def _get_product_ids(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns a list of products for the rule
        '''
        res = {}
        
        for rule in self.browse(cr, uid, ids, context=context):
            res[rule.id] = []
            for line in rule.line_ids:
                res[rule.id].append(line.product_id.id)
        
        return res
    
    def _src_product_ids(self, cr, uid, obj, name, args, context=None):
        if not context:
            context = {}
            
        res = []
            
        for arg in args:
            if arg[0] == 'product_ids':
                rule_ids = []
                line_ids = self.pool.get('threshold.value.line').search(cr, uid, [('product_id', arg[1], arg[2])])
                for l in self.pool.get('threshold.value.line').browse(cr, uid, line_ids):
                    if l.threshold_value_id.id not in rule_ids:
                        rule_ids.append(l.threshold_value_id.id)
                res.append(('id', 'in', rule_ids))
                
        return res
    
    _columns = {
        'name': fields.char(size=128, string='Reference', required=True),
        'active': fields.boolean(string='Active'),
        'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse', required=True),
        'location_id': fields.many2one('stock.location', 'Location', required=True, ondelete="cascade", 
                                       domain="[('is_replenishment', '=', warehouse_id)]",
                                       help='Location where the computation is made'),
        'compute_method': fields.selection([('fixed', 'Fixed values'), ('computed', 'Computed values')],
                                           string='Method of computation', required=True,
                                           help="""If 'Fixed values', the scheduler will compare stock of product with the threshold value of the line. \n
                                           If 'Computed values', the threshold value and the ordered quantity will be calculated according to defined parameters"""),
        'consumption_method': fields.selection([('amc', 'Average Monthly Consumption'), ('fmc', 'Forecasted Monthly Consumption')],
                                               string='Consumption Method',
                                               help='Method used to compute the consumption of products.'),
        'consumption_period_from': fields.date(string='Period of calculation', 
                                             help='This period is a number of past months the system has to consider for AMC calculation.'\
                                             'By default this value is equal to the frequency in the Threshold.'),
        'consumption_period_to': fields.date(string='-'),
        'frequency': fields.float(digits=(16,2), string='Order frequency', 
                                  help='The time between two replenishments. Will be used to compute the quantity to order.'),
        'safety_month': fields.float(digits=(16,2), string='Safety Stock in months',
                                     help='In months. Period during the stock is not empty but need to be replenish. \
                                     Used to compute the quantity to order.'),
        'lead_time': fields.float(digits=(16,2), string='Fixed Lead Time in months',
                                  help='In months. Time to be delivered after processing the purchase order.'),
        'supplier_lt': fields.boolean(string='Product\'s supplier LT',
                                      help='If checked, use the lead time set in the supplier form.'),
        'line_ids': fields.one2many('threshold.value.line', 'threshold_value_id', string="Products"),
        'fixed_line_ids': fields.one2many('threshold.value.line', 'threshold_value_id2', string="Products"),
        'product_ids': fields.function(_get_product_ids, fnct_search=_src_product_ids, 
                                    type='many2many', relation='product.product', method=True, string='Products'),
        'sublist_id': fields.many2one('product.list', string='List/Sublist', ondelete='set null'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type', ondelete='set null'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group', ondelete='set null'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family', ondelete='set null'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root', ondelete='set null'),
    }
    
    _defaults = {
        'name': lambda obj, cr, uid, context=None: obj.pool.get('ir.sequence').get(cr, uid, 'threshold.value') or '',
        'active': lambda *a: True,
        'frequency': lambda *a: 3,
        'consumption_method': lambda *a: 'amc',
        'consumption_period_from': lambda *a: (now() + RelativeDate(day=1, months=-2)).strftime('%Y-%m-%d'),
        'consumption_period_to': lambda *a: (now() + RelativeDate(day=1)).strftime('%Y-%m-%d'),
    }
    
    def copy(self, cr, uid, ids, defaults={}, context=None):
        '''
        Increment the sequence
        '''
        name = self.pool.get('ir.sequence').get(cr, uid, 'threshold.value') or ''
        defaults.update({'name': name})
        
        return super(threshold_value, self).copy(cr, uid, ids, defaults, context=context)
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Get the default values for the replenishment rule
        '''
        res = super(threshold_value, self).default_get(cr, uid, fields, context=context)
        
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
        
        return res
    
    def onchange_warehouse_id(self, cr, uid, ids, warehouse_id, context=None):
        """ Finds default stock location id for changed warehouse.
        @param warehouse_id: Changed id of warehouse.
        @return: Dictionary of values.
        """
        if warehouse_id:
            w = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context)
            v = {'location_id': w.lot_stock_id.id}
            return {'value': v}
        return {}
    
    def on_change_method(self, cr, uid, ids, method):
        '''
        Unfill the consumption period if the method is FMC
        '''
        res = {}
        
        if method and method == 'fmc':
            res.update({'consumption_period_from': False, 'consumption_period_to': False})
        elif method and method == 'amc':
            res.update({'consumption_period_from': (now() + RelativeDate(day=1, months=-2)).strftime('%Y-%m-%d'),
                        'consumption_period_to': (now() + RelativeDate(day=1, months=1, days=-1)).strftime('%Y-%m-%d')})
        
        return {'value': res}
    
    def on_change_period(self, cr, uid, ids, from_date, to_date):
        '''
        Check if the from date is younger than the to date
        '''
        warn = {}
        val = {}
        
        if from_date and to_date and from_date > to_date:
            warn = {'title': 'Issue on date',
                    'message': 'The start date must be younger than end date'}
            
        if from_date:
            val.update({'consumption_period_from': (DateFrom(from_date) + RelativeDate(day=1)).strftime('%Y-%m-%d')})
            
        if to_date:
            val.update({'consumption_period_to': (DateFrom(to_date) + RelativeDate(months=1, day=1, days=-1)).strftime('%Y-%m-%d')})
        
        return {'value': val, 'warning': warn}
    
    ##############################################################################################################################
    # The code below aims to enable filtering products regarding their sublist or their nomenclature.
    # Then, we fill lines of the one2many object 'threshold.value.line' according to the filtered products
    ##############################################################################################################################
    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, 0, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False, context={'withnum': 1})

    def fill_lines(self, cr, uid, ids, context=None):
        '''
        Fill all lines according to defined nomenclature level and sublist
        '''
        if context is None:
            context = {}
        for report in self.browse(cr, uid, ids, context=context):
            product_ids = []
            products = []
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

            # Check if products in already existing lines are in domain
            products = []
            for line in report.line_ids:
                if line.product_id.id in product_ids:
                    products.append(line.product_id.id)
                else:
                    self.pool.get('threshold.value.line').unlink(cr, uid, line.id, context=context)

            for product in self.pool.get('product.product').browse(cr, uid, product_ids, context=context):
                # Check if the product is not already on the report
                if product.type not in ('consu', 'service', 'service_recep') and product.id not in products:
                    self.pool.get('threshold.value.line').create(cr, uid, {'product_id': product.id,
                                                                                            'product_uom_id': product.uom_id.id,
                                                                                            'product_qty': 1.00,
                                                                                            'threshold_value_id': report.id})
        return {'type': 'ir.actions.act_window',
                'res_model': 'threshold.value',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'target': 'dummy',
                'context': context}
        
    def dummy(self, cr, uid, ids, context=None):
        return True

    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field, context={'withnum': 1})

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if vals.get('sublist_id',False):
            vals.update({'nomen_manda_0':False,'nomen_manda_1':False,'nomen_manda_2':False,'nomen_manda_3':False})
        if vals.get('nomen_manda_0',False):
            vals.update({'sublist_id':False})
        ret = super(threshold_value, self).write(cr, uid, ids, vals, context=context)
        return ret

    def on_change_compute_method(self, cr, uid, ids, compute_method,
        context=None):
        res = {}
        if compute_method and compute_method == 'computed':
            # UF-2511: switch from 'fixed' to 'compute' compute method
            # warn user to refresh values
            # (are not any more computed in 'fixed' mode)
            msg = "You switch from 'fixed values' to 'computed values'. " \
                "Please click on 'Refresh values' button to compute values."
            res = {
                'warning': {
                    'title': _('Warning'),
                    'message': _(msg),
                    },
            }
        return res

threshold_value()

class threshold_value_line(osv.osv):
    _name = 'threshold.value.line'
    _description = 'Threshold Value Line'
    _rec_name = 'product_id'
    
    def copy_data(self, cr, uid, ids, defaults={}, context=None):
        res = super(threshold_value_line, self).copy_data(cr, uid, ids, defaults, context=context)
        
        if isinstance(res, dict):
            if 'threshold_value_id' in res:
                del res['threshold_value_id']
            if 'threshold_value_id2' in res:
                del res['threshold_value_id2']
        
        return res
    
    def create(self, cr, uid, vals, context=None):
        '''
        Add the second link to the threshold value rule
        '''
        if 'threshold_value_id' in vals:
            vals.update({'threshold_value_id2': vals['threshold_value_id']})
        elif 'threshold_value_id2' in vals:
            vals.update({'threshold_value_id': vals['threshold_value_id2']})
        
        return super(threshold_value_line, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        Add the second link to the threshold value rule
        '''
        if not ids:
            return True
        if 'threshold_value_id' in vals:
            vals.update({'threshold_value_id2': vals['threshold_value_id']})
        elif 'threshold_value_id2' in vals:
            vals.update({'threshold_value_id': vals['threshold_value_id2']})
            
        context.update({'fake_threshold_value': vals.get('fake_threshold_value', False)})
        vals.update({'fake_threshold_value': 0.00})
        
        return super(threshold_value_line, self).write(cr, uid, ids, vals, context=context)
    
    def _get_values(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Compute and return the threshold value and qty to order
        '''
        res = {}
        if context is None:
            context = {}
        
        for line in self.browse(cr, uid, ids, context=context):
            if context.get('fake_threshold_value', False):
                res[line.id] = context.get('fake_threshold_value', 0.00)
                continue 
            res[line.id] = 0.00
            
            rule = line.threshold_value_id
            context.update({'location_id': rule.location_id.id, 'compute_child': True})
            product = self.pool.get('product.product').browse(cr, uid, line.product_id.id, context=context)
            result = self._get_threshold_value(cr, uid, line.id, product, rule.compute_method, rule.consumption_method, 
                                                     rule.consumption_period_from, rule.consumption_period_to, rule.frequency, 
                                                     rule.safety_month, rule.lead_time, rule.supplier_lt, line.product_uom_id.id, context)
            res[line.id] = result.get(field_name, 0.00) 
        
        return res

    
    def _get_threshold(self, cr, uid, ids, context={}):
        res = {}
        for t in self.pool.get('threshold.value').browse(cr, uid, ids, context=context):
            for l in t.line_ids:
                res[l.id] = True
                
        return res.keys()
        
    def _get_data(self, cr, uid, ids, field_name, args, context=None):
        '''
        Compute some data
        '''
        product_obj = self.pool.get('product.product')
        proc_obj = self.pool.get('procurement.order')

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            if context and context.get('compute_method', False) == 'fixed':
                # UF-2511: do not compute in 'fixed' compute method mode
                res[line.id] = {
                    'consumption': 0.,
                    'real_stock': 0.,
                    'available_stock': 0.,
                    'expiry_before': False,
                    'supplier_id': False,
                    'required_date': False,
                }
                continue

            # Stock values
            location_id = line.threshold_value_id.location_id.id
            stock_product = product_obj.browse(cr, uid, line.product_id.id, context=dict(context, location=location_id))
            # Consumption values
            from_date = line.threshold_value_id.consumption_period_from
            to_date = line.threshold_value_id.consumption_period_to
            consu_product = product_obj.browse(cr, uid, line.product_id.id, context=dict(context, from_date=from_date, to_date=to_date))
            consu = 0.00
            if line.threshold_value_id.consumption_method == 'amc':
                consu = consu_product.product_amc
            elif line.threshold_value_id.consumption_method == 'fmc':
                consu = consu_product.reviewed_consumption
            else:
                consu = 0.00

            # Expiry values
            d_values = {'reviewed_consumption': line.threshold_value_id.consumption_method == 'fmc',
                        'past_consumption': line.threshold_value_id.consumption_method == 'amc',
                        'manual_consumption': 0.00,
                        'consumption_period_from': line.threshold_value_id.consumption_period_from,
                        'consumption_period_to': line.threshold_value_id.consumption_period_to,
                        'leadtime': line.threshold_value_id.lead_time,
                        'coverage': line.threshold_value_id.frequency,
                        'safety_stock': 0.00,
                        'safety_time': line.threshold_value_id.safety_month}
            expiry_product_qty = product_obj.get_expiry_qty(cr, uid, line.product_id.id, location_id, False, d_values, context=dict(context, location=location_id, compute_child=True))

            new_context = context.copy()
            new_context.update({'from_date': from_date,
                                'to_date': to_date,
                                'get_data': True,
                                'consumption_period_from': d_values['consumption_period_from'],
                                'consumption_period_to': d_values['consumption_period_to'],})

            qty_to_order, req_date = proc_obj._compute_quantity(cr, uid, False, line.product_id, line.threshold_value_id.location_id.id, d_values, context=new_context)

            res[line.id] = {'consumption': consu,
                            'real_stock': stock_product.qty_available,
                            'available_stock': stock_product.virtual_available,
                            'expiry_before': expiry_product_qty,
                            'supplier_id': stock_product.seller_id.id,
                            'required_date': req_date,
                            }

        return res
    
    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'product_uom_id': fields.many2one('product.uom', string='Product UoM', required=True),
        'product_qty': fields.function(_get_values, method=True, type='float', string='Quantity to order', related_uom='product_uom_id'),
        'fake_threshold_value': fields.float(digits=(16,2), string='Threshold value'),
        'threshold_value': fields.function(_get_values, method=True, type='float', string='Threshold value',
                                           store={'threshold.value.line': (lambda self, cr, uid, ids, c=None: ids, ['product_id'],20),
                                                  'threshold.value': (_get_threshold, ['compute_method',
                                                                                       'consumption_method',
                                                                                       'consumption_period_from',
                                                                                       'consumption_period_to',
                                                                                       'frequency',
                                                                                       'safety_month',
                                                                                       'lead_time',
                                                                                       'supplier_lt'], 10)},
                                            related_uom='product_uom_id'),
        'fixed_product_qty': fields.float(digits=(16,2), string='Quantity to order', related_uom='product_uom_id'),
        'fixed_threshold_value': fields.float(digits=(16,2), string='Threshold value', related_uom='product_uom_id'),
        'threshold_value_id': fields.many2one('threshold.value', string='Threshold', ondelete='cascade', required=True),
        'threshold_value_id2': fields.many2one('threshold.value', string='Threshold', ondelete='cascade', required=True),
        'consumption': fields.function(_get_data, method=True, type='float', digits=(16,3), string='AMC/FMC', multi='data', readonly=True),
        'real_stock': fields.function(_get_data, method=True, type='float', digits=(16,3), string='Real stock', multi='data', readonly=True, related_uom='product_uom_id'),
        'available_stock': fields.function(_get_data, method=True, type='float', digits=(16,3), string='Available stock', multi='data', readonly=True, related_uom='product_uom_id'),
        'expiry_before': fields.function(_get_data, method=True, type='float', digits=(16,3), string='Exp. before consumption', multi='data', readonly=True, related_uom='product_uom_id'),
        'supplier_id': fields.function(_get_data, method=True, type='many2one', relation='res.partner', string='Supplier', multi='data', readonly=True),
        'required_date': fields.function(_get_data, method=True, type='date', string='Required by date', multi='data', readonly=True),
    }
    
    def _check_uniqueness(self, cr, uid, ids, context=None):
        '''
        Check if the product is not already in the current rule
        '''
        for line in self.browse(cr, uid, ids, context=context):
            lines = self.search(cr, uid, [('id', '!=', line.id), 
                                          ('product_id', '=', line.product_id.id),
                                          '|',
                                          ('threshold_value_id2', '=', line.threshold_value_id2.id),
                                          ('threshold_value_id', '=', line.threshold_value_id.id)], context=context)
            if lines:
                return False
            
        return True
    
    _constraints = [
        (_check_uniqueness, 'You cannot have two times the same product on the same threshold value rule', ['product_id'])
    ]
    
    def _get_threshold_value(self, cr, uid, line_id, product, compute_method, consumption_method,
                                consumption_period_from, consumption_period_to, frequency,
                                safety_month, lead_time, supplier_lt, uom_id, context=None):
        '''
        Return the threshold value and ordered qty of a product line
        '''
        if not context:
            context = {}

        if line_id and isinstance(line_id, list):
            line_id = line_id[0]
        
        cons = 0.00
        threshold_value = 0.00
        qty_to_order = 0.00
        if compute_method == 'computed':
            # Get the product available before change the context (from_date and to_date in context)
            product_available = product.qty_available
            
            # Change the context to compute consumption
            c = context.copy()
            c.update({'from_date': consumption_period_from, 'to_date': consumption_period_to})
            product = self.pool.get('product.product').browse(cr, uid, product.id, context=c)
            cons = consumption_method == 'fmc' and product.reviewed_consumption or product.product_amc
            
            # Set lead time according to choices in threshold rule (supplier or manual lead time)
            lt = supplier_lt and float(product.seller_delay)/30.0 or lead_time
                
            # Compute the threshold value
            threshold_value = cons * (lt + safety_month)
            threshold_value = self.pool.get('product.uom')._compute_qty(cr, uid, product.uom_id.id, threshold_value, product.uom_id.id)
                
            # Compute the quantity to re-order
            qty_to_order = cons * (frequency + lt + safety_month)\
                            - product_available - product.incoming_qty + product.outgoing_qty 
            qty_to_order = self.pool.get('product.uom')._compute_qty(cr, uid, uom_id or product.uom_id.id, \
                                                                     qty_to_order, product.uom_id.id)
            qty_to_order = qty_to_order > 0.00 and qty_to_order or 0.00
        elif line_id:
            line = self.browse(cr, uid, line_id, context=context)
            threshold_value = line.fixed_threshold_value
            qty_to_order = line.fixed_product_qty
            
        return {'threshold_value': threshold_value, 'product_qty': qty_to_order}

    def onchange_product_id(self, cr, uid, ids, product_id, compute_method=False, consumption_method=False,
                                consumption_period_from=False, consumption_period_to=False, frequency=False,
                                safety_month=False, lead_time=False, supplier_lt=False, fixed_tv=0.00, 
                                fixed_qty=0.00, uom_id=False, field='product_id', context=None):
        """ Finds UoM for changed product.
        @param product_id: Changed id of product.
        @return: Dictionary of values.
        """
        if not context:
            context = {}
        
        res = {'value': {'product_uom_id': False,
                         'fake_threshold_value': 0.00,
                         'threshold_value': 0.00}}
        if product_id:
            prod = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            if field == 'product_id':
                res['value'].update({'product_uom_id': prod.uom_id.id})
            elif uom_id:
                res['value'].update({'product_uom_id': uom_id})
            
            if compute_method:
                tv = self._get_threshold_value(cr, uid, ids, prod, compute_method, consumption_method,
                                               consumption_period_from, consumption_period_to, frequency,
                                               safety_month, lead_time, supplier_lt, uom_id or prod.uom_id.id, context=context)['threshold_value']
                res['value'].update({'fake_threshold_value': tv, 'threshold_value': tv})

                if prod.uom_id.id:
                    res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id or prod.uom_id.id, tv, ['fixed_threshold_value', 'fixed_product_qty', 'threshold_value', 'fake_threshold_value'], result=res)
                if prod.uom_id.id and fixed_tv:
                    res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id or prod.uom_id.id, fixed_tv, ['fixed_threshold_value'], result=res)
                if prod.uom_id.id and fixed_qty:
                    res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id or prod.uom_id.id, fixed_tv, ['fixed_product_qty'], result=res)

        return res

    def onchange_uom_qty(self, cr, uid, ids, uom_id, tv_qty, product_qty):
        '''
        Check round of qty according to UoM
        '''
        res = {}
        uom_obj = self.pool.get('product.uom')

        if tv_qty:
            res = uom_obj._change_round_up_qty(cr, uid, uom_id, tv_qty, 'fixed_threshold_value', result=res)

        if product_qty:
            res = uom_obj._change_round_up_qty(cr, uid, uom_id, product_qty, 'fixed_product_qty', result=res)

        return res

threshold_value_line()
