
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

from osv import fields, osv
from tools.translate import _
import time
import netsvc
from operator import itemgetter, attrgetter

PREFIXES = {'sale.order': 'so_', 'purchase.order': 'po_', 'procurement.order': 'pr_', 'stock.picking': 'pick_'}

class stock_forecast_line(osv.osv_memory):
    '''
    view corresponding to pack families
    
    integrity constraint 
    '''
    _name = "stock.forecast.line"
    _rec_name = 'date'
    
    def _get_selection(self, cr, uid, field, objects, context=None):
        '''
        get selection related of specified objects, and modify keys on the fly
        '''
        result = []
        
        for obj in objects:
            tuples = self.pool.get(obj)._columns[field].selection
            for tuple in tuples:
                result.append((PREFIXES[obj] + tuple[0], tuple[1]))
        
        return result
    
    def _get_states(self, cr, uid, context=None):
        '''
        get states of specified objects, and modify keys on the fly
        '''
        field = 'state'
        objects = ['sale.order', 'purchase.order', 'procurement.order', 'stock.picking']
        return self._get_selection(cr, uid, field, objects, context=context)
    
    def _get_order_type(self, cr, uid, context=None):
        '''
        get order_type of specified objects, and modify keys on the fly
        '''
        field = 'order_type'
        objects = ['sale.order', 'purchase.order']
        return self._get_selection(cr, uid, field, objects, context=context)
    
    _columns = {
        'date' : fields.date(string="Date"),
        'doc' : fields.char('Doc', size=1024,),
        'order_type': fields.selection(_get_order_type, string='Order Type'),
        'reference' : fields.char('Reference', size=1024,),
        'state' : fields.selection(_get_states, string='State'),
        'qty' : fields.float('Quantity', digits=(16,2)),
        'stock_situation' : fields.float('Stock Situation', digits=(16,2)),
        'wizard_id' : fields.many2one('stock.forecast', string="Wizard"),
    }
    
stock_forecast_line()


class stock_forecast(osv.osv_memory):
    _name = "stock.forecast"
    _description = "Stock Level Forecast"
    _columns = {
        'product': fields.many2one('product.product', 'Product'),
        'warehouse' : fields.many2one('stock.warehouse', 'Warehouse'),
        'product_uom': fields.many2one('product.uom', 'Product UoM'),
        'qty' : fields.float('Quantity', digits=(16,2), readonly=True),
        'stock_forecast_lines': fields.one2many('stock.forecast.line', 'wizard_id', 'Stock Forecasts'),
     }
    
    def onchange(self, cr, uid, ids, product, warehouse, product_uom, context=None):
        '''
        onchange function, trigger the value update of quantity
        '''
        if context is None:
            context = {}
            
        qty = 0
        if product:
            product = self.pool.get('product.product').browse(cr, uid, product, context=context)
            c = context.copy()
            # if you remove the coma after done, it will no longer work properly
            c.update({'states': ('done',),
                      'what': ('in', 'out'),
                      'to_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                      'warehouse': warehouse,
                      'uom': product_uom})
            
            qty = product.get_product_available(context=c)[product.id]
        
        return {'value': {'qty': qty}}
    
    def do_export(self, cr, uid, ids, context=None):
        '''
        call the export action
        '''
        # create stock.forecast.export object
        export_obj = self.pool.get('stock.forecast.export')
        
        return export_obj.export_to_csv(cr, uid, ids, context=context)
        
        return {
                'name': 'Stock Level Forecast',
                'res_model': 'stock.forecast.export',
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'state': 'code',
                'code': 'action = obj.export_to_csv(context=context)',
                'view_mode': 'form',
                'view_id': False,
                'target': 'new',
                }
        
        return {
                'name': 'Stock Level Forecast',
                'view_mode': 'form',
                'view_id': False,
                'view_type': 'form',
                'res_model': 'stock.forecast',
                'type': 'ir.actions.act_window',
                'nodestroy': True,
                'target': 'new',
                'domain': '[]',
                'context': context,
                }
    
    def reset_fields(self, cr, uid, ids, context=None):
        '''
        reset all fields and table
        '''
        self.write(cr, uid, ids, {'product': False,
                                  'warehouse': False,
                                  'product_uom': False,}, context=context)
        
        line_obj = self.pool.get('stock.forecast.line')
        line_ids = line_obj.search(cr, uid, [('wizard_id', 'in', ids)], context=context)
        line_obj.unlink(cr, uid, line_ids, context=context)
        
        return {
                'name': 'Stock Level Forecast',
                'view_mode': 'form',
                'view_id': False,
                'view_type': 'form',
                'res_model': 'stock.forecast',
                'res_id': ids[0],
                'type': 'ir.actions.act_window',
                'nodestroy': True,
                'target': 'new',
                'domain': '[]',
                'context': context,
                }
        
    def do_forecast(self, cr, uid, ids, context=None):
        '''
        generate the corresponding values
        '''
        if context is None:
            context = {}
            
        # line object
        line_obj = self.pool.get('stock.forecast.line')
        # objects
        so_obj = self.pool.get('sale.order')
        sol_obj = self.pool.get('sale.order.line')
        po_obj = self.pool.get('purchase.order')
        pol_obj = self.pool.get('purchase.order.line')
        pro_obj = self.pool.get('procurement.order')
        move_obj = self.pool.get('stock.move')
        
        # current date
        today = time.strftime('%Y-%m-%d %H:%M:%S')
        
        for wizard in self.browse(cr, uid, ids, context=context):
            product = wizard.product
            warehouse_id = wizard.warehouse.id
            product_uom_id = wizard.product_uom.id
            
            # the list of lines which will be created according to date order - [{},]
            line_to_create = []
            
            if product:
                # the first line represents the virual stock of the product at present time, without
                # any other information
                c = context.copy()
                # if you remove the coma after done, it will no longer work properly
                c.update({'states': ('done',),
                          'what': ('in', 'out'),
                          'to_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                          'warehouse': warehouse_id,
                          'uom': product_uom_id})
                qty = product.get_product_available(context=c)[product.id]
                
                line_obj.create(cr, uid, {'date': today,
                                          'doc': False,
                                          'order_type': False,
                                          'reference': False,
                                          'state': False,
                                          'qty': False,
                                          'stock_situation': qty,
                                          'wizard_id': wizard.id,}, context=context)
                
                # SALE ORDERS - negative
                # list all sale order lines corresponding to selected product
                #so_list = so_obj.search(cr, uid, [()], context=context)
                sol_list = sol_obj.search(cr, uid, [('date_planned', '>', today),
                                                    ('state', 'in', ('procurement', 'proc_progress', 'draft')),
                                                    ('product_id', '=', product.id)], order='date_planned', context=context)
                
                for sol in sol_obj.browse(cr, uid, sol_list, context=context):
                    # create lines corresponding to so
                    values = {'date': sol.date_planned,
                              'doc': 'SO',
                              'order_type': PREFIXES['sale.order'] + sol.order_id.order_type,
                              'reference': sol.order_id.name,
                              'state': PREFIXES['sale.order'] + sol.order_id.state,
                              'qty': -sol.product_uom_qty,
                              'stock_situation': False,
                              'wizard_id': wizard.id,}
                    if sol.procurement_request:
                        values.update(doc='ISR')
                        
                    line_to_create.append(values)
                
                # PURCHASE ORDERS - positive
                pol_list = pol_obj.search(cr, uid, [('date_planned', '>', today),
                                                    ('state', 'in', ('draft',)),
                                                    ('product_id', '=', product.id)], order='date_planned', context=context)
                
                for pol in pol_obj.browse(cr, uid, pol_list, context=context):
                    # create lines corresponding to po
                    line_to_create.append({'date': pol.date_planned,
                                           'doc': 'PO',
                                           'order_type': PREFIXES['purchase.order'] + pol.order_id.order_type,
                                           'reference': pol.order_id.name,
                                           'state': PREFIXES['purchase.order'] + pol.order_id.state,
                                           'qty': pol.product_qty,
                                           'stock_situation': False,
                                           'wizard_id': wizard.id,})
                
                # PROCUREMENT ORDERS
                pro_list = pro_obj.search(cr, uid, [('date_planned', '>', today),
                                                    ('state', 'in', ('exception',)),
                                                    ('product_id', '=', product.id)], order='date_planned', context=context)
                
                for pro in pro_obj.browse(cr, uid, pro_list, context=context):
                    # create lines corresponding to po
                    line_to_create.append({'date': pro.date_planned,
                                           'doc': 'PR',
                                           'order_type': False,
                                           'reference': pro.origin,
                                           'state': PREFIXES['procurement.order'] + pro.state,
                                           'qty': pro.product_qty,
                                           'stock_situation': False,
                                           'wizard_id': wizard.id,})
                    
                # STOCK MOVES - in positive - out negative
                moves_list = move_obj.search(cr, uid, [('date_expected', '>', today),
                                                       ('state', 'not in', ('done', 'cancel')),
                                                       ('product_id', '=', product.id)], order='date_expected', context=context)
                
                for move in move_obj.browse(cr, uid, moves_list, context=context):
                    if move.picking_id.type in ('in', 'out',):
                        # create lines corresponding to po
                        values = {'date': move.date_expected,
                                  'doc': 'IN',
                                  # to check - purchase order or sale order prefix ?
                                  'order_type': move.order_type and PREFIXES['purchase.order'] + move.order_type or False,
                                  'reference': move.picking_id.name,
                                  'state': PREFIXES['stock.picking'] + move.picking_id.state,
                                  'qty': move.product_qty,
                                  'stock_situation': False,
                                  'wizard_id': wizard.id,}
                        if move.picking_id.type == 'out':
                            values.update(doc='OUT', qty=-move.product_qty)
                        
                        line_to_create.append(values)
                
                # sort the lines according to date, and then doc
                line_to_create = sorted(line_to_create, key=itemgetter('date', 'doc'))
                
                # create the lines
                for line in line_to_create:
                    # update the stock situation, cannot be done before the list is actually ordered
                    qty += line['qty']
                    line.update(stock_situation=qty)
                    line_obj.create(cr, uid, line, context=context)
            
            return {
                    'name': 'Stock Level Forecast',
                    'view_mode': 'form',
                    'view_id': False,
                    'view_type': 'form',
                    'res_model': 'stock.forecast',
                    'res_id': ids[0],
                    'type': 'ir.actions.act_window',
                    'nodestroy': True,
                    'target': 'new',
                    'domain': '[]',
                    'context': context,
                    }
    
    def default_get(self, cr, uid, fields, context=None):
        """ For now no special initial values to load at wizard opening
        
         @return: A dictionary which of fields with values.
        """
        if context is None:
            context = {}
        
        res = super(stock_forecast, self).default_get(cr, uid, fields, context=context)
        
        if context.get('active_ids', []):
            active_id = context.get('active_ids')[0]
            
            if 'product' in fields:
                res.update(product=active_id)
        
        return res
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        generates the xml view
        '''
        # call super
        result = super(stock_forecast, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        
        _moves_arch_lst = """
                        <form string="Stock Forecast">
                            <group col="4" colspan="4">
                                <field name="product" on_change="onchange(product, warehouse, product_uom)" />
                                <field name="warehouse" on_change="onchange(product, warehouse, product_uom)" />
                                <field name="product_uom" on_change="onchange(product, warehouse, product_uom)" />
                                <field name="qty" />
                            </group>
                            <newline />
                            <group col="4" colspan="2"></group>
                            <group col="4" colspan="2">
                                <button name="reset_fields" string="Reset" type="object" icon="gtk-clear" />
                                <button name="do_forecast" string="Forecast" type="object" icon="gtk-apply" />
                            </group>
                            
                            <field name="stock_forecast_lines" colspan="4" nolabel="1" mode="tree,form"></field>
                            <group col="6" colspan="2"></group>
                            <group col="6" colspan="2">
                                <button name="print" string="Print" type="object" icon="gtk-print" />
                                <button name="do_export" string="Export" type="object" icon="gtk-save" />
                                <button name="graph" string="Graph" type="object" icon="gtk-stock_graph" />
                            </group>
                        </form>
                        """
        _moves_fields = result['fields']

        _moves_fields.update({
                            'stock_forecast_lines': {'relation': 'stock.forecast.line', 'type' : 'one2many', 'string' : 'Forecasts'}, 
                            })
        
        result['arch'] = _moves_arch_lst
        result['fields'] = _moves_fields
        return result

stock_forecast()
