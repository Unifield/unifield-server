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

from osv import osv
from osv import fields

import netsvc

from tools.translate import _

class wizard_compare_rfq(osv.osv_memory):
    _name = 'wizard.compare.rfq'
    _description = 'Compare Quotations'
    
    _columns = {
        'rfq_number': fields.integer(string='# of Quotations', readonly=True),
        'line_ids': fields.one2many('wizard.compare.rfq.line', 'compare_id', string='Lines'),
    }

    def start_compare_rfq(self, cr, uid, ids, context={}):
        order_obj = self.pool.get('purchase.order')
        compare_line_obj = self.pool.get('wizard.compare.rfq.line')
        
        # openERP BUG ?
        ids = context.get('active_ids',[])
        
        if not ids:
            raise osv.except_osv(_('Error'), _('No quotation found !'))
        if len(ids) < 2:
            raise osv.except_osv(_('Error'), _('You should select at least two quotations to compare !'))
            
        products = {}
        line_ids = []
        
        for o in order_obj.browse(cr, uid, ids, context=context):
            if o.state != 'draft':
                raise osv.except_osv(_('Error'), _('You cannot compare confirmed Quotations !'))
            for l in o.order_line:
                if l.price_unit > 0.00:
                    if not products.get(l.product_id.id, False):
                        products[l.product_id.id] = {'product_id': l.product_id.id, 'po_line_ids': []}
                    products[l.product_id.id]['po_line_ids'].append(l.id)
                
        for p_id in products:
            p = products.get(p_id)
            po_line_ids= []
            for po_line in p.get('po_line_ids'):
                po_line_ids.append(po_line)
            cmp_line_ids = compare_line_obj.search(cr, uid, [('product_id', '=', p.get('product_id'))])
            if not cmp_line_ids or not context.get('end_wizard', False):
                line_ids.append((0, 0, {'product_id': p.get('product_id'), 'po_line_ids': [(6,0,po_line_ids)]}))

            else:
                line_ids.append((0, 0, cmp_line_ids[0]))
             
        rfq_compare_obj = self.pool.get('wizard.compare.rfq')
        newid = rfq_compare_obj.create(cr, uid, {'rfq_number': len(ids), 'line_ids': line_ids})
        
        return {'type': 'ir.actions.act_window',
            'res_model': 'wizard.compare.rfq',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': newid,
            'context': context,
           }
        
    def create_po(self, cr, uid, ids, context={}):
        '''
        Creates PO according to the selection
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        po_line_obj = self.pool.get('purchase.order.line')
        po_obj = self.pool.get('purchase.order')
        
        po_ids= []
        
        for wiz in self.browse(cr, uid, ids, context=context):
            # For each line, delete non selected lines
            unlink_lines = []
            for product_line in wiz.line_ids:
                for po_line in product_line.po_line_ids:
                    if po_line.order_id.partner_id.id != product_line.supplier_id.id:
                        unlink_lines.append(po_line.id)
                        # Save the order list
                        if po_line.order_id.id not in po_ids:
                            po_ids.append(po_line.order_id.id)
                        
            
            # Unlink lines
            po_line_obj.unlink(cr, uid, unlink_lines, context=context)
            # Unlink order with no lines
            for po in po_obj.browse(cr, uid, po_ids):
                # Unlink lines with unit price equal to 0.00
                for line in po.order_line:
                    if line.price_unit == 0.00:
                        po_line_obj.unlink(cr, uid, [line.id], context=context)
                if len(po.order_line) == 0:
                    po_ids.remove(po.id)
                    po_obj.unlink(cr, uid, [po.id], context=context)
                    
            # Confirm all other PO
            wf_service = netsvc.LocalService("workflow")
            for po in po_ids:
                wf_service.trg_validate(uid, 'purchase.order', po, 'purchase_confirm', cr)
                
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', po_ids)],
                'context': context
                }
            
wizard_compare_rfq()


class wizard_compare_rfq_line(osv.osv_memory):
    _name = 'wizard.compare.rfq.line'
    _description = 'Compare Quotation Line'
    
    _columns = {
        'compare_id': fields.many2one('wizard.compare.rfq', string='Wizard'),
        'product_id': fields.many2one('product.product', string='Product'),
        'supplier_id': fields.many2one('res.partner', string='Supplier'),
        'po_line_ids': fields.many2many('purchase.order.line', 'rfq_po_line_rel', 'compare_id', 'line_id',
                                       string='Quotation Line'),
    }
    
    def choose_supplier(self, cr, uid, ids, context={}):
        '''
        Opens a wizard to compare and choose a supplier for this line
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]        
        
        choose_sup_obj = self.pool.get('wizard.choose.supplier')
        choose_line_obj = self.pool.get('wizard.choose.supplier.line')
        line_id = self.browse(cr, uid, ids[0], context=context)
        
        line_data = {'product_id': line_id.product_id.id,
                     'compare_id': line_id.id}
        
        if line_id.supplier_id and line_id.supplier_id.id:
            line_data.update({'supplier_id': line_id.supplier_id.id})
        
        new_id = choose_sup_obj.create(cr, uid, line_data, context=context)
        
        line_ids = []
        for l in line_id.po_line_ids:
            line_ids.append(choose_line_obj.create(cr, uid, {'supplier_id': l.order_id.partner_id.id,
                                                             'po_line_id': l.id,
                                                             'price_unit': l.price_unit,
                                                             'qty': l.product_qty,
                                                             'compare_line_id': line_id.id,
                                                             'compare_id': line_id.compare_id.id,
                                                             'price_total': l.product_qty*l.price_unit}))
        choose_sup_obj.write(cr, uid, [new_id], {'line_ids': [(6,0,line_ids)]})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.choose.supplier',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': new_id,
                'context': context,
                }
    
wizard_compare_rfq_line()


class wizard_choose_supplier(osv.osv_memory):
    _name = 'wizard.choose.supplier'
    _description = 'Choose a supplier'
    
    _columns = {
        'product_id': fields.many2one('product.product', string='Product'),
        'supplier_id': fields.many2one('res.partner', string='Supplier'),
        'line_ids': fields.many2many('wizard.choose.supplier.line', 'choose_supplier_line', 'init_id', 'line_id',
                                     string='Lines'),
        'compare_id': fields.many2one('wizard.compare.rfq.line', string='Wizard'),
    }
    
    def return_view(self, cr, uid, ids, context={}):
        '''
        Return to the main wizard
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        obj = self.browse(cr, uid, ids[0])
            
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.compare.rfq',
                'view_mode': 'form',
                'view_type': 'form',
                'target': 'new',
                'res_id': obj.compare_id.compare_id.id,
                'context': context}
    
wizard_choose_supplier()


class wizard_choose_supplier_line(osv.osv_memory):
    _name = 'wizard.choose.supplier.line'
    _description = 'Line Choose supplier wizard'
    
    _order = 'price_unit'
    
    _columns = {
        'compare_id': fields.many2one('wizard.compare.rfq', string='Compare'),
        'compare_line_id': fields.many2one('wizard.compare.rfq.line', string='Compare Line'),
        'po_line_id': fields.many2one('purchase.order.line', string='PO Line'),
        'supplier_id': fields.many2one('res.partner', string='Supplier'),
        'price_unit': fields.float(digits=(16,2), string='Unit Price'),
        'qty': fields.float(digits=(16,2), string='Qty'),
        'price_total': fields.float(digits=(16,2), string='Total Price'),
    }
    
    def write(self, cr, uid, ids, data, context={}):
        '''
        Change the quantity on the purchase order line if 
        it's modified on the supplier choose line
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        if 'qty' in data:
            for line in self.browse(cr, uid, ids):
                self.pool.get('purchase.order.line').write(cr, uid, [line.po_line_id.id], {'product_qty': data.get('qty', line.qty)})
                
        return super(wizard_choose_supplier_line, self).write(cr, uid, ids, data, context=context)
    
    def choose_supplier(self, cr, uid, ids, context={}):
        '''
        Define the supplier for the line
        '''
        compare_obj = self.pool.get('wizard.compare.rfq')
        compare_line_obj = self.pool.get('wizard.compare.rfq.line')
        
        if isinstance(ids, (int, long)):
                      ids = [ids]
        
        line_id = self.browse(cr, uid, ids[0])
        
        compare_line_obj.write(cr, uid, [line_id.compare_line_id.id], {'supplier_id': line_id.supplier_id.id})
        
        context.update({'end_wizard': True})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.compare.rfq',
                'view_mode': 'form',
                'view_type': 'form',
                'target': 'new',
                'res_id': line_id.compare_id.id,
                'context': context,
                }
    
wizard_choose_supplier_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
