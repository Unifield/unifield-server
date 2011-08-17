
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


class stock_forecast_line(osv.osv_memory):
    '''
    view corresponding to pack families
    
    integrity constraint 
    '''
    _name = "stock.forecast.line"
    _rec_name = 'date'
    
    _SELECTION_STATE = [# sale order
                        ('procurement', 'Internal Supply Requirement'),
                        ('proc_progress', 'In Progress'),
                        ('proc_cancel', 'Cancelled'),
                        ('proc_done', 'Done'),
                        ('draft', 'Quotation'),
                        ('waiting_date', 'Waiting Schedule'),
                        ('manual', 'Manual In Progress'),
                        ('progress', 'In Progress'),
                        ('shipping_except', 'Shipping Exception'),
                        ('invoice_except', 'Invoice Exception'),
                        ('done', 'Done'),
                        ('cancel', 'Cancelled'),
                        # purchase order
                        ('draft', 'Request for Quotation'),
                        ('wait', 'Waiting'),
                        ('confirmed', 'Waiting Approval'),
                        ('approved', 'Approved'),
                        ('except_picking', 'Shipping Exception'),
                        ('except_invoice', 'Invoice Exception'),
                        ('done', 'Done'),
                        ('cancel', 'Cancelled'),
                        ]
    
    _columns = {
        'date' : fields.date(string="Date"),
        'doc' : fields.char('Doc', size=1024,),
        'order_type': fields.selection([('regular', 'Regular'), ('donation_exp', 'Donation before expiry'), 
                                        ('donation_st', 'Standard donation'), ('loan', 'Loan'), 
                                        ('in_kind', 'In Kind Donation'), ('purchase_list', 'Purchase List'),
                                        ('direct', 'Direct Purchase Order')], string='Order Type'),
        'reference' : fields.char('Reference', size=1024,),
        'state' : fields.selection(_SELECTION_STATE, string='State'),
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
    
    def reset_fields(self, cr, uid, ids, context=None):
        '''
        reset all fields and table
        '''
        self.write(cr, uid, ids, {'product': False,
                                  'warehouse': False,
                                  'product_uom': False,}, context=context)
        
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
        # line object
        line_obj = self.pool.get('stock.forecast.line')
        
        for wizard in self.browse(cr, uid, ids, context=context):
            product = wizard.product
            warehouse = wizard.warehouse
            uom = wizard.product_uom
            
            print product,warehouse,uom
            
            # list all sale order lines corresponding to selected product
            
            
            # create a line for test purpose
            line_obj.create(cr, uid, {'doc': 'OUT',
                                      'order_type': 'regular',
                                      'reference': 'POxxxx',
                                      'state': 'procurement',
                                      'qty': 120,
                                      'stock_situation': 55,
                                      'wizard_id': wizard.id,}, context=context)
            
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
        return res
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        generates the xml view
        '''
        # call super
        result = super(stock_forecast, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        
        _moves_arch_lst = """
                        <form string="Stock Forecast">
                            <field name="product" on_change="onchange(product, warehouse, product_uom)" />
                            <field name="warehouse" on_change="onchange(product, warehouse, product_uom)" />
                            <field name="product_uom" on_change="onchange(product, warehouse, product_uom)" />
                            <field name="qty" />
                            <group col="4" colspan="4">
                                <button name="reset_fields" string="Reset" type="object" icon="gtk-convert" />
                                <button name="do_forecast" string="Forecast" type="object" icon="gtk-convert" />
                            </group>
                            <separator colspan="4" string="Forecasts"/>
                            <field name="stock_forecast_lines" colspan="4" nolabel="1" mode="tree,form"></field>
                        </form>"""
        _moves_fields = result['fields']

        _moves_fields.update({
                            'stock_forecast_lines': {'relation': 'stock.forecast.line', 'type' : 'one2many', 'string' : 'Forecasts'}, 
                            })
        
        result['arch'] = _moves_arch_lst
        result['fields'] = _moves_fields
        return result

stock_forecast()
