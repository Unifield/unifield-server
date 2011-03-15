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
        
        context['compare_id'] = self.browse(cr, uid, ids[0]).compare_id.id
        context['compare_line_id'] = ids[0]
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.choose.supplier',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
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
        'compare_id': fields.many2many('wizard.compare.rfq.line', 'compare_line_rel', 'choose_id', 'compare_id',
                                       string='Wizard'),
    }
    
    def default_get(self, cr, uid, fields, context={}):
        '''
        Initialize data
        '''
        if not context.get('compare_line_id', False):
            raise osv.except_osv(_('Error'), _('Data not found !'))
        
        compare_line_obj = self.pool.get('wizard.compare.rfq.line')
        choose_line_obj = self.pool.get('wizard.choose.supplier.line')

        res = {}
        
        compare_id = compare_line_obj.browse(cr, uid, context.get('compare_line_id'), context=context)
        
        res['product_id'] = compare_id.product_id.id
        res['compare_line_id'] = compare_id.id
        res['compare_id'] = compare_id.compare_id.id
        res['supplier_id'] = compare_id.supplier_id.id
        res['line_ids'] = []
        
        for l in compare_id.po_line_ids:
            res['line_ids'].append(choose_line_obj.create(cr, uid, {'supplier_id': l.order_id.partner_id.id,
                                                                    'po_line_id': l.id,
                                                                    'price_unit': l.price_unit,
                                                                    'qty': l.product_qty,
                                                                    'compare_line_id': compare_id.id,
                                                                    'compare_id': compare_id.compare_id.id,
                                                                    'price_total': l.product_qty*l.price_unit}))
        
        return res
    
wizard_choose_supplier()


class wizard_choose_supplier_line(osv.osv_memory):
    _name = 'wizard.choose.supplier.line'
    _description = 'Line Choose supplier wizard'
    
    _order = 'supplier_id'
    
    _columns = {
        'compare_id': fields.many2one('wizard.compare.rfq', string='Compare'),
        'compare_line_id': fields.many2one('wizard.compare.rfq.line', string='Compare Line'),
        'po_line_id': fields.many2one('purchase.order.line', string='PO Line'),
        'supplier_id': fields.many2one('res.partner', string='Supplier'),
        'price_unit': fields.float(digits=(16,2), string='Unit Price'),
        'qty': fields.float(digits=(16,2), string='Qty'),
        'price_total': fields.float(digits=(16,2), string='Total Price'),
    }
    
    def choose_supplier(self, cr, uid, ids, context={}):
        '''
        Define the supplier for the line
        '''
        compare_obj = self.pool.get('wizard.compare.rfq')
        compare_line_obj = self.pool.get('wizard.compare.rfq.line')
        
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
