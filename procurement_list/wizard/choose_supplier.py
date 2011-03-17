#!/usr/bin/env python
# -*- encoding: utf-8 -*-
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

from osv import osv
from osv import fields

import netsvc
import time

from tools.translate import _


class procurement_choose_supplier(osv.osv_memory):
    _name = 'procurement.choose.supplier'
    _description = 'Choose supplier'

    _columns = {
        'list_id': fields.many2one('procurement.list', string='Procurement List'),
        'date': fields.date(string='Date', readonly=True),
        'line_ids': fields.one2many('procurement.choose.supplier.line', 'wizard_id', string='Procurement Lines'),
    }
    
    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d'),
    }
    
    def start_choose_supplier(self, cr, uid, ids, context={}):
        '''
        Fills fields of the wizard
        '''
        if ids and isinstance(ids, (int, long)):
            ids = [ids]
            
        proc_list_obj = self.pool.get('procurement.list')

        procurement_ids = context.get('active_ids', [])
        if not procurement_ids:
            return res

        result = []
        for procurement in proc_list_obj.browse(cr, uid, procurement_ids, context=context):
            # Check if the list is in 'draft' state
            if procurement.state != 'draft':
                raise osv.except_osv(_('Error'), _('You can only choose suppliers for procurement list in \'Draft\' state'))
            for l in procurement.line_ids:
                result.append((0, 0, self._create_memory_line(l)))
            
        new_id = self.create(cr, uid, {'date': time.strftime('%Y-%m-%d'),
                                       'list_id': procurement_ids[0],
                                       'line_ids': result})
            
        return {'type': 'ir.actions.act_window',
                'res_model': 'procurement.choose.supplier',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': new_id,
                'context': context,
               }

    def _create_memory_line(self, line):
        '''
        Return data of new procurement_choose_supplier_line
        '''
        line_memory = {
            'line_id': line.id,
            'product_id': line.product_id.id,
            'product_uom': line.product_uom_id.id,
            'product_qty': line.product_qty,
            'supplier_id': line.product_id.seller_id.id,
        }

        return line_memory

    def create_po(self, cr, uid, ids, context={}):
        '''
        Creates all purchase orders according to choices on wizard
        '''
        if ids and isinstance(ids, (int, long)):
            ids = [ids]
            
        order_obj = self.pool.get('purchase.order')
        order_line_obj = self.pool.get('purchase.order.line')
        proc_obj = self.pool.get('procurement.list')
        line_obj = self.pool.get('procurement.choose.supplier.line')
        prod_sup_obj = self.pool.get('product.supplierinfo')

        # We search if at least one line hasn't defined supplier
        line_without = line_obj.search(cr, uid, [('wizard_id', 'in', ids), ('supplier_id', '=', False)])
        if line_without:
            raise osv.except_osv(_('Error'), _('You cannot create purchase orders while all lines haven\'t a defined supplier'))

        # We search lines group by supplier_id
        po_exists = {}
        po_id = False
        po_ids = []
        line_ids = line_obj.search(cr, uid, [('wizard_id', 'in', ids)], order='supplier_id')
        for l in line_obj.browse(cr, uid, line_ids):
            # Search if a PO already exists in the system
            if not po_exists.get(l.supplier_id.id, False):
                # If no PO in local memory, search in DB
                po_exist = order_obj.search(cr, uid, [('origin', '=', l.line_id.list_id.name), ('partner_id', '=', l.supplier_id.id)])
                if po_exist:
                    # A PO exists in DB, set the id in local memory
                    po_exists[l.supplier_id.id] = po_exist[0]
                else: 
                    # try to create a new PO, and set its id in local memory
                    address = l.supplier_id.address_get().get('default')
                    # Returns an error when the supplier has not defined address
                    if not address:
                        raise osv.except_osv(_('Error'), _('The supplier %s has no address defined on its form' %l.supplier_id.name))
                    # When starting or when the supplier changed, we create a Purchase Order
                    po_id = order_obj.create(cr, uid, {'partner_id': l.supplier_id.id,
                                                       'partner_address_id': address,
                                                       'pricelist_id': l.supplier_id.property_product_pricelist.id,
                                                       'origin': l.line_id.list_id.name,
                                                       'location_id': proc_obj._get_location(cr, uid, l.line_id.list_id.warehouse_id)})
                    po_exists[l.supplier_id.id] = po_id

            # Get the PO id in local memory
            po_id = po_exists.get(l.supplier_id.id)
                
            # We create all lines for this supplier
            price_unit = prod_sup_obj.price_get(cr, uid, [l.supplier_id.id], l.product_id.id, l.product_qty)
            order_line_obj.create(cr, uid, {'product_uom': l.product_uom.id,
                                            'product_id': l.product_id.id,
                                            'order_id': po_id,
                                            'price_unit': price_unit[l.supplier_id.id],
                                            'date_planned': l.wizard_id.date,
                                            'product_qty': l.product_qty,
                                            'name': l.product_id.name,})

        for supplier in po_exists:
            po_ids.append(po_exists.get(supplier))

        # We confirm all created orders
        wf_service = netsvc.LocalService("workflow")
        for po in po_ids:
            wf_service.trg_validate(uid, 'purchase.order', po, 'purchase_confirm', cr)

        proc_id = self.browse(cr, uid, ids[0]).list_id.id
        proc_obj.write(cr, uid, proc_id, {'state': 'done', 'order_ids': [(6, 0, po_ids)]}) 

        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', po_ids)],
               }
        
    def create_rfq(self, cr, uid, ids, context={}):
        '''
        Returns the wizard to choose a list of supplier  
        '''
        if ids and isinstance(ids, (int, long)):
            ids = [ids]
        context.update({'wizard_id': ids[0]})
        return {'type': 'ir.actions.act_window',
                'res_model': 'procurement.choose.supplier.rfq',
                'view_mode': 'form',
                'view_type': 'form',
                'target': 'new',
                'opened': False,
                'context': context,
               }
        
procurement_choose_supplier()


class procurement_choose_supplier_line(osv.osv_memory):
    _name = 'procurement.choose.supplier.line'
    _description = 'Choose supplier line'

    _columns = {
        'wizard_id': fields.many2one('procurement.choose.supplier', string='Wizard', required=True),
        'line_id': fields.many2one('procurement.list.line', string='Procurement Line'),
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'product_uom': fields.many2one('product.uom', string='UoM', required=True),
        'product_qty': fields.float(digits=(16,2), string='Qty', required=True),
        'supplier_id': fields.many2one('res.partner', string='Supplier', domain=[('supplier', '=', 1)]),
    }
    
    def split_line(self, cr, uid, ids, context={}):
        '''
        Split a line into two lines
        '''
        if ids and isinstance(ids, (int, long)):
            ids = [ids]
        context.update({'line_id': ids[0]})
        return {'type': 'ir.actions.act_window',
                'res_model': 'procurement.choose.line.split',
                'target': 'new',
                'view_type': 'form',
                'view_mode': 'form',
                'context': context,
                }
        
    def merge_line(self, cr, uid, ids, context={}):
        '''
        Merges two lines
        '''
        if ids and isinstance(ids, (int, long)):
            ids = [ids]
        context.update({'line_id': ids[0]})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'procurement.choose.line.merge',
                'target': 'new',
                'view_type': 'form',
                'view_mode': 'form',
                'context': context,
                }

procurement_choose_supplier_line()


class procurement_choose_supplier_line_split(osv.osv_memory):
    _name = 'procurement.choose.line.split'
    _description = 'Wizard to split a line into two lines'
    
    _columns = {
        'line_id': fields.many2one('procurement.choose.supplier.line', string='Line to split'),
        'qty': fields.float(digits=(16,2), string='Quantity for the new line', required=True),
    }
    
    def default_get(self, cr, uid, fields, context={}):
        '''
        Fills information for the wizard
        '''
        line_obj = self.pool.get('procurement.choose.supplier.line')
        
        res = super(procurement_choose_supplier_line_split, self).default_get(cr, uid, fields, context)
        line_id = context.get('line_id', False)
        
        if not line_id:
            return res
        
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
        line_obj = self.pool.get('procurement.choose.supplier.line')
        
        for obj in self.browse(cr, uid, ids, context=context):
            # Returns an error if the quantity is negative
            if obj.qty < 0.00:
                raise osv.except_osv(_('Error'), _('The new quantity should be positive'))
            if obj.qty > obj.line_id.product_qty:
                raise osv.except_osv(_('Error'), _('The new quantity can\'t be superior to the quantity of initial line'))
            # Changes the quantity on the old line
            line_obj.write(cr, uid, [obj.line_id.id], {'product_qty': obj.line_id.product_qty-obj.qty})
            # Creates the new line with new quantity
            line_obj.create(cr, uid, {'wizard_id': obj.line_id.wizard_id.id,
                                      'line_id': obj.line_id.line_id.id,
                                      'product_id': obj.line_id.product_id.id,
                                      'product_uom': obj.line_id.product_uom.id,
                                      'product_qty': obj.qty,
                                      'supplier_id': False,})
            
        return self.return_view(cr, uid, ids, context=context)
        
    def return_view(self, cr, uid, ids, context={}):
        '''
        Return the main view
        '''
        if ids and isinstance(ids, (int, long)):
            ids = [ids]
        res_id = False
        
        for obj in self.browse(cr, uid, ids, context=context):
            res_id = obj
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'procurement.choose.supplier',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': obj.line_id.wizard_id.id,
               }
    
procurement_choose_supplier_line_split()


class procurement_choose_supplier_line_merge(osv.osv_memory):
    _name = 'procurement.choose.line.merge'
    _description = 'Merge Lines'
    
    _columns = {
        'line_id': fields.many2one('procurement.choose.supplier.line', string='Line to merged', readonly=True),
        'line_ids': fields.many2many('procurement.choose.supplier.line', 'merge_line_rel', 'merge_id', 'line_id',
                                     string='Lines to merged'),
    }
    
    def default_get(self, cr, uid, fields, context={}):
        '''
        Initializes data with only lines with the same product and the same
        procurement list
        
        '''
        line_obj = self.pool.get('procurement.choose.supplier.line')
        res = {}
        
        line_id = context.get('line_id', False)
        if not line_id:
            raise osv.except_osv(_('Error'), _('No lines to merged'))
        
        line = line_obj.browse(cr, uid, line_id, context=context)
        product_id = line.product_id.id
        product_uom = line.product_uom.id
        wizard_id = line.wizard_id.id
        
        res['line_id'] = line_id
        res['line_ids']= line_obj.search(cr, uid, [('wizard_id', '=', wizard_id), 
                                                   ('product_id', '=', product_id),
                                                   ('product_uom', '=', product_uom)])
        
        if line_id in res['line_ids']:
            res['line_ids'].remove(line_id)
        
        return res
    
    def merge_confirm(self, cr, uid, ids, context={}):
        '''
        Merged lines
        '''
        if ids and isinstance(ids, (int, long)):
            ids = [ids]
        line_obj = self.pool.get('procurement.choose.supplier.line')
        
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
            
        return self.return_view(cr, uid, ids, context=context)
        
    def return_view(self, cr, uid, ids, context={}):
        '''
        Return the main view
        '''
        if ids and isinstance(ids, (int, long)):
            ids = [ids]
        res_id = False
        
        for obj in self.browse(cr, uid, ids, context=context):
            res_id = obj
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'procurement.choose.supplier',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': obj.line_id.wizard_id.id,
               }
        
    
procurement_choose_supplier_line_merge()


class procurement_choose_supplier_rfq(osv.osv_memory):
    _name = 'procurement.choose.supplier.rfq'
    _description = 'Choose Supplier tp generate RfQ'

    _columns = {
        'choose_id': fields.many2one('procurement.choose.supplier', string='Wizard'),
        'supplier_ids': fields.many2many('res.partner', 'supplier_rfq_rel', 'rfq_id', 'supplier_id',
                                         string='Suppliers', domain=[('supplier', '=', 1)]),
    }
    
    def default_get(self, cr, uid, fields, context={}):
        '''
        Fills information in the wizard 
        '''
        res = super(procurement_choose_supplier_rfq, self).default_get(cr, uid, fields, context=context)
        wizard_id = context.get('wizard_id', False)
        
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
            origin = obj.choose_id.list_id.name
            location_id = proc_list_obj._get_location(cr, uid, obj.choose_id.list_id.warehouse_id)
            
            lines = []
            for l in obj.choose_id.line_ids: 
                lines.append({'line_id': l.line_id,
                              'product_id': l.product_id.id,
                              'product_uom': l.product_uom.id,
                              'product_name': l.product_id.name,
                              'product_qty': l.product_qty,})
             
            # Creates one RfQ for each supplier
            for s in obj.supplier_ids:
                po_id = order_obj.create(cr, uid, {'partner_id': s.id,
                                                   'partner_address_id': s.address_get().get('default'),
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
                                                    'date_planned': obj.choose_id.date,
                                                    'product_qty': l.get('product_qty'),
                                                    'name': l.get('product_name'),
                                                    })
                    
        proc_id = self.browse(cr, uid, ids[0]).choose_id.list_id.id
        proc_list_obj.write(cr, uid, proc_id, {'state': 'done', 'order_ids': [(6, 0, po_ids)]})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', po_ids)]}
        
    def return_view(self, cr, uid, ids, context={}):
        '''
        Return the main view
        '''
        if ids and isinstance(ids, (int, long)):
            ids = [ids]
        res_id = False        
        for obj in self.browse(cr, uid, ids, context=context):
            res_id = obj
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'procurement.choose.supplier',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': obj.choose_id.id,
               }

procurement_choose_supplier_rfq()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

