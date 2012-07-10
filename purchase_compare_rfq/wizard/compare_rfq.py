# -*- coding: utf-8 -*-
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

from tools.translate import _

class wizard_compare_rfq(osv.osv_memory):
    _name = 'wizard.compare.rfq'
    _description = 'Compare Quotations'
    
    _columns = {
        'rfq_number': fields.integer(string='# of Quotations', readonly=True),
        'line_ids': fields.one2many('wizard.compare.rfq.line', 'compare_id', string='Lines'),
        'tender_id': fields.many2one('tender', string="Tender", readonly=True,)
    }

    def start_compare_rfq(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        order_obj = self.pool.get('purchase.order')
        compare_line_obj = self.pool.get('wizard.compare.rfq.line')
        
        # openERP BUG ?
        ids = context.get('active_ids',[])
        
        # tender reference
        tender_id = context.get('tender_id', False)
        
        # already compared values
        suppliers = context.get('suppliers', False)
        
        if not ids:
            raise osv.except_osv(_('Error'), _('No quotation found !'))
#        if len(ids) < 2:
#            raise osv.except_osv(_('Error'), _('You should select at least two quotations to compare !'))
            
        products = {}
        line_ids = []
        
        for o in order_obj.browse(cr, uid, ids, context=context):
            if o.state != 'draft' and o.state != 'rfq_updated':
                raise osv.except_osv(_('Error'), _('You cannot compare confirmed Purchase Order !'))
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
                product_id = p.get('product_id')
                values = {'product_id': product_id, 'po_line_ids': [(6,0,po_line_ids)], 'supplier_id': suppliers and suppliers.get(product_id, False) or False,}
                line_ids.append((0, 0, values))

            else:
                line_ids.append((0, 0, cmp_line_ids[0]))
             
        rfq_compare_obj = self.pool.get('wizard.compare.rfq')
        newid = rfq_compare_obj.create(cr, uid, {'rfq_number': len(ids), 'line_ids': line_ids, 'tender_id': tender_id}, context=context)
        
        return {'type': 'ir.actions.act_window',
            'res_model': 'wizard.compare.rfq',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': newid,
            'context': context,
           }
        
    def update_tender(self, cr, uid, ids, context=None):
        '''
        update the corresponding tender lines
        
        related rfq line: po_line_id.id
        '''
        tender_obj = self.pool.get('tender')
        for wiz in self.browse(cr, uid, ids, context=context):
            # loop through wizard_compare_rfq_line
            tender_id = wiz.tender_id.id
            for wiz_line in wiz.line_ids:
                # check if a supplier has been selected for this product
                if wiz_line.po_line_id:
                    # update the tender lines with corresponding product_id
                    updated_lines = [] # use to store the on-the-fly lines
                    for tender in tender_obj.browse(cr, uid, [wiz.tender_id.id], context=context):
                        for tender_line in tender.tender_line_ids:
                            if tender_line.product_id.id == wiz_line.product_id.id:
                                values = {'purchase_order_line_id': wiz_line.po_line_id.id,}
                                tender_line.write(values, context=context)
                                updated_lines.append(tender_line.id);
                                
                        # UF-733: if all tender lines have been compared (have PO Line id), then set the tender to be ready
                        # for proceeding to other actions (create PO, Done etc)
                        if tender.internal_state == 'draft':
                            flag = True
                            for line in tender.tender_line_ids:
                                if line.id not in updated_lines and not line.purchase_order_line_id:
                                    flag = False
                            if flag:
                                tender_obj.write(cr, uid, tender.id, {'internal_state': 'updated'})

            # display the corresponding tender                                
            return {'type': 'ir.actions.act_window',
                    'res_model': 'tender',
                    'view_type': 'form',
                    'view_mode': 'form,tree',
                    'target': 'crush',
                    'res_id': tender_id,
                    'context': context
                    }
        
    def create_po(self, cr, uid, ids, context=None):
        '''
        Creates PO according to the selection
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        po_line_obj = self.pool.get('purchase.order.line')
        po_obj = self.pool.get('purchase.order')
        
        po_ids= []
        
        for wiz in self.browse(cr, uid, ids, context=context):
            # For each line, delete non selected lines
            unlink_lines = []
            non_choosen_lines = []
            choosen_lines = []
            for product_line in wiz.line_ids:
                for po_line in product_line.po_line_ids:
                    # Save the order list
                    if po_line.order_id.id not in po_ids:
                        po_ids.append(po_line.order_id.id)
                    if product_line.po_line_id and po_line.id != product_line.po_line_id.id:
                        unlink_lines.append(po_line.id)
                    elif product_line.po_line_id and po_line.id == product_line.po_line_id.id:
                        choosen_lines.append(po_line.id)
                    else:
                        non_choosen_lines.append(po_line.id)
            
            # Unlink lines
            po_line_obj.unlink(cr, uid, unlink_lines, context=context)
            
            wf_service = netsvc.LocalService("workflow")
            
            # Unlink order with no lines
            returned_po = []
            for po in po_obj.browse(cr, uid, po_ids):
                new_lines = []
                validate_po = True
                # Unlink lines with unit price equal to 0.00
                for line in po.order_line:
                    if line.price_unit == 0.00:
                        po_line_obj.unlink(cr, uid, [line.id], context=context)
                    elif line.id in choosen_lines:
                        new_lines.append(line.id)
                    elif line.id in non_choosen_lines:
                        validate_po = False
                        
                if new_lines and len(new_lines) != len(po.order_line): # We create a new PO for confirmed lines
                    new_po_id = po_obj.copy(cr, uid, po.id, {'order_lines': (6, 0, [])})
                    # Delete all lines generated by the copy of the old PO
                    for new_l in po_obj.browse(cr, uid, new_po_id).order_line:
                        po_line_obj.unlink(cr, uid, new_l.id)
                    # Move the PO line to the new PO
                    po_line_obj.write(cr, uid, new_lines, {'order_id': new_po_id})
                    # Validate the new PO
                    wf_service.trg_validate(uid, 'purchase.order', new_po_id, 'purchase_confirm', cr)
                    returned_po.append(new_po_id)
                elif len(po.order_line) == 0:   # We remove all purchase line which haven't lines
                    po_ids.remove(po.id)
                    po_obj.unlink(cr, uid, [po.id], context=context)
                elif validate_po:   # We validate the PO if all lines of this PO are confirmed
                    wf_service.trg_validate(uid, 'purchase.order', po.id, 'purchase_confirm', cr)
                    returned_po.append(po.id)


        context['search_default_draft'] = 0 
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', returned_po)],
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
        'po_line_id': fields.many2one('purchase.order.line', string='Selected line'),
        'po_line_ids': fields.many2many('purchase.order.line', 'rfq_po_line_rel', 'compare_id', 'line_id',
                                       string='Quotation Line'),
    }
    
    def choose_supplier(self, cr, uid, ids, context=None):
        '''
        Opens a wizard to compare and choose a supplier for this line
        '''
        if context is None:
            context = {}
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
                                                             'notes': l.notes,
                                                             'compare_line_id': line_id.id,
                                                             'compare_id': line_id.compare_id.id,
                                                             'currency_id': l.order_id.pricelist_id.currency_id.id,
                                                             'price_total': l.product_qty*l.price_unit}))
        choose_sup_obj.write(cr, uid, [new_id], {'line_ids': [(6,0,line_ids)],
                                                 'line_notes_ids': [(6,0,line_ids)]})
        
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
        'line_notes_ids': fields.many2many('wizard.choose.supplier.line', 'choose_supplier_line', 'init_id', 'line_id',
                                     string='Lines'),
        'compare_id': fields.many2one('wizard.compare.rfq.line', string='Wizard'),
    }
    
    def return_view(self, cr, uid, ids, context=None):
        '''
        Return to the main wizard
        '''
        if context is None:
            context = {}
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
    
    def _get_func_total(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the total of line in functional currency
        '''
        res = {}
        
        for line in self.browse(cr, uid, ids, context=context):
            func_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
            if field_name == 'func_currency_id':
                res[line.id] = func_currency
            elif field_name == 'func_price_total':
                res[line.id] = self.pool.get('res.currency').compute(cr, uid, line.currency_id.id, func_currency, line.price_total, round=True, context=context)
                
        return res
    
    _columns = {
        'compare_id': fields.many2one('wizard.compare.rfq', string='Compare'),
        'compare_line_id': fields.many2one('wizard.compare.rfq.line', string='Compare Line'),
        'po_line_id': fields.many2one('purchase.order.line', string='PO Line'),
        'supplier_id': fields.many2one('res.partner', string='Supplier'),
        'price_unit': fields.float(digits=(16,2), string='Unit Price'),
        'qty': fields.float(digits=(16,2), string='Qty'),
        'price_total': fields.float(digits=(16,2), string='Total Price'),
        'currency_id': fields.many2one('res.currency', string='Currency'),
        'func_price_total': fields.function(_get_func_total, method=True, string='Func. Total Price', type='float'),
        'func_currency_id': fields.function(_get_func_total, method=True, string='Func. Currency', type='many2one', relation='res.currency'),
        'notes': fields.text(string='Notes'),
    }
    
    def write(self, cr, uid, ids, data, context=None):
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
    
    def choose_supplier(self, cr, uid, ids, context=None):
        '''
        Define the supplier for the line
        '''
        if context is None:
            context = {}
        compare_obj = self.pool.get('wizard.compare.rfq')
        compare_line_obj = self.pool.get('wizard.compare.rfq.line')
        
        if isinstance(ids, (int, long)):
                      ids = [ids]
        
        line_id = self.browse(cr, uid, ids[0])
        compare_line_obj.write(cr, uid, [line_id.compare_line_id.id], {'supplier_id': line_id.supplier_id.id, 'po_line_id': line_id.po_line_id.id})
        
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
