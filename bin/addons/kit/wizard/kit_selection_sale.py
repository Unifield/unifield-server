# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Copyright (C) 2011 MSF, TeMPO Consulting.
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
import decimal_precision as dp

import netsvc

from msf_outgoing import INTEGRITY_STATUS_SELECTION

class kit_selection_sale(osv.osv_memory):
    '''
    kit selection
    '''
    _name = "kit.selection.sale"
    
    _columns = {'product_id_kit_selection_sale': fields.many2one('product.product', string='Kit Product', readonly=True),
                'kit_id_kit_selection_sale': fields.many2one('composition.kit', string='Theoretical Kit'),
                'order_line_id_kit_selection_sale': fields.many2one('sale.order.line', string='Sale Order Line', readonly=True, required=True),
                # one2many
                'product_ids_kit_selection_sale': fields.one2many('kit.selection.sale.line', 'wizard_id_kit_selection_sale_line', string='Replacement Products'),
                # related fields
                'partner_id_kit_selection_sale': fields.related('order_line_id_kit_selection_sale', 'order_id', 'partner_id', string='Partner', type='many2one', relation='res.partner', readonly=True, store=False),
                'pricelist_id_kit_selection_sale': fields.related('order_line_id_kit_selection_sale', 'order_id', 'pricelist_id', string='Currency', type='many2one', relation='product.pricelist', readonly=True, store=False),
                'warehouse_id_kit_selection_sale': fields.related('order_line_id_kit_selection_sale', 'order_id', 'warehouse_id', string='Warehouse', type='many2one', relation='stock.warehouse', readonly=True, store=False),
                }
    
    _defaults = {'product_id_kit_selection_sale': lambda s, cr, uid, c: c.get('product_id', False),
                 'order_line_id_kit_selection_sale': lambda s, cr, uid, c: c.get('active_ids') and c.get('active_ids')[0] or False,
                 }
    
    def import_items(self, cr, uid, ids, context=None):
        '''
        import lines into product_ids_kit_selection_sale
        '''
        # objects
        line_obj = self.pool.get('kit.selection.sale.line')
        # purchase order line id
        sol_ids = context['active_ids']
        
        for obj in self.browse(cr, uid, ids, context=context):
            if not obj.kit_id_kit_selection_sale:
                raise osv.except_osv(_('Warning !'), _('A theoretical version should be selected.'))
            if obj.kit_id_kit_selection_sale.state != 'completed':
                raise osv.except_osv(_('Warning !'), _('The theoretical version must be completed.'))
            for item in obj.kit_id_kit_selection_sale.composition_item_ids:
                values = {'order_line_id_kit_selection_sale_line': obj.order_line_id_kit_selection_sale.id,
                          'wizard_id_kit_selection_sale_line': obj.id,
                          'product_id_kit_selection_sale_line': item.item_product_id.id,
                          'qty_kit_selection_sale_line': item.item_qty,
                          'uom_id_kit_selection_sale_line': item.item_uom_id.id,
                          }
                line_obj.create(cr, uid, values, context=dict(context, sol_ids=context['active_ids']))
        return self.pool.get('wizard').open_wizard(cr, uid, sol_ids, w_type='update', context=context)
    
    def validate_lines(self, cr, uid, ids, context=None):
        '''
        validate the lines
        
        - qty > 0.0 (must_be_greater_than_0)
        - unit price > 0.0
        
        return True or False
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        lot_obj = self.pool.get('stock.production.lot')
        # errors
        errors = {'must_be_greater_than_0': False,
                  'price_must_be_greater_than_0': False,
                  }
        for obj in self.browse(cr, uid, ids, context=context):
            for item in obj.product_ids_kit_selection_sale:
                # reset the integrity status
                item.write({'integrity_status': 'empty'}, context=context)
                # qty
                if item.qty_kit_selection_sale_line <= 0.0:
                    # qty is needed
                    errors.update(must_be_greater_than_0=True)
                    item.write({'integrity_status': 'must_be_greater_than_0'}, context=context)
                # unit price
                if item.price_unit_kit_selection_sale_line <= 0.0:
                    # unit price is needed
                    errors.update(price_must_be_greater_than_0=True)
                    item.write({'integrity_status': 'price_must_be_greater_than_0'}, context=context)
        # check the encountered errors
        return all([not x for x in errors.values()])

    def do_de_kitting(self, cr, uid, ids, context=None):
        '''
        create a sale order line for each kit item and delete the selected kit purchase order line
        '''
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        so_obj = self.pool.get('sale.order')
        sol_obj = self.pool.get('sale.order.line')
        # id of corresponding sale order line
        sol_ids = context['active_ids']
        sol_id = context['active_ids'][0]
        sol = sol_obj.browse(cr, uid, sol_id, context=context)
        if sol.order_id.state not in ['draft', 'validated']:
            raise osv.except_osv(_('Warning !'), _('Sale order line kit replacement with components function is only available for Draft and Validated states.'))
        # integrity constraint
        integrity_check = self.validate_lines(cr, uid, ids, context=context)
        if not integrity_check:
            # the windows must be updated to trigger tree colors
            return self.pool.get('wizard').open_wizard(cr, uid, sol_ids, w_type='update', context=context)
        # process
        ctx_keep_info = context.copy()
        ctx_keep_info['keepDateAndDistrib'] = True
        for obj in self.browse(cr, uid, ids, context=context):
            if not len(obj.product_ids_kit_selection_sale):
                raise osv.except_osv(_('Warning !'), _('Replacement Items must be selected.'))
            # to keep a link to previous line (for copy) and as a flag to write in the first loop
            last_line_id = False
            # for each item from the product_ids_kit_selection_sale
            for item_v in obj.product_ids_kit_selection_sale:
                # price unit is mandatory
                if item_v.price_unit_kit_selection_sale_line <= 0.0:
                    raise osv.except_osv(_('Warning !'), _('Unit Price must be specified for each line.'))
                # selected product_id
                product_id = item_v.product_id_kit_selection_sale_line.id
                # selected qty
                qty = item_v.qty_kit_selection_sale_line
                if qty <= 0.0:
                    raise osv.except_osv(_('Warning !'), _('Quantity must be greater than 0.0.'))
                # selected uom
                uom_id = item_v.uom_id_kit_selection_sale_line.id
                # price unit
                price_unit = item_v.price_unit_kit_selection_sale_line
                # call purchase order line on change function
                data = self.pool.get('kit.selection.sale.line')._call_sol_on_change(cr, uid, ids, product_id, qty, uom_id, price_unit,
                                                                               type='product_id_change',
                                                                               context=dict(context, sol_ids=context['active_ids']))
                # common dictionary of data
                values = {'product_id': product_id,
                          'price_unit': price_unit,
                          'product_uom': uom_id,
                          'product_uom_qty': sol.product_uom_qty*qty,
                          'product_uos': uom_id,
                          'product_uos_qty': sol.product_uos_qty*qty,
                          'default_code': data['value']['default_code'],
                          'name': data['value']['name'],
                          'default_name': data['value']['default_name'],
                          }
                
                # following new sequencing policy, we check if resequencing occur (behavior 1).
                # if not (behavior 2), the split line keeps the same line number as original line
                if not sol_obj.allow_resequencing(cr, uid, [obj.order_line_id_kit_selection_sale.id], context=context):
                    # set default value for line_number as the same as original line
                    values.update({'line_number': obj.order_line_id_kit_selection_sale.line_number})
                
                if last_line_id:
                    # the existing purchase order line has already been updated, we create a new one
                    # copy the original purchase order line
                    last_line_id = sol_obj.copy(cr, uid, last_line_id, values, context=ctx_keep_info)
                    # as so *line* state is draft anyhow, we do not need to process the created line
                else:
                    # first item to be treated, we update the existing line
                    last_line_id = obj.order_line_id_kit_selection_sale.id
                    sol_obj.write(cr, uid, [last_line_id], values, context=context)
                
        return {'type': 'ir.actions.act_window_close'}
    
kit_selection_sale()


class kit_selection_sale_line(osv.osv_memory):
    '''
    substitute items
    '''
    _name = 'kit.selection.sale.line'
    
    def create(self, cr, uid, vals, context=None):
        '''
        default price unit from sol on_change function
        '''
        # objects
        sol_obj = self.pool.get('sale.order.line')
        # id of corresponding sale order line
        sol_id = context.get('active_ids', False) and context['active_ids'][0] or False
        if sol_id and ('price_unit_kit_selection_sale_line' not in vals or vals.get('price_unit_kit_selection_sale_line') == 0.0):
            sol = sol_obj.browse(cr, uid, sol_id, context=context)
            # selected product_id
            product_id = vals.get('product_id_kit_selection_sale_line', False)
            # selected qty
            qty = vals.get('qty_kit_selection_sale_line', 0.0)
            # selected uom
            uom_id = vals.get('uom_id_kit_selection_sale_line', False)
            # price unit
            price_unit = vals.get('price_unit_kit_selection_sale_line', 0.0)
            # gather default values
            data = self._call_sol_on_change(cr, uid, context['active_ids'],
                                            product_id, qty, uom_id, price_unit, type='product_id_change',
                                            context=context)
            
            # update price_unit value
            vals.update({'price_unit_kit_selection_sale_line': data['value']['price_unit']})
        return super(kit_selection_sale_line, self).create(cr, uid, vals, context=context)
    
    def _call_sol_on_change(self, cr, uid, ids, product_id, qty, uom_id, price_unit, type, context=None):
        '''
        core function from sale order line
        
        def product_id_change(self, cr, uid, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False):
        '''
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        # objects
        sol_obj = self.pool.get('sale.order.line')
        prod_obj = self.pool.get('product.product')
        # id of corresponding purchase order line
        sol_id = context['sol_ids'][0]
        sol = sol_obj.browse(cr, uid, sol_id, context=context)
        # pricelist from purchase order
        pricelist_id = sol.order_id.pricelist_id.id
        # partner_id from purchase order
        partner_id = sol.order_id.partner_id.id
        # date_order from purchase order
        date_order = sol.order_id.date_order
        # fiscal_position from purchase order
        fiscal_position_id = sol.order_id.fiscal_position.id
        # date_planned from purchase order line
        date_planned = sol.date_planned
        # name
        name = False
        if product_id:
            name = prod_obj.read(cr, uid, product_id, ['name'], context=context)['name']
        # notes
        notes = sol.notes
        # state
        state = sol.order_id.state
        # gather default values
        if type == 'product_uom_change':
            data = getattr(sol_obj, type)(cr, uid, ids, pricelist=pricelist_id, product=product_id, qty=qty,
                                          uom=uom_id, qty_uos=qty, uos=uom_id, name=name, partner_id=partner_id,
                                          lang='lang' in context and context['lang'], update_tax=False, date_order=date_order)
        elif type == 'product_id_change':
            data = getattr(sol_obj, type)(cr, uid, ids, pricelist=pricelist_id, product=product_id, qty=qty,
                                             uom=uom_id, qty_uos=qty, uos=uom_id, name=name, partner_id=partner_id,
                                             lang='lang' in context and context['lang'], update_tax=True, date_order=date_order, packaging=False, fiscal_position=fiscal_position_id, flag=False)
        return data
    
    def on_product_id_change(self, cr, uid, ids, product_id, qty, uom_id, price_unit, context=None):
        '''
        core function from purchase order line
        
        def product_id_change(self, cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False, fiscal_position=False, date_planned=False,
            name=False, price_unit=False, notes=False):
        '''
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        # product change, we reset everything
        result = {'value': {'uom_id_kit_selection_sale_line': False,
                            'price_unit_kit_selection_sale_line': 0.0,
                            'qty_kit_selection_sale_line': 0.0}}
        # gather default values
#        data = self._call_sol_on_change(cr, uid, ids, product_id, qty, uom_id, price_unit, 'product_id_change', context=context)
        data = self._call_sol_on_change(cr, uid, ids, product_id, qty, uom_id, price_unit, type='product_id_change', context=context)
        
        # update result price_unit and default uom
        if 'price_unit' in data['value']:
            result['value'].update({'price_unit_kit_selection_sale_line': data['value']['price_unit']})
        if 'product_qty' in data['value']:
            result['value'].update({'qty_kit_selection_sale_line': data['value']['product_qty']})
        if 'product_uom' in data['value']:
            result['value'].update({'uom_id_kit_selection_sale_line': data['value']['product_uom']})
            
        return result
    
    def on_uom_id_change(self, cr, uid, ids, product_id, qty, uom_id, price_unit, context=None):
        '''
        core function from purchase order line
        
        def product_uom_change(self, cursor, user, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False):
        '''
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        # uom change - we reset the qty and price
        result = {'value': {'qty_kit_selection_sale_line': 0.0,
                            'price_unit_kit_selection_sale_line': 0.0}}
        # gather default values
        data = self._call_sol_on_change(cr, uid, ids, product_id, qty, uom_id, price_unit, type='product_uom_change', context=context)
        # update result price_unit and default uom
        if 'price_unit' in data['value']:
            result['value'].update({'price_unit_kit_selection_sale_line': data['value']['price_unit']})
        if 'product_qty' in data['value']:
            result['value'].update({'qty_kit_selection_sale_line': data['value']['product_qty']})
        return result
    
    def on_qty_change(self, cr, uid, ids, product_id, qty, uom_id, price_unit, context=None):
        '''
        core function from purchase order line
        
        def product_id_change(self, cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False, fiscal_position=False, date_planned=False,
            name=False, price_unit=False, notes=False):
        '''
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        # qty changed - we do not reset anything 
        result = {'value': {}}
        # gather default values
        data = self._call_sol_on_change(cr, uid, ids, product_id, qty, uom_id, price_unit, type='product_id_change', context=context)
        # update result price_unit and default uom
        if 'price_unit' in data['value']:
            result['value'].update({'price_unit_kit_selection_sale_line': data['value']['price_unit']})
        if 'product_uom' in data['value'] and not uom_id:
            result['value'].update({'uom_id_kit_selection_sale_line': data['value']['product_uom']})

        if qty:
            uom_id = result.get('value', {}).get('uom_id_kit_selection_sale_line', uom_id)
            result = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, qty, 'qty_kit_selection_sale_line', result=result)

        return result
    
    _columns = {'integrity_status': fields.selection(string=' ', selection=INTEGRITY_STATUS_SELECTION, readonly=True),
                'order_line_id_kit_selection_sale_line': fields.many2one('sale.order.line', string='Sale Order Line', readonly=True, required=True),
                'wizard_id_kit_selection_sale_line': fields.many2one('kit.selection.sale', string='Kit Selection wizard'),
                # data
                'product_id_kit_selection_sale_line': fields.many2one('product.product', string='Product', required=True),
                'qty_kit_selection_sale_line': fields.float(string='Qty', required=True, related_uom='uom_id_kit_selection_sale_line'),
                'uom_id_kit_selection_sale_line': fields.many2one('product.uom', string='UoM', required=True),
                'price_unit_kit_selection_sale_line': fields.float('Unit Price', required=True, digits_compute=dp.get_precision('Purchase Price')),
                }
    
    _defaults = {'integrity_status': 'empty',
                 }
    
kit_selection_sale_line()

