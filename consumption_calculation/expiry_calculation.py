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
from tools.translate import _

from mx.DateTime import *
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
        'input_output_ok': fields.boolean(string='Exclude Input and Output locations'),
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
        loc_obj = self.pool.get('stock.location')
        lots = {}
        loc_ids = []
        
        report = self.browse(cr, uid, ids[0], context=context)
        lot_ids = lot_obj.search(cr, uid, [('life_date', '<=', (date.today() + timedelta(weeks=report.week_nb)).strftime('%Y-%m-%d'))])
        domain = [('date', '<=', (date.today()  + timedelta(weeks=report.week_nb)).strftime('%Y-%m-%d')), ('state', '=', 'done'), ('prodlot_id', 'in', lot_ids)]
        domain_out = [('date', '<=', (date.today()  + timedelta(weeks=report.week_nb)).strftime('%Y-%m-%d')), ('state', '=', 'done'), ('prodlot_id', 'in', lot_ids)]
            
        not_loc_ids = []
        # Remove input and output location
        if report.input_output_ok:
            wh_ids = self.pool.get('stock.warehouse').search(cr, uid, [], context=context)
            for wh in self.pool.get('stock.warehouse').browse(cr, uid, wh_ids, context=context):
                not_loc_ids.extend(loc_obj.search(cr, uid, [('location_id', 'child_of', wh.lot_input_id.id)], context=context))
                not_loc_ids.extend(loc_obj.search(cr, uid, [('location_id', 'child_of', wh.lot_output_id.id)], context=context))

        if report.location_id:
            # Search all children locations of the report location
            loc_ids = loc_obj.search(cr, uid, [('location_id', 'child_of', report.location_id.id), ('quarantine_location', '=', False), ('usage', '=', 'internal'), ('id', 'not in', not_loc_ids)], context=context)
        else:
            # Search all locations according to parameters
            loc_ids = loc_obj.search(cr, uid, [('usage', '=', 'internal'), ('quarantine_location', '=', False), ('id', 'not in', not_loc_ids)], context=context)
        
        # Return the good view
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'expiry_quantity_report_processed_loc_view')[1]
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
            if move.prodlot_id and move.prodlot_id.id in lots and move.location_id.id in lots[move.prodlot_id.id]:
                lots[move.prodlot_id.id][move.location_id.id] -= move.product_qty
                
        for lot_location in lots:
            lot_brw = lot_obj.browse(cr, uid, lot_location, context=context)
            for location in lots[lot_location]:
                if lots[lot_location][location] > 0.00:
                    context.update({'location': location, 'compute_child': False})
                    real_qty = lot_obj.browse(cr, uid, lot_location, context=context).product_id.qty_available
                    self.pool.get('expiry.quantity.report.line').create(cr, uid, {'product_id': lot_brw.product_id.id,
                                                                                  'uom_id': lot_brw.product_id.uom_id.id,
                                                                                  'real_stock': real_qty,
                                                                                  'expired_qty': lots[lot_location][location],
                                                                                  'batch_number': lot_brw.name,
                                                                                  'expiry_date': lot_brw.life_date,
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
    _order = 'expiry_date, location_id, product_id asc'
    
    _columns = {
        'report_id': fields.many2one('expiry.quantity.report', string='Report', required=True),
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'product_code': fields.related('product_id', 'default_code', string='Reference', type='char'),
        'product_name': fields.related('product_id', 'name', string='Name', type='char'),
        'uom_id': fields.related('product_id', 'uom_id', string='UoM', type='many2one', relation='product.uom'),
        'real_stock': fields.float(digits=(16, 2), string='Total product real stock in location'),
        'expired_qty': fields.float(digits=(16, 2), string='Batch expired quantity in location'),
        'batch_number': fields.many2one('production.lot', string='Batch number'),
        'expiry_date': fields.date(string='Expiry date'),
        'location_id': fields.many2one('stock.location', string='Location'),
    }
    
expiry_quantity_report_line()


class product_likely_expire_report(osv.osv_memory):
    _name = 'product.likely.expire.report'
    _description = 'Products list likely to expire'
    
    _columns = {
        'location_id': fields.many2one('stock.location', string='Location'),
        'msf_instance': fields.char(size=64, string='Location', readonly=True),
        'input_output_ok': fields.boolean(string='Exclude Input and Output locations'),
        'date_from': fields.date(string='From', required=True),
        'date_to': fields.date(string='To', required=True),
        'consumption_type': fields.selection([('fmc', 'FMC -- Forecasted Monthly Consumption'), 
                                              ('amc', 'AMC -- Average Monthly Consumption'), 
                                              ('rac', 'RAC -- Real Average Consumption')], string='Consumption', required=True),
        'line_ids': fields.one2many('product.likely.expire.report.line', 'report_id', string='Lines', readonly=True),
        'consumption_from': fields.date(string='From'),
        'consumption_to': fields.date(string='To'),
        'only_non_zero': fields.boolean(string='Only products with total expired > 0'),
    }
    
    _defaults = {
        'date_from': lambda *a: time.strftime('%Y-%m-%d'),
        'consumption_to': lambda *a: time.strftime('%Y-%m-%d'),
        'consumption_type': lambda *a: 'fmc',
        'msf_instance': lambda *a: 'MSF Instance',
    }

    def period_change(self, cr, uid, ids, consumption_from, consumption_to, consumption_type, context={}):
        '''
        Get the first or last day of month
        '''
        res = {}

        if consumption_type == 'amc':
            if consumption_from:
                res.update({'consumption_from': (DateFrom(consumption_from) + RelativeDateTime(day=1)).strftime('%Y-%m-%d')})
            if consumption_to:
                res.update({'consumption_to': (DateFrom(consumption_to) + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d')})

        return {'value': res}
            
    
    def _get_average_consumption(self, cr, uid, product_id, consumption_type, date_from, date_to, context={}):
        '''
        Return the average consumption for all locations
        '''
        if not context:
            context = {}
        
        product_obj = self.pool.get('product.product')
        res = 0.00
        
        new_context = context.copy()
        new_context.update({'from_date': date_from,
                            'to_date': date_to,
                            'average': True})
        
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
            
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        move_obj = self.pool.get('stock.move')
        lot_obj = self.pool.get('stock.production.lot')
        loc_obj = self.pool.get('stock.location')
        product_obj = self.pool.get('product.product')
        line_obj = self.pool.get('product.likely.expire.report.line')
        item_obj = self.pool.get('product.likely.expire.report.item')
        item_line_obj = self.pool.get('product.likely.expire.report.item.line')
        
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'product_likely_expire_report_form_processed')[1]
        report = self.browse(cr, uid, ids[0], context=context)
        
        if report.date_to <= report.date_from:
            raise osv.except_osv(_('Error'), _('You cannot have \'To date\' older than \'From date\''))
        
        if report.consumption_type in ('amc', 'rac') and report.consumption_from > report.consumption_to:
            raise osv.except_osv(_('Error'), _('You cannot have \'To date\' older than \'From date\''))
            
        if report.consumption_type in ('amc', 'rac'):
            context.update({'from': report.consumption_from, 'to': report.consumption_to})
        else:
            context.update({'from': report.date_from, 'to': report.date_to})
        
        location_ids = []
        not_loc_ids = []

        if report.input_output_ok:
            wh_ids = self.pool.get('stock.warehouse').search(cr, uid, [], context=context)
            for wh in self.pool.get('stock.warehouse').browse(cr, uid, wh_ids, context=context):
                not_loc_ids.extend(loc_obj.search(cr, uid, [('location_id', 'child_of', wh.lot_input_id.id)], context=context))
                not_loc_ids.extend(loc_obj.search(cr, uid, [('location_id', 'child_of', wh.lot_output_id.id)], context=context))
        
        if report.location_id:
            # Get all locations
            location_ids = loc_obj.search(cr, uid, [('location_id', 'child_of', report.location_id.id), ('quarantine_location', '=', False), ('id', 'not in', not_loc_ids)], order='location_id', context=context)
        else:
            # Get all locations
            wh_location_ids = loc_obj.search(cr, uid, [('usage', '=', 'internal'), ('quarantine_location', '=', False), ('id', 'not in', not_loc_ids)], order='location_id', context=context)

            move_ids = move_obj.search(cr, uid, [('prodlot_id', '!=', False)], context=context)
            for move in move_obj.browse(cr, uid, move_ids, context=context):
                if move.location_id.id not in location_ids:
                    if move.location_id.usage == 'internal' and not move.location_id.quarantine_location and move.location_id.id in wh_location_ids:
                        location_ids.append(move.location_id.id)
                if move.location_dest_id.id not in location_ids and not move.location_dest_id.quarantine_location and move.location_dest_id.id in wh_location_ids:
                    if move.location_dest_id.usage == 'internal':
                        location_ids.append(move.location_dest_id.id)
            
        context.update({'location_id': location_ids, 'location': location_ids})
        
        lot_ids = lot_obj.search(cr, uid, [('stock_available', '>', 0.00)], order='product_id, life_date', context=context)
        
        from_date = DateFrom(report.date_from)
        to_date = DateFrom(report.date_to) + RelativeDateTime(day=1, months=1, days=-1)
        
        # Set all months between from_date and to_date
        dates = []
        while (from_date < to_date):
            dates.append(from_date)
            from_date = from_date + RelativeDateTime(months=1, day=1)
            
        # Create a report line for each product
        products = {}
        for lot in lot_obj.browse(cr, uid, lot_ids, context=context):
            if lot.product_id and lot.product_id.id not in products:
                products.update({lot.product_id.id: {}})
                consumption = self._get_average_consumption(cr, uid, lot.product_id.id, 
                                                                     report.consumption_type,
                                                                     context.get('from', report.date_from),
                                                                     context.get('to', report.date_to),
                                                                     context=context)
                
                products[lot.product_id.id].update({'line_id': line_obj.create(cr, uid, {'report_id': report.id,
                                                                                         'product_id': lot.product_id.id,
                                                                                         'in_stock': lot.product_id.qty_available,
                                                                                         'total_expired': 0.00,
                                                                                         'consumption': consumption,})})
                
                # Create an item for each date
                seq = 0
                total_cons = 0.00
                already_cons = 0.00
                rest = 0.00
                total_expired = 0.00
                start_month_flag = True
                last_expiry_date = False
                for month in dates:
                    if not last_expiry_date: last_expiry_date = month
                    
                    item_id = item_obj.create(cr, uid, {'name': month.strftime('%m/%y'), 
                                                        'line_id': products[lot.product_id.id]['line_id']}, context=context)
                    available_qty = 0.00
                    expired_qty = 0.00
                    seq += 1
                    
                    # Create a line for each lot which expired in this month
                    domain = [('product_id', '=', lot.product_id.id),
                             ('stock_available', '>', 0.00),
                             ('life_date', '<', (month + RelativeDateTime(months=1, day=1)).strftime('%Y-%m-%d'))]

                    # If we are not in the first month of the period, displayed all products already expired
                    if not start_month_flag:
                        domain.append(('life_date', '>=', month.strftime('%Y-%m-%d')))
                        item_obj.write(cr, uid, [item_id], {'period_start': (month + RelativeDateTime(day=1)).strftime('%Y-%m-%d')}, context=context)
                    else:
                        item_obj.write(cr, uid, [item_id], {'period_start': report.date_from}, context=context)

                    # Remove the token after the first month processing
                    start_month_flag = False

                    product_lot_ids = lot_obj.search(cr, uid, domain, order='life_date', context=context)
                    
                    # Create an item line for each lot and each location
                    for product_lot in lot_obj.browse(cr, uid, product_lot_ids, context=context):
                        lot_days = Age(DateFrom(product_lot.life_date), last_expiry_date)
                        lot_coeff = (lot_days.years*365.0 + lot_days.months*30.0 + lot_days.days)/30.0
                        if lot_coeff >= 0.00: last_expiry_date = DateFrom(product_lot.life_date)
                        if lot_coeff < 0.00: lot_coeff = 0.00
                        lot_cons = self.pool.get('product.uom')._compute_qty(cr, uid, lot.product_id.uom_id.id, round(lot_coeff*consumption,2), lot.product_id.uom_id.id) + rest
                        
                        if lot_cons > 0.00:
                            if lot_cons >= product_lot.stock_available:
                                already_cons += product_lot.stock_available
                                rest = lot_cons - product_lot.stock_available
                                l_expired_qty = 0.00
                            else :
                                l_expired_qty = product_lot.stock_available - lot_cons
                                already_cons += lot_cons
                                rest = 0.00
                        else:
                            l_expired_qty = product_lot.stock_available
                        expired_qty += l_expired_qty
                        
                        lot_context = context.copy()
                        lot_context.update({'prodlot_id': product_lot.id})
                        product = product_obj.browse(cr, uid, lot.product_id.id, context=lot_context)
                        lot_expired_qty = l_expired_qty
                        for location in location_ids:
                            new_lot_context = lot_context.copy()
                            new_lot_context.update({'location': location, 'compute_child': False})
                            product2 = product_obj.browse(cr, uid, lot.product_id.id, context=new_lot_context)
                            if product2.qty_available > 0.00:
                                # Create the item line
                                if product2.qty_available <= lot_expired_qty:
                                    new_lot_expired = product2.qty_available
                                    lot_expired_qty -= product2.qty_available
                                else:
                                    new_lot_expired = lot_expired_qty
                                    lot_expired_qty = 0.00
                                item_line_obj.create(cr, uid, {'item_id': item_id,
                                                               'lot_id': product_lot.id,
                                                               'location_id': location,
                                                               'available_qty': product2.qty_available,
                                                               'expired_qty': new_lot_expired})
                            
                        available_qty += product.qty_available
                            
                    item_obj.write(cr, uid, [item_id], {'available_qty': available_qty,
                                                        'expired_qty': expired_qty}, context=context)
                    total_expired += expired_qty
                    
                if report.only_non_zero and total_expired <= 0.00:
                    line_obj.unlink(cr, uid, [products[lot.product_id.id]['line_id']], context=context)
                else:
                    line_obj.write(cr, uid, [products[lot.product_id.id]['line_id']], {'total_expired': total_expired}, context=context)
            
        new_date = []        
        for date in dates:
            new_date.append(date.strftime('%m/%y'))
            
        context.update({'dates': new_date})
                    
        return {'type': 'ir.actions.act_window',
                'res_model': 'product.likely.expire.report',
                'res_id': report.id,
                'view_id': [view_id],
                'view_type': 'form',
                'view_mode': 'form',
                'context': context,
                'target': 'dummy'}
        
        
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context={}, toolbar=False, submenu=False):
        if not context:
            context = {}
            
        res = super(product_likely_expire_report, self).fields_view_get(cr, uid, view_id, view_type, context=context)
        
        line_view = """<tree string="Expired products">
                <field name="product_id"/>
                <field name="consumption"/>
                """
                
        dates = context.get('dates', [])
        for month in dates:
            line_view += '<field name="%s" />' % month
            line_view += '<button name="go_to_item_%s" type="object" string="Go to item" icon="gtk-info" context="{item_date: %s}" />' % (month, month)
            
        line_view += """<field name="in_stock"/>
                        <field name="total_expired" />
                        </tree>"""
                        
        if res['fields'].get('line_ids', {}).get('views', {}).get('tree', {}).get('arch', {}):
            res['fields']['line_ids']['views']['tree']['arch'] = line_view
             
        return res
                
product_likely_expire_report()


class product_likely_expire_report_line(osv.osv_memory):
    _name = 'product.likely.expire.report.line'
    
    _columns = {
            'report_id': fields.many2one('product.likely.expire.report', string='Report', required=True, ondelete='cascade'),
            'product_id': fields.many2one('product.product', string='Product', required=True),
            'consumption': fields.float(digits=(16,2), string='Monthly Consumption', required=True),
            'in_stock': fields.float(digits=(16,2), string='In stock'),
            'total_expired': fields.float(digits=(16,2), string='Total expired'),
    }
    
    def __getattr__(self, name, *args, **kwargs):
        if name[:11] == 'go_to_item_':
            date = name[11:]
            self.date = date
            return self.go_to_item
        else:
            return self.name
    
    def fields_get(self, cr, uid, fields=None, context={}):
        if not context:
            context = {}
            
        res = super(product_likely_expire_report_line, self).fields_get(cr, uid, fields, context)
        dates = context.get('dates', [])
        
        for month in dates:
            res.update({month: {'selectable': True,
                               'type': 'many2one',
                               'relation': 'product.likely.expire.report.item',
                               'string': month}})
            
        return res
    
    def go_to_item(self, cr, uid, ids, context={}):
        if not context:
            context = {}
            
        if not context.get('item_date', self.date):
            raise osv.except_osv(_('Error'), _('You haven\'t choose an item to open'))
        
        item_date = context.get('item_date', self.date)
        item_ids = self.pool.get('product.likely.expire.report.item').search(cr, uid, [('name', '=', item_date), ('line_id', '=', ids[0])], context=context)
        if not item_ids:
            raise osv.except_osv(_('Error'), _('You haven\'t choose an item to open'))
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'product.likely.expire.report.item',
                'res_id': item_ids[0],
                'view_type': 'form',
                'view_mode': 'form',
                'context': context,
                'target': 'new'}
        
            
    def read(self, cr, uid, ids, vals, context={}, load='_classic_read'):
        '''
        Set values for all dates
        '''
        
        res = super(product_likely_expire_report_line, self).read(cr, uid, ids, vals, context=context, load=load)
        
        item_obj = self.pool.get('product.likely.expire.report.item')
        for r in res:
            exp_ids = item_obj.search(cr, uid, [('line_id', '=', r['id'])], context=context)
            for exp in item_obj.browse(cr, uid, exp_ids, context=context):
                r.update({exp.name: ''})
                if exp.expired_qty > 0.00:
                    name = '%s (%s)' % (exp.available_qty, exp.expired_qty)
                else:
                    # Be careful to the undividable spaces
                    name = '      %s' % (exp.available_qty)

                r.update({exp.name: name})
                
        return res

        
product_likely_expire_report_line()


class product_likely_expire_report_item(osv.osv_memory):
    _name = 'product.likely.expire.report.item'
    
    _columns = {
            'line_id': fields.many2one('product.likely.expire.report.line', string='Line', ondelete='cascade'),
            'name': fields.char(size=64, string='Month'),
            'available_qty': fields.float(digits=(16,2), string='Available Qty.'),
            'expired_qty': fields.float(digits=(16,2), string='Expired Qty.'),
            'period_start': fields.date(string='Period start', readonly=True),
            'line_ids': fields.one2many('product.likely.expire.report.item.line', 'item_id', string='Batchs'),
    }
    
product_likely_expire_report_item()


class product_likely_expire_report_item_line(osv.osv_memory):
    _name = 'product.likely.expire.report.item.line'
    _order = 'expired_date, location_id'
    
    _columns = {
            'item_id': fields.many2one('product.likely.expire.report.item', strig='Item', ondelete='cascade'),
            'lot_id': fields.many2one('stock.production.lot', string='Lot'),
            'location_id': fields.many2one('stock.location', string='Location'),
            'available_qty': fields.float(digits=(16,2), string='Available Qty.'),
            'expired_qty': fields.float(digits=(16,2), string='Expired Qty.'),
            'expired_date': fields.related('lot_id', 'life_date', type='date', string='Expiry date'),
    }
    
product_likely_expire_report_item_line()
     

class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'
    
    def get_expiry_qty(self, cr, uid, product_id, location_id, monthly_consumption, context={}):
        '''
        Get the expired quantity of product
        '''
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        product_obj = self.pool.get('product.product')
        lot_obj = self.pool.get('stock.production.lot')
        stock_obj = self.pool.get('stock.location')
        
        monthly_consumption = 0.00
        
        # Get the monthly consumption
        if context.get('reviewed_consumption', False):
            monthly_consumption = product_obj.browse(cr, uid, product_id, context=context).reviewed_consumption
        elif context.get('monthly_consumption', False):
            monthly_consumption = product_obj.browse(cr, uid, product_id, context=context).monthly_consumption
        else:
            monthly_consumption = context.get('manual_consumption', 0.00)
            
        location_ids = stock_obj.search(cr, uid, [('location_id', 'child_of', location_id)])
            
        move_ids = move_obj.search(cr, uid, ['|', ('location_id', 'in', location_ids), ('location_dest_id', 'in', location_ids), 
                                             ('product_id', '=', product_id), ('prodlot_id', '!=', False)], context=context)
        
        lots = []
        for move in move_obj.browse(cr, uid, move_ids, context=context):
            if not move.prodlot_id.id in lots:
                lots.append(move.prodlot_id.id)
        
        # Get all lots for the product product_id
        lot_ids = lot_obj.search(cr, uid, [('product_id', '=', product_id), ('stock_available', '>', 0.00), ('id', 'in', lots)], \
                                order='life_date', context=context)


        
        # Sum of months before expiry
        sum_ni = 0.00      
        expired_qty = 0.00
        last_date = now()
        last_qty = False
        
        for lot in lot_obj.browse(cr, uid, lot_ids, context=context):
            life_date = strptime(lot.life_date, '%Y-%m-%d')
            rel_time = RelativeDateDiff(life_date, now())
            ni = round((rel_time.months*30 + rel_time.days)/30.0, 2)
            if last_qty == False:
                last_qty = uom_obj._compute_qty(cr, uid, lot.product_id.uom_id.id, (ni-sum_ni)*monthly_consumption, lot.product_id.uom_id.id)
            if last_date > life_date:
                expired_qty = lot.stock_available                
            elif ni - sum_ni > 0.00:
                expired_qty += last_qty
                last_qty = uom_obj._compute_qty(cr, uid, lot.product_id.uom_id.id, (ni-sum_ni)*monthly_consumption, lot.product_id.uom_id.id)
                sum_ni += ni
            else:
                break
        return expired_qty
    
product_product()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
