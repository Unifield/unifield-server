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
    wizard called to confirm an action
    '''
    _name = "kit.selection"
    _columns = {'product_id': fields.many2one('product.product', string='Kit Product', readonly=True),
                'kit_id': fields.many2one('composition.kit', string='Theoretical Kit', required=True),
                'question': fields.text(string='Question', readonly=True),
                }
    
    _defaults = {'product_id': lambda s, cr, uid, c: c.get('product_id', False),
                 'question': lambda s, cr, uid, c: c.get('question', False)}

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
            if not obj.kit_id:
                raise osv.except_osv(_('Warning !'), _('A theoretical version should be selected.'))
            # for each item from the theoretical kit
            for item_v in obj.kit_id.composition_item_ids:
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
                data = pol_obj.product_id_change(cr, uid, ids, pricelist=pricelist_id, product=item_v.item_product_id.id, qty=item_v.item_qty, uom=item_v.item_uom_id.id,
                                                 partner_id=partner_id, date_order=date_order, fiscal_position=fiscal_position_id, date_planned=date_planned,
                                                 name=False, price_unit=0.0, notes=False)
                # copy original purchase order line
                data['value'].update({'product_id': item_v.item_product_id.id, 'product_qty': pol.product_qty*item_v.item_qty})
                p_values = {'product_id': item_v.item_product_id.id,
                            'product_qty': pol.product_qty*item_v.item_qty,
                            'price_unit': data['value']['price_unit'],
                            'product_uom': item_v.item_uom_id.id,
                            'default_code': data['value']['default_code'],
                            'name': data['value']['name'],
                            'date_planned': pol.date_planned,
                            'confirmed_delivery_date': pol.confirmed_delivery_date,
                            'default_name': data['value']['default_name'],
                            'order_id': pol.order_id.id,
                            'notes': pol.notes,
                            'comment': pol.comment,
                            }
                new_id = pol_obj.create(cr, uid, p_values, context=context)
                
        # delete the pol
        pol_obj.unlink(cr, uid, [pol_id], context=context)
                
        return {'type': 'ir.actions.act_window_close'}
    
kit_selection()
