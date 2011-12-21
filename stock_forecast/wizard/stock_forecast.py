
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

PREFIXES = {'sale.order': 'so_',
            'purchase.order': 'po_',
            'procurement.order': 'pr_',
            'stock.picking': 'pick_',
            'tender': 'tend_',
            }

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
        objects = ['sale.order', 'purchase.order', 'procurement.order', 'stock.picking', 'tender',]
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
        'reference': fields.reference('Reference', selection=[], size=128),
        'state' : fields.selection(_get_states, string='State'),
        'qty' : fields.float('Quantity', digits=(16,2)),
        'stock_situation' : fields.float('Stock Situation', digits=(16,2)),
        'wizard_id' : fields.many2one('stock.forecast', string="Wizard"),
    }
    
    _order = 'date asc'
    
stock_forecast_line()


class stock_forecast(osv.osv_memory):
    _name = "stock.forecast"
    _description = "Stock Level Forecast"
    
    def _get_selection(self, cr, uid, field, objects, text, context=None):
        '''
        get selection related of specified objects, and modify keys on the fly
        '''
        result = []
        
        for obj in objects:
            tuples = self.pool.get(obj)._columns[field].selection
            for tuple in tuples:
                if tuple[0] == text:
                    return tuple[1]
        
        return text
    
    def _get_info(self, cr, uid, ids, fields, arg, context=None):
        '''
        get info concerning the selected product
        '''
        result = {}
        for wiz in self.browse(cr, uid, ids, context=context):
            result[wiz.id] = {'product_family_info_id': False,
                      'procurement_method': False,
                      'supply_method': False,
                      'keep_cool': False,
                      'short_shelf_life': False,
                      'dangerous_goods': False,
                      'justification_code_id': False,
                      }
            values = result[wiz.id]
            if wiz.product_id:
                values['product_family_info_id'] = wiz.product_id.nomen_manda_2.id
                values['procurement_method'] = wiz.product_id.procure_method
                values['supply_method'] = wiz.product_id.supply_method
                values['keep_cool'] = wiz.product_id.heat_sensitive_item
                values['short_shelf_life'] = wiz.product_id.short_shelf_life
                values['dangerous_goods'] = wiz.product_id.dangerous_goods
                values['justification_code_id'] = wiz.product_id.justification_code_id.id
        return result
    
    _columns = {
                'product_id': fields.many2one('product.product', 'Product'),
                'warehouse_id' : fields.many2one('stock.warehouse', 'Warehouse'),
                'product_uom_id': fields.many2one('product.uom', 'Product UoM'),
                'qty' : fields.float('Quantity', digits=(16,2), readonly=True),
                'product_family_id': fields.many2one('product.nomenclature', 'Product Family', domain=[('level', '=', 2)]), # not used
                'stock_forecast_lines': fields.one2many('stock.forecast.line', 'wizard_id', 'Stock Forecasts'),
                'product_family_info_id': fields.function(_get_info, type='many2one', relation='product.nomenclature', method=True, string='Product Family', multi='get_info',),
                'procurement_method': fields.function(_get_info, type='selection', selection=[('make_to_stock','Make to Stock'),('make_to_order','Make to Order')], method=True, string='Procurement Method', multi='get_info',),
                'supply_method': fields.function(_get_info, type='selection', selection=[('produce','Produce'),('buy','Buy')], method=True, string='Supply Method', multi='get_info',),
                'keep_cool': fields.function(_get_info, type='boolean', method=True, string='Keep Cool', multi='get_info',),
                'short_shelf_life': fields.function(_get_info, type='boolean', method=True, string='Short Shelf Life', multi='get_info',),
                'dangerous_goods': fields.function(_get_info, type='boolean', method=True, string='Dangerous Goods', multi='get_info',),
                'justification_code_id': fields.function(_get_info, type='many2one', relation='product.justification.code', method=True, string='Justification Code', multi='get_info',),
                }
    
    def start_forecast(self, cr, uid, ids, context=None):
        '''
        create forecast wizard object and execute do_forecast method before
        displaying it
        '''
        wizard_id = self.create(cr, uid, {}, context=context)
        # call do forecast on the created wizard
        self.do_forecast(cr, uid, [wizard_id], context=context)
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.forecast',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'popup',
                'res_id': wizard_id,
                'context': dict(context),
                }
    
    def onchange(self, cr, uid, ids, product_id, product_family_id, warehouse_id, product_uom_id, context=None):
        '''
        onchange function, trigger the value update of quantity
        '''
        if context is None:
            context = {}
            
        product_obj = self.pool.get('product.product')
        
        # get values from facade onchange functions
        values = context.get('values', {})
            
        product_list = []
        if product_id:
            product_list.append(product_id)
            
        if product_family_id:
            product_ids = product_obj.search(cr, uid, [('nomen_manda_2', '=', product_family_id)], context=context)
            product_list.extend(product_ids)
            
        c = context.copy()
        # if you remove the coma after done, it will no longer work properly
        c.update({'states': ('done',),
                  'what': ('in', 'out'),
                  'to_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                  'warehouse': warehouse_id,
                  'uom': product_uom_id})
        
        qty = product_obj.get_product_available(cr, uid, product_list, context=c)
        overall_qty = sum(qty.values())
        values.update(qty=overall_qty)
        
        return {'value': values}
    
    def do_print(self, cr, uid, ids, context=None):
        '''
        Print the report as PDF file
        '''
        if context is None:
            context = {}
            
        product_obj = self.pool.get('product.product')
        
        # data gathered on screen made available for the report
        product_name = 'n/a'
        product_code = 'n/a'
        warehouse_name = 'n/a'
        product_uom_name = 'n/a'
        product_family_name = 'n/a'
        product_family_info = 'n/a'
        
        procurement_method = 'n/a'
        supply_method = 'n/a'
        
        keep_cool = False
        short_shelf_life = False
        dangerous_goods = False
        
        qty = False
        date = time.strftime('%Y-%m-%d')
        
        # gather the wizard data
        for wizard in self.browse(cr, uid, ids, context=context):
            # product
            product_list = []
            if wizard.product_id:
                product_list.append(wizard.product_id.id)
                product_name = wizard.product_id.name
                product_code = wizard.product_id.default_code
                product_family_info = wizard.product_family_info_id.name
                
                procurement_method = self._get_selection(cr, uid, 'procure_method', ['product.template',], wizard.procurement_method, context=context)
                supply_method = self._get_selection(cr, uid, 'supply_method', ['product.template',], wizard.supply_method, context=context)
                
                keep_cool = str(bool(wizard.keep_cool)) 
                short_shelf_life = str(wizard.short_shelf_life)
                dangerous_goods = str(wizard.dangerous_goods)
                justification_code = wizard.justification_code_id and wizard.justification_code_id.name_get()[0][1] or 'n/a'
                
            else:
                raise osv.except_osv(_('Warning !'), _('No product selected.'))
                
            if wizard.product_family_id:
                product_ids = product_obj.search(cr, uid, [('nomen_manda_2', '=', wizard.product_family_id.id)], context=context)
                product_list.extend(product_ids)
                product_family_name = wizard.product_family_id.name
                
            # compute the overall_qty
            c = context.copy()
            # if you remove the coma after done, it will no longer work properly
            c.update({'states': ('done',),
                      'what': ('in', 'out'),
                      'to_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                      'warehouse': wizard.warehouse_id.id,
                      'uom': wizard.product_uom_id.id})
            qty = product_obj.get_product_available(cr, uid, product_list, context=c)
            overall_qty = sum(qty.values())
                
            # warehouse
            if wizard.warehouse_id:
                warehouse_name = wizard.warehouse_id.name
            # product uom
            if wizard.product_uom_id:
                product_uom_name = wizard.product_uom_id.name
        
            data = {'product_name': product_name,
                    'product_code': product_code,
                    'warehouse_name': warehouse_name,
                    'product_uom_name': product_uom_name,
                    'product_family_name': product_family_name,
                    'qty': overall_qty,
                    'date': date,
                    'product_family_info': product_family_info,
                    'procurement_method': procurement_method,
                    'supply_method': supply_method,
                    'keep_cool': keep_cool,
                    'short_shelf_life': short_shelf_life,
                    'dangerous_goods': dangerous_goods,
                    'justification_code': justification_code,
                    }
           
            line_ids = [x.id for x in wizard.stock_forecast_lines]
            if not line_ids:
                raise osv.except_osv(_('Warning !'), _('Your search did not match with any moves'))
        
            datas = {'ids': line_ids,
                     'model': 'stock.forecast.line',
                     'form': data}

            return {'type': 'ir.actions.report.xml',
                    'report_name': 'stock.forecast.report',
                    'datas': datas}
    
    def do_export(self, cr, uid, ids, context=None):
        '''
        call the export action
        '''
        if context is None:
            context = {}
        # create stock.forecast.export object
        export_obj = self.pool.get('stock.forecast.export')
        
        return export_obj.export_to_csv(cr, uid, ids, context=dict(context, stock_forecast_id=ids))
        
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
        self.write(cr, uid, ids, {'product_id': False,
                                  'warehouse_id': False,
                                  'product_uom_id': False,}, context=context)
        
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
        
    def do_graph(self, cr, uid, ids, context=None):
        '''
        void
        '''
        return {
                'name': 'Stock Level Forecast',
                'view_mode': 'graph,tree',
                'view_id': False,
                'view_type': 'form',
                'res_model': 'stock.forecast.line',
                'type': 'ir.actions.act_window',
                'nodestroy': True,
                'target': 'new',
                'domain': '[("wizard_id", "in", %s)]'%ids,
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
        tenderl_obj = self.pool.get('tender.line')
        pro_obj = self.pool.get('procurement.order')
        move_obj = self.pool.get('stock.move')
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        
        # clear existing lines
        line_ids = line_obj.search(cr, uid, [('wizard_id', 'in', ids)], context=context)
        line_obj.unlink(cr, uid, line_ids, context=context)
        
        # current date
        today = time.strftime('%Y-%m-%d %H:%M:%S')
        
        for wizard in self.browse(cr, uid, ids, context=context):
            prod = wizard.product_id
            product_family = wizard.product_family_id
            warehouse_id = wizard.warehouse_id.id
            product_uom_id = wizard.product_uom_id.id
            
            if not prod:
                raise osv.except_osv(_('Warning !'), _('You must select a product'))
            
            # the list of lines which will be created according to date order - [{},]
            line_to_create = []
            # list of product ids
            product_list = []
            
            if prod:
                product_list.append(prod.id)
                
            if product_family:
                product_ids = product_obj.search(cr, uid, [('nomen_manda_2', '=', product_family.id)], context=context)
                product_list.extend(product_ids)
                
            # qty of all products
            c = context.copy()
            # if you remove the coma after done, it will no longer work properly
            c.update({'states': ('done',),
                      'what': ('in', 'out'),
                      'to_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                      'warehouse': warehouse_id,
                      'uom': product_uom_id})
            qty = product_obj.get_product_available(cr, uid, product_list, context=c)
            overall_qty = sum(qty.values())
            
            for product in product_obj.browse(cr, uid, product_list, context=context):
                # UOM to use - either selected one or product one
                uom_to_use = product.uom_id
                if  wizard.product_uom_id:
                    uom_to_use = wizard.product_uom_id
                
                # SALE ORDERS - negative
                # list all sale order lines corresponding to selected product
                #so_list = so_obj.search(cr, uid, [()], context=context)
                sol_list = sol_obj.search(cr, uid, [('state', 'in', ('procurement', 'progress', 'draft')),
                                                    ('product_id', '=', product.id)], order='date_planned', context=context)
                
                for sol in sol_obj.browse(cr, uid, sol_list, context=context):
                    # create lines corresponding to so
                    values = {'date': sol.order_id.ready_to_ship_date and (len(sol.order_id.ready_to_ship_date.split(' ')) > 1 and sol.order_id.ready_to_ship_date.split(' ')[0] or sol.order_id.ready_to_ship_date) or '',
                              'doc': 'SO',
                              'order_type': PREFIXES['sale.order'] + sol.order_id.order_type,
                              'reference': 'sale.order,%s'%sol.order_id.id,
                              'state': PREFIXES['sale.order'] + sol.order_id.state,
                              'qty': uom_obj._compute_qty_obj(cr, uid, sol.product_uom, -sol.product_uom_qty, uom_to_use, context=context),
                              'stock_situation': False,
                              'wizard_id': wizard.id,}
                    if sol.procurement_request:
                        values.update(doc='ISR')
                        
                    line_to_create.append(values)
                
                # PURCHASE ORDERS - positive
                pol_list = pol_obj.search(cr, uid, [('order_state', 'in', ('draft', 'confirmed',)),
                                                    ('tender_id', '=', False),
                                                    ('product_id', '=', product.id)], order='date_planned', context=context)
                
                for pol in pol_obj.browse(cr, uid, pol_list, context=context):
                    # create lines corresponding to po
                    line_to_create.append({'date': pol.confirmed_delivery_date or len(pol.date_planned.split(' ')) > 1 and pol.date_planned.split(' ')[0] or pol.date_planned,
                                           'doc': 'PO',
                                           'order_type': PREFIXES['purchase.order'] + pol.order_id.order_type,
                                           'reference': 'purchase.order,%s'%pol.order_id.id,
                                           'state': PREFIXES['purchase.order'] + pol.order_id.state,
                                           'qty':  uom_obj._compute_qty_obj(cr, uid, pol.product_uom, pol.product_qty, uom_to_use, context=context),
                                           'stock_situation': False,
                                           'wizard_id': wizard.id,})
                    
                # TENDERS - positive
                ids_list = tenderl_obj.search(cr, uid, [('state', 'not in', ('done',)),
                                                        ('product_id', '=', product.id)], order='date_planned', context=context)
                
                for obj in tenderl_obj.browse(cr, uid, ids_list, context=context):
                    # create lines corresponding to po
                    line_to_create.append({'date': len(obj.date_planned.split(' ')) > 1 and obj.date_planned.split(' ')[0] or obj.date_planned,
                                           'doc': 'TENDER',
                                           'order_type': False,
                                           'reference': 'tender,%s'%obj.tender_id.id,
                                           'state': PREFIXES['tender'] + obj.tender_id.state,
                                           'qty':  uom_obj._compute_qty_obj(cr, uid, obj.product_uom, obj.qty, uom_to_use, context=context),
                                           'stock_situation': False,
                                           'wizard_id': wizard.id,
                                           })
                
                # PROCUREMENT ORDERS
                pro_list = pro_obj.search(cr, uid, [('state', 'in', ('exception',)),
                                                    ('product_id', '=', product.id)], order='date_planned', context=context)
                
                for pro in pro_obj.browse(cr, uid, pro_list, context=context):
                    # create lines corresponding to po
                    line_to_create.append({'date': pro.date_planned.split(' ')[0],
                                           'doc': 'PR',
                                           'order_type': False,
                                           'reference': 'procurement.order,%s'%pro.id,
                                           'state': PREFIXES['procurement.order'] + pro.state,
                                           'qty': uom_obj._compute_qty_obj(cr, uid, pro.product_uom, pro.product_qty, uom_to_use, context=context),
                                           'stock_situation': False,
                                           'wizard_id': wizard.id,})
                    
                # STOCK MOVES - in positive - out negative
                moves_list = move_obj.search(cr, uid, [('state', 'not in', ('done', 'cancel')),
                                                       ('product_qty', '!=', 0.0), # dont take empty draft picking tickets into account if empty
                                                       ('picking_subtype', 'not in', ('ppl', 'packing')), # dont take into account moves that are out of STOCK location
                                                       ('product_id', '=', product.id)], order='date_expected', context=context)
                
                for move in move_obj.browse(cr, uid, moves_list, context=context):
                    if move.picking_id.type in ('in', 'out',):
                        # create lines corresponding to po
                        values = {'date': move.date_expected.split(' ')[0],
                                  'doc': 'IN',
                                  # to check - purchase order or sale order prefix ?
                                  'order_type': move.order_type and PREFIXES['purchase.order'] + move.order_type or False,
                                  'reference': 'stock.picking,%s'%move.picking_id.id,
                                  'state': PREFIXES['stock.picking'] + move.picking_id.state,
                                  'qty': uom_obj._compute_qty_obj(cr, uid, move.product_uom, move.product_qty, uom_to_use, context=context),
                                  'stock_situation': False,
                                  'wizard_id': wizard.id,}
                        if move.picking_id.type == 'out':
                            values.update(doc='OUT', qty=uom_obj._compute_qty_obj(cr, uid, move.product_uom, -move.product_qty, uom_to_use, context=context))
                        
                        line_to_create.append(values)
                
            # sort the lines according to date, and then doc
            line_to_create = sorted(line_to_create, key=itemgetter('date', 'doc'))
            
            # create the first line with overall qty
            line_obj.create(cr, uid, {'date': today.split(' ')[0],
                                      'doc': False,
                                      'order_type': False,
                                      'reference': False,
                                      'state': False,
                                      'qty': False,
                                      'stock_situation': overall_qty,
                                      'wizard_id': wizard.id,}, context=context)
            
            # create the lines
            for line in line_to_create:
                # update the stock situation, cannot be done before the list is actually ordered
                overall_qty += line['qty']
                line.update(stock_situation=overall_qty)
                line_obj.create(cr, uid, line, context=context)
            
            return True # popup policy
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
            
        product_obj = self.pool.get('product.product')
        
        res = super(stock_forecast, self).default_get(cr, uid, fields, context=context)
        
        if context.get('active_ids', []):
            active_id = context.get('active_ids')[0]
            
            if 'product_id' in fields:
                res.update(product_id=active_id)
                # update quantity
                if 'qty' in fields:
                    c = context.copy()
                    # if you remove the coma after done, it will no longer work properly
                    c.update({'states': ('done',),
                              'what': ('in', 'out'),
                              'to_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                              'warehouse': False,
                              'uom': False})
                    
                    qty = product_obj.get_product_available(cr, uid, [active_id], context=c)
                    res.update(qty=qty[active_id])
                    
                if 'product_uom_id' in fields:
                    res.update(product_uom_id=product_obj.browse(cr, uid, active_id, context=context).uom_id.id)
                    
        return res
    
    def onchange_product(self, cr, uid, ids, product_id, product_family_id, warehouse_id, product_uom_id, context=None):
        '''
        product changed
        '''
        if context is None:
            context = {}
            
        product_obj = self.pool.get('product.product')
            
        values = {}
        context.update(values=values)
        # if product family is filled, we empty it
        if product_family_id:
            values.update(product_family_id=False)
            return self.onchange(cr, uid, ids, product_id, False, warehouse_id, product_uom_id, context)
        else:
            # update the uom values
            if product_id:
                values.update(product_uom_id=product_obj.browse(cr, uid, product_id, context=context).uom_id.id)
            return self.onchange(cr, uid, ids, product_id, product_family_id, warehouse_id, product_uom_id, context)
        
    def onchange_nomen(self, cr, uid, ids, product_id, product_family_id, warehouse_id, product_uom_id, context=None):
        '''
        product family changed
        '''
        if context is None:
            context = {}
        
        values = {}
        context.update(values=values)
        # if product family is filled, we empty it
        if product_id:
            values.update(product_id=False)
            return self.onchange(cr, uid, ids, False, product_family_id, warehouse_id, product_uom_id, context)
        else:
            return self.onchange(cr, uid, ids, product_id, product_family_id, warehouse_id, product_uom_id, context)
        
    def onchange_warehouse(self, cr, uid, ids, product_id, product_family_id, warehouse_id, product_uom_id, context=None):
        '''
        warehouse changed
        '''
        return self.onchange(cr, uid, ids, product_id, product_family_id, warehouse_id, product_uom_id, context)
        
    def onchange_uom(self, cr, uid, ids, product_id, product_family_id, warehouse_id, product_uom_id, context=None):
        '''
        uom changed
        '''
        return self.onchange(cr, uid, ids, product_id, product_family_id, warehouse_id, product_uom_id, context)
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        generates the xml view
        '''
        # call super
        result = super(stock_forecast, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        
        _moves_arch_lst = """
                        <form string="Stock Forecast">
                            <group col="4" colspan="4">
                                <field name="product_id" colspan="4" on_change="onchange_product(product_id, product_family_id, warehouse_id, product_uom_id)" />
                                <!-- <field name="product_family_id" on_change="onchange_nomen(product_id, product_family_id, warehouse_id, product_uom_id)" /> -->
                                <field name="product_family_info_id" />
                                <field name="warehouse_id" on_change="onchange_warehouse(product_id, product_family_id, warehouse_id, product_uom_id)" />
                                <field name="product_uom_id" attrs="{'readonly':[('product_id', '=', False),],}" on_change="onchange_uom(product_id, product_family_id, warehouse_id, product_uom_id)" />
                                <field name="qty" />
                            </group>
                            <group col="2" colspan="2">
                                <separator string='Procurement' />
                                <field name="procurement_method" />
                                <field name="supply_method" />
                            </group>
                            <group col="2" colspan="2">
                                <separator string='Specific Information' />
                                <field name="keep_cool" />
                                <field name="short_shelf_life" />
                                <field name="dangerous_goods" />
                                <field name="justification_code_id" />
                            </group>
                            <newline />
                            <field name="stock_forecast_lines" colspan="4" nolabel="1" mode="tree,form" readonly="1"></field>
                            <group col="6" colspan="2">
                                <button name="do_print" string="Print" type="object" icon="gtk-print" />
                                <button name="do_export" string="Export" type="object" icon="gtk-save" />
                                <button name="do_graph" string="Graph" type="object" icon="terp-account" />
                            </group>
                            <group col="6" colspan="2">
                                <group col="6" colspan="2"></group>
                                <!-- <button name="reset_fields" string="Reset" type="object" icon="gtk-clear" /> -->
                                <button name="do_forecast" string="Refresh Forecast" type="object" icon="gtk-apply" />
                                <button icon="gtk-cancel" special="cancel" string="Close Wizard"/>
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


class purchase_order_line(osv.osv):
    '''
    add order_state columns    
    '''
    _inherit = 'purchase.order.line'
    STATE_SELECTION = [
                       ('draft', 'Draft'),
                       ('wait', 'Wait'),
                       ('confirmed', 'Validated'),
                       ('approved', 'Confirmed'),
                       ('except_picking', 'Receipt Exception'),
                       ('except_invoice', 'Invoice Exception'),
                       ('done', 'Closed'),
                       ('cancel', 'Cancelled'),
                       ('rfq_sent', 'Sent'),
                       ('rfq_updated', 'Updated'),
                       #('rfq_done', 'RfQ Done'),
                       ]
    _columns = {'order_state': fields.related('order_id', 'state', string='Purchase Order State', type='selection', selection=STATE_SELECTION,),
                }
    
purchase_order_line()


class stock_move(osv.osv):
    '''
    corresponding picking subtype
    '''
    _inherit = 'stock.move'
    _columns = {'picking_subtype': fields.related('picking_id', 'subtype', string='Picking Subtype', type='selection', selection=[('picking', 'Picking'),('ppl', 'PPL'),('packing', 'Packing')],),
                }
    
stock_move()
