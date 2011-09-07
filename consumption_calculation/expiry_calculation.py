# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

from datetime import date, timedelta, datetime
import time

class expiry_quantity_report(osv.osv_memory):
    _name = 'expiry.quantity.report'
    _description = 'Products Expired'
    
    def _get_date_to(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Compute the end date for the calculation
        '''
        if not context:
            context = {}
        
        res = {}
        
        for report in self.browse(cr, uid, ids, context=context):
            res[report.id] = (date.today() + timedelta(weeks=report.week_nb)).strftime('%Y-%m-%d')
            
        return res
    
    _columns = {
        'location_id': fields.many2one('stock.location', string='Location'),
        'week_nb': fields.integer(string='Period of calculation (Today till XX weeks)', required=True),
        'date_to': fields.function(_get_date_to, method=True, type='date', string='Limit date', readonly=True),
        'line_ids': fields.one2many('expiry.quantity.report.line', 'report_id', string='Products', readonly=True),
    }
    
    def process_lines(self, cr, uid, ids, context={}):
        '''
        Creates all lines of expired products
        '''
        if not context:
            context = {}
        
        move_obj = self.pool.get('stock.move')
        lot_obj = self.pool.get('stock.production.lot')
        lots = {}
        
        report = self.browse(cr, uid, ids[0], context=context)
        lot_ids = lot_obj.search(cr, uid, [('life_date', '<=', (date.today() + timedelta(weeks=report.week_nb)).strftime('%Y-%m-%d'))])        
        domain = [('date_expected', '<=', date.today().strftime('%Y-%m-%d')), ('state', '=', 'done'), ('prodlot_id', 'in', lot_ids)]
        domain_out = domain
        
        
        if report.location_id:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'expiry_quantity_report_processed_view')[1]
            domain.append(('location_dest_id', '=', report.location_id.id))
            domain_out.append(('location_id', '=', report.location_id.id))
        else:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'expiry_quantity_report_processed_loc_view')[1]
            loc_ids = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'internal')], context=context)
            domain.append(('location_dest_id', 'in', loc_ids))
            domain_out.append(('location_id', 'in', loc_ids))
            
        move_ids = move_obj.search(cr, uid, domain, context=context)
        for move in move_obj.browse(cr, uid, move_ids, context=context):
            if move.prodlot_id:
                lot_id = move.prodlot_id.id
                # Add the lot in the list
                if lot_id not in lots:
                    lots[lot_id] = {}
                
                # Add the location in the lot list
                if move.location_dest_id.id not in lots[lot_id]:
                    lots[lot_id][move.location_dest_id.id] = 0.00
                    
                lots[lot_id][move.location_dest_id.id] += move.product_qty
        
        move_out_ids = move_obj.search(cr, uid, domain_out, context=context)
        for move in move_obj.browse(cr, uid, move_out_ids, context=context):
            if move.prodlot_id and move.prodlot_id.id in lots and move.location_dest_id.id in lots[move.prodlot_id.id]:
                lots[move.prodlot_id.id][move.location_dest_id.id] -= move.product_qty
                
        for lot_location in lots:
            product = lot_obj.browse(cr, uid, lot_location, context=context).product_id
            lot_name = lot_obj.browse(cr, uid, lot_location, context=context).name
            for location in lots[lot_location]:
                if lots[lot_location][location] > 0.00:
                    context.update({'location': location})
                    real_qty = lot_obj.browse(cr, uid, lot_location, context=context).product_id.qty_available
                    self.pool.get('expiry.quantity.report.line').create(cr, uid, {'product_id': product.id,
                                                                                  'uom_id': product.uom_id.id,
                                                                                  'real_stock': real_qty,
                                                                                  'expired_qty': lots[lot_location][location],
                                                                                  'batch_number': lot_name,
                                                                                  'location_id': location,
                                                                                  'report_id': ids[0],
                                                                                  })        
            
        return {'type': 'ir.actions.act_window',
                'res_model': 'expiry.quantity.report',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [view_id],
                'res_id': ids[0],
        }
    
expiry_quantity_report()


class expiry_quantity_report_line(osv.osv_memory):
    _name = 'expiry.quantity.report.line'
    _description = 'Products expired line'
    
    _columns = {
        'report_id': fields.many2one('expiry.quantity.report', string='Report', required=True),
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'product_code': fields.related('product_id', 'default_code', string='Reference', type='char'),
        'product_name': fields.related('product_id', 'name', string='Name', type='char'),
        'uom_id': fields.related('product_id', 'uom_id', string='UoM', type='many2one', relation='product.uom'),
        'real_stock': fields.float(digits=(16, 2), string='Real stock'),
        'expired_qty': fields.float(digits=(16, 2), string='Expired quantity'),
        'batch_number': fields.many2one('production.lot', string='Batch number'),
        'location_id': fields.many2one('stock.location', string='SLoc'),
    }
    
expiry_quantity_report_line()


class product_likely_expire_report(osv.osv_memory):
    _name = 'product.likely.expire.report'
    _description = 'Products list likely to expire'
    
    _columns = {
        'location_id': fields.many2one('stock.location', string='Location'),
        'date_from': fields.date(string='From', required=True),
        'date_to': fields.date(string='To', required=True),
        'consumption_type': fields.selection([('fmc', 'FMC -- Forecasted Monthly Consumption'), 
                                              ('amc', 'AMC -- Average Monthly Consumption'), 
                                              ('rac', 'RAC -- Real Average Consumption')], string='Consumption', required=True),
        'line_ids': fields.one2many('product.likely.expire.report.line', 'report_id', string='Lines', readonly=True),
    }
    
    _defaults = {
        'date_from': lambda *a: time.strftime('%Y-%m-%d'),
    }
    
    def _get_average_consumption(self, cr, uid, product_id, consumption_type, location_ids, date_from, date_to, context={}):
        '''
        Return the average consumption for all locations
        '''
        if not context:
            context = {}
        
        product_obj = self.pool.get('product.product')
        res = 0.00
        
        new_context = context.copy()
        
        new_context.update({'location_id': location_ids,
                            'date_from': date_from,
                            'date_to': date_to})
        
        if consumption_type == 'fmc':
            res = product_obj.browse(cr, uid, product_id, context=new_context).reviewed_consumption
        elif consumption_type == 'amc':
            res = product_obj.compute_amc(cr, uid, product_id, context=new_context)
        else:
            res = product_obj.browse(cr, uid, product_id, context=new_context).monthly_consumption
        
        return res
        
            
    def process_lines(self, cr, uid, ids, context={}):
        '''
        Creates all moves with expiry quantities for all
        lot life date
        '''
        if not context:
            context = {}
            
        move_obj = self.pool.get('stock.move')
        lot_obj = self.pool.get('stock.production.lot')
        line_obj = self.pool.get('product.likely.expire.report.line')
        model_obj = self.pool.get('ir.model')
        fields_obj = self.pool.get('ir.model.field')
        
        model_id = model_obj.search(cr, uid, [('model', '=', 'product.likely.expire.report.line')], context=context)[0]        
        
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'product_likely_expire_report_form_processed')[1]
        report = self.browse(cr, uid, ids[0], context=context)
        
        if report.location_id:
            context.update({'location_id': report.location_id.id})
        
        products = {}
        location_ids = []
        
        if report.location_id:
            location_ids = [report.location_id.id]
        else:
            location_ids = []
            move_ids = move_obj.search(cr, uid, [('prodlot_id', '!=', False)], context=context)
            for move in move_obj.browse(cr, uid, move_ids, context=context):
                if move.location_id.id not in location_ids:
                    if move.location_id.usage == 'internal':
                        location_ids.append(move.location_id.id)
                if move.location_dest_id.id not in location_ids:
                    if move.location_dest_id.usage == 'internal':
                        location_ids.append(move.location_dest_id.id)
        
        lot_ids = lot_obj.search(cr, uid, [('stock_available', '>', 0.00), ('life_date', '>=', report.date_from)], order='product_id, life_date', context=context)
        
        for lot in lot_obj.browse(cr, uid, lot_ids, context=context):
            if lot.product_id.id not in products:
                products[lot.product_id.id] = {'start': 0.00, 
                                               'expired': [], 
                                               'rest': 0.00, 
                                               'consumed': 0.00, 
                                               'total_expired': 0.00, 
                                               'line_id': False}
                
            products[lot.product_id.id]['start'] += lot.stock_available
            
        for product in products:
            products[product]['average_consumption'] = self._get_average_consumption(cr, uid, product, report.consumption_type, location_ids, report.date_from, report.date_to, context=context)
            
        for lot in lot_obj.browse(cr, uid, lot_ids, context=context):
            coeff = datetime.strptime(lot.life_date, '%Y-%m-%d') - datetime.strptime(report.date_from, '%Y-%m-%d')
            # Theorical consumption
            theo = round((coeff.days/30.0), 1) * products[lot.product_id.id]['average_consumption']
            theo = self.pool.get('product.uom')._compute_qty(cr, uid, lot.product_id.uom_id.id, theo, lot.product_id.uom_id.id) + products[lot.product_id.id]['rest'] - products[lot.product_id.id]['consumed']
            products[lot.product_id.id]['consumed'] += theo
                    
            # Fill the expired quantities on date
            if theo < lot.stock_available:
                products[lot.product_id.id]['expired'].append((lot.life_date, lot.stock_available-theo))
                products[lot.product_id.id]['total_expired'] += lot.stock_available-theo
            else:
                products[lot.product_id.id]['rest'] = theo - lot.stock_available
                
        for product in products:
            if products[product]['total_expired'] != 0.00:
                data = {'report_id': ids[0],
                        'product_id': product,
                        'real_stock': products[product]['start'],
                        'total_expired': products[product]['total_expired']}
                
                line_id = line_obj.create(cr, uid, data, context=context)
            
                products[product]['line_id'] = line_id
            
        context.update({'products': products})            
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'product.likely.expire.report',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [view_id],
                'context': context,
                'res_id': report.id}
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context={}, toolbar=False, submenu=False):
        if not context:
            context={}
            
        res = super(product_likely_expire_report, self).fields_view_get(cr, uid, view_id, view_type, context=context)
        
        line_view = """<tree string="Expired products">
    <field name="product_code"/>
    <field name="product_name"/>
    """
        
        products = context.get('products', [])
        
        dates = []
        
        for product in products:
            for expired_date in products[product].get('expired', []):
                if expired_date[0] not in dates:
                    dates.append(expired_date[0])
                    
        dates.sort()
                    
        for date in dates:
            line_view += '<field name="%s" />' % date
            
        line_view += """<field name="real_stock"/>
    <field name="total_expired"/>
    </tree>"""
    
        if res['fields'].get('line_ids', {}).get('views', {}).get('tree', {}).get('arch', {}):
            res['fields']['line_ids']['views']['tree']['arch'] = line_view
             
        return res
    
product_likely_expire_report()


class product_likely_expire_report_line(osv.osv_memory):
    _name = 'product.likely.expire.report.line'
    _description = 'Products line likely to expire'
    
    _columns = {
        'report_id': fields.many2one('product.likely.expire.report', string='Report', required=True),
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'product_code': fields.related('product_id', 'default_code', string='Reference', type='char'),
        'product_name': fields.related('product_id', 'name', string='Name', type='char'),
        'uom_id': fields.related('product_id', 'uom_id', string='UoM', type='many2one', relation='product.uom'),
        'real_stock': fields.float(digits=(16, 2), string='Real stock'),
        'total_expired': fields.float(digits=(16,2), string='Total expired'),
    }
    
    def fields_get(self, cr, uid, fields=None, context={}):
        if not context:
            context = {}
            
        res = super(product_likely_expire_report_line, self).fields_get(cr, uid, fields, context)
        products = context.get('products', [])
        dates = []
        
        for product in products:
            for expired_date in products[product].get('expired', []):
                if expired_date[0] not in dates:
                    dates.append(expired_date[0])
                    
        dates.sort()
                    
        for date in dates:
            label = time.strptime(date, '%Y-%m-%d')
            res.update({date: {'digits': (16, 2),
                               'selectable': True,
                               'type': 'float',
                               'string': '%s-%s-%s' % (label.tm_mday, label.tm_mon, label.tm_year)}})
            
        return res
    
    def read(self, cr, uid, ids, vals, context={}, load='_classic_read'):
        res = super(product_likely_expire_report_line, self).read(cr, uid, ids, vals, context=context, load=load)
        
        return res
    
product_likely_expire_report_line()
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
