#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF.
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

import netsvc
import time

from tools.translate import _


class procurement_list_line_split(osv.osv_memory):
    _name = 'procurement.list.line.split'
    _description = 'Wizard to split a line into two lines'
    
    _columns = {
        'line_id': fields.many2one('procurement.list.line', string='Line to split'),
        'qty': fields.float(digits=(16,2), string='Quantity for the new line', required=True),
    }
    
    def default_get(self, cr, uid, fields, context={}):
        '''
        Fills information for the wizard
        '''
        line_obj = self.pool.get('procurement.list.line')
        
        res = super(procurement_list_line_split, self).default_get(cr, uid, fields, context)
        line_id = context.get('line_id', False)
        state = context.get('state', False)
        
        if not line_id:
            return res
        
        line = line_obj.browse(cr, uid, line_id, context=context)
        if state == 'done':
            raise osv.except_osv(_('Error'), _('You cannot split a line in a Closed Internal Request'))
        
        res['line_id'] = line_id
        
        # Default quantity = Old quantity divided by 2
        res['qty'] = line_obj.browse(cr, uid, line_id, context=context).product_qty/2
        
        return res
    
    def split(self, cr, uid, ids, context={}):
        '''
        Changes the quantity of the old line and creates a new line with the
        new quantity
        '''
        if ids and isinstance(ids, (int, long)):
            ids = [ids]
        line_obj = self.pool.get('procurement.list.line')
        
        for obj in self.browse(cr, uid, ids, context=context):
            # Returns an error if the quantity is negative
            if obj.qty < 0.00:
                raise osv.except_osv(_('Error'), _('The new quantity should be positive'))
            if obj.qty > obj.line_id.product_qty:
                raise osv.except_osv(_('Error'), _('The new quantity can\'t be superior to the quantity of initial line'))
            # Changes the quantity on the old line
            line_obj.write(cr, uid, [obj.line_id.id], {'product_qty': obj.line_id.product_qty-obj.qty})
            # Creates the new line with new quantity
            line_obj.create(cr, uid, {'list_id': obj.line_id.list_id.id,
                                      'product_id': obj.line_id.product_id.id,
                                      'product_uom_id': obj.line_id.product_uom_id.id,
                                      'product_qty': obj.qty,
                                      'supplier_id': False,
                                      'from_stock': obj.line_id.from_stock, 
                                     }
                            )
            
        return {'type': 'ir.actions.act_window_close'}
            
procurement_list_line_split()


class procurement_list_line_merge(osv.osv_memory):
    _name = 'procurement.list.line.merge'
    _description = 'Merge Lines'
    
    _columns = {
        'line_id': fields.many2one('procurement.list.line', string='Line to merged', readonly=True),
        'line_ids': fields.many2many('procurement.list.line', 'merge_line_rel', 'merge_id', 'line_id',
                                     string='Lines to merged'),
    }
    
    def default_get(self, cr, uid, fields, context={}):
        '''
        Initializes data with only lines with the same product and the same
        procurement list
        
        '''
        line_obj = self.pool.get('procurement.list.line')
        res = {}
        
        line_id = context.get('line_id', False)
        state = context.get('state', False)
        if not line_id:
            raise osv.except_osv(_('Error'), _('No lines to merged'))
        
        line = line_obj.browse(cr, uid, line_id, context=context)
        if state == 'done':
            raise osv.except_osv(_('Error'), _('You cannot merge a line in a Closed Internal Request'))
        product_id = line.product_id.id
        product_uom = line.product_uom_id.id
        wizard_id = line.list_id.id
        
        res['line_id'] = line_id
        res['line_ids']= line_obj.search(cr, uid, [('list_id', '=', wizard_id), 
                                                   ('product_id', '=', product_id),
                                                   ('product_uom_id', '=', product_uom)])
        
        if line_id in res['line_ids']:
            res['line_ids'].remove(line_id)
        
        return res
    
    def merge_confirm(self, cr, uid, ids, context={}):
        '''
        Merged lines
        '''
        if ids and isinstance(ids, (int, long)):
            ids = [ids]
        line_obj = self.pool.get('procurement.list.line')
        
        for obj in self.browse(cr, uid, ids, context=context):
            # Get the supplier of the main line because if merge no lines, 
            # the supplier shouldn't removed
            supplier_id = obj.line_id.supplier_id.id
            qty = obj.line_id.product_qty
            for line in obj.line_ids:
                qty += line.product_qty
                supplier_id = False
                line_obj.unlink(cr, uid, [line.id])
                
            line_obj.write(cr, uid, [obj.line_id.id], {'product_qty': qty, 'supplier_id': supplier_id})
            
        return {'type': 'ir.actions.act_window_close'}
            
procurement_list_line_merge()


class procurement_choose_supplier_rfq(osv.osv_memory):
    _name = 'procurement.choose.supplier.rfq'
    _description = 'Choose Supplier tp generate RfQ'

    _columns = {
        'choose_id': fields.many2one('procurement.list', string='Wizard'),
        'supplier_ids': fields.many2many('res.partner', 'supplier_rfq_rel', 'rfq_id', 'supplier_id',
                                         string='Suppliers', domain=[('supplier', '=', 1)]),
    }
    
    def default_get(self, cr, uid, fields, context={}):
        '''
        Fills information in the wizard 
        '''
        res = super(procurement_choose_supplier_rfq, self).default_get(cr, uid, fields, context=context)
        wizard_id = context.get('active_id', False)
        
        if not wizard_id:
            return res
        
        res['choose_id'] = wizard_id
        
        return res
    
    def create_rfq(self, cr, uid, ids, context={}):
        '''
        Creates Requests for Quotation for each supplier with all lines
        '''
        if ids and isinstance(ids, (int, long)):
            ids = [ids]
        order_obj = self.pool.get('purchase.order')
        order_line_obj = self.pool.get('purchase.order.line')
        proc_list_obj = self.pool.get('procurement.list')
        proc_line_obj = self.pool.get('procurement.list.line')
        
        po_ids = []  # List of all created RfQ
        
        for obj in self.browse(cr, uid, ids):
            origin = obj.choose_id.name
            location_id = proc_list_obj._get_location(cr, uid, obj.choose_id.warehouse_id)
            
            lines = []
            for l in obj.choose_id.line_ids: 
                lines.append({'line_id': l.id,
                              'product_id': l.product_id.id,
                              'product_uom': l.product_uom_id.id,
                              'product_name': l.product_id.name,
                              'product_qty': l.product_qty,})
             
            # Creates one RfQ for each supplier
            for s in obj.supplier_ids:
                address = s.address_get().get('default')
                if not address:
                    raise osv.except_osv(_('Error'), _('The supplier %s has no address defined on its form' %s.name))
                po_id = order_obj.create(cr, uid, {'partner_id': s.id,
                                                   'partner_address_id': address,
                                                   'pricelist_id': s.property_product_pricelist.id,
                                                   'origin': origin,
                                                   'location_id': location_id})
                po_ids.append(po_id)
                # Creates lines
                for l in lines:
                    order_line_obj.create(cr, uid, {'product_uom': l.get('product_uom'),
                                                    'product_id': l.get('product_id'),
                                                    'order_id': po_id,
                                                    'price_unit': 0.00,
                                                    'date_planned': obj.choose_id.order_date,
                                                    'product_qty': l.get('product_qty'),
                                                    'name': l.get('product_name'),
                                                    })
                    
        proc_id = self.browse(cr, uid, ids[0]).choose_id.id
        proc_list_obj.write(cr, uid, proc_id, {'state': 'done', 'order_ids': [(6, 0, po_ids)]})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', po_ids)]}

procurement_choose_supplier_rfq()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

