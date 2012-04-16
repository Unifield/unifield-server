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


class kit_selection(osv.osv_memory):
    '''
    kit selection
    '''
    _name = "kit.selection"
    _columns = {'product_id': fields.many2one('product.product', string='Kit Product', readonly=True),
                'kit_id': fields.many2one('composition.kit', string='Theoretical Kit'),
                'order_line_id_kit_selection': fields.many2one('purchase.order.line', string="Purchase Order Line", readonly=True, required=True),
                'product_ids_kit_selection': fields.one2many('kit.selection.line', 'wizard_id_kit_selection_line', string='Replacement Products'),
                }
    
    _defaults = {'product_id': lambda s, cr, uid, c: c.get('product_id', False),
                 'order_line_id_kit_selection': lambda s, cr, uid, c: c.get('active_ids') and c.get('active_ids')[0] or False,
                 }
    
    def import_items(self, cr, uid, ids, context=None):
        '''
        import lines into product_ids_kit_selection
        '''
        # objects
        line_obj = self.pool.get('kit.selection.line')
        
        for obj in self.browse(cr, uid, ids, context=context):
            if not obj.kit_id:
                raise osv.except_osv(_('Warning !'), _('A theoretical version should be selected.'))
            for item in obj.kit_id.composition_item_ids:
                values = {'order_line_id_kit_selection_line': obj.order_line_id_kit_selection.id,
                          'wizard_id_kit_selection_line': obj.id,
                          'product_id_kit_selection_line': item.item_product_id.id,
                          'qty_kit_selection_line': item.item_qty,
                          'uom_id_kit_selection_line': item.item_uom_id.id,
                          }
                line_obj.create(cr, uid, values, context=context)
        return True

    def do_de_kitting(self, cr, uid, ids, context=None):
        '''
        create a purchase order line for each kit item and delete the selected kit purchase order line
        '''
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        pol_obj = self.pool.get('purchase.order.line')
        # id of corresponding purchase order line
        pol_id = context['active_ids'][0]
        pol = pol_obj.browse(cr, uid, pol_id, context=context)
        for obj in self.browse(cr, uid, ids, context=context):
            if not len(obj.product_ids_kit_selection):
                raise osv.except_osv(_('Warning !'), _('Replacement Items must be selected.'))
            # for each item from the product_ids_kit_selection
            for item_v in obj.product_ids_kit_selection:
                # price unit is mandatory
                if item_v.price_unit <= 0.0:
                    raise osv.except_osv(_('Warning !'), _('Unit Price must be specified for each line.'))
                # selected product_id
                product_id = item_v.product_id_kit_selection_line.id
                # selected qty
                qty = item_v.qty_kit_selection_line
                # selected uom
                uom_id = item_v.uom_id_kit_selection_line.id
                # pricelist from purchase order
                pricelist_id = pol.order_id.pricelist_id.id
                # partner_id from purchase order
                partner_id = pol.order_id.partner_id.id
                # date_order from purchase order
                date_order = pol.order_id.date_order
                # fiscal_position from purchase order
                fiscal_position_id = pol.order_id.fiscal_position.id
                # date_planned from purchase order line
                date_planned = pol.date_planned
                # gather default values
                data = pol_obj.product_id_change(cr, uid, ids, pricelist=pricelist_id, product=product_id, qty=qty, uom=uom_id,
                                                 partner_id=partner_id, date_order=date_order, fiscal_position=fiscal_position_id, date_planned=date_planned,
                                                 name=False, price_unit=0.0, notes=False)
                # copy original purchase order line # deprecated
                data['value'].update({'product_id': product_id, 'product_qty': pol.product_qty*qty})
                # create a new pol
                p_values = {'product_id': product_id,
                            'product_qty': pol.product_qty*qty,
                            'price_unit': item_v.price_unit,
                            'product_uom': uom_id,
                            'default_code': data['value']['default_code'],
                            'name': data['value']['name'],
                            'date_planned': pol.date_planned,
                            'confirmed_delivery_date': pol.confirmed_delivery_date,
                            'default_name': data['value']['default_name'],
                            'order_id': pol.order_id.id,
                            'notes': pol.notes,
                            'comment': pol.comment,
                            'procurement_id': pol.procurement_id.id,
                            'partner_id': pol.partner_id.id,
                            'company_id': pol.company_id.id,
                            'state': pol.state,
                            }
                new_id = pol_obj.create(cr, uid, p_values, context=context)
                
        # delete the pol
        pol_obj.unlink(cr, uid, [pol_id], context=context)
                
        return {'type': 'ir.actions.act_window_close'}
    
kit_selection()


class kit_selection_line(osv.osv_memory):
    '''
    substitute items
    '''
    _name = 'kit.selection.line'
    
    def create(self, cr, uid, vals, context=None):
        '''
        default price unit from pol on_change function
        '''
        # objects
        pol_obj = self.pool.get('purchase.order.line')
        # id of corresponding purchase order line
        pol_id = context.get('active_ids', False) and context['active_ids'][0]
        if pol_id and ('price_unit' not in vals or vals.get('price_unit') == 0.0):
            pol = pol_obj.browse(cr, uid, pol_id, context=context)
            # selected product_id
            product_id = vals.get('product_id_kit_selection_line', False)
            # selected qty
            qty = vals.get('qty_kit_selection_line', 0.0)
            # selected uom
            uom_id = vals.get('uom_id_kit_selection_line', False)
            # pricelist from purchase order
            pricelist_id = pol.order_id.pricelist_id.id
            # partner_id from purchase order
            partner_id = pol.order_id.partner_id.id
            # date_order from purchase order
            date_order = pol.order_id.date_order
            # fiscal_position from purchase order
            fiscal_position_id = pol.order_id.fiscal_position.id
            # date_planned from purchase order line
            date_planned = pol.date_planned
            # gather default values
            data = pol_obj.product_id_change(cr, uid, context['active_ids'], pricelist=pricelist_id, product=product_id, qty=qty, uom=uom_id,
                                             partner_id=partner_id, date_order=date_order, fiscal_position=fiscal_position_id, date_planned=date_planned,
                                             name=False, price_unit=0.0, notes=False)
            # update price_unit value
            vals.update({'price_unit': data['value']['price_unit']})
        return super(kit_selection_line, self).create(cr, uid, vals, context=context)
    
    def on_change_product_id(self, cr, uid, ids, product_id, context=None):
        '''
        on change
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        # default value
        result = {'value': {'qty_kit_selection_line': 0.0, 'uom_id_kit_selection_line': False}}
        if product_id:
            uom_id = prod_obj.browse(cr, uid, product_id, context=context).uom_id.id
            result['value'].update({'uom_id_kit_selection_line': uom_id})
        return result
    
    _columns = {'order_line_id_kit_selection_line': fields.many2one('purchase.order.line', string="Purchase Order Line", readonly=True, required=True),
                'wizard_id_kit_selection_line': fields.many2one('kit.selection', string='Kit Selection wizard'),
                # data
                'product_id_kit_selection_line': fields.many2one('product.product', string='Product', required=True),
                'qty_kit_selection_line': fields.float(string='Qty', digits_compute=dp.get_precision('Product UoM'), required=True),
                'uom_id_kit_selection_line': fields.many2one('product.uom', string='UoM', required=True),
                'price_unit': fields.float('Unit Price', required=True, digits_compute=dp.get_precision('Purchase Price')),
                }
    
kit_selection_line()


