# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2011 MSF, TeMPO Consulting
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

from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta, relativedelta
from osv import osv, fields
from osv.orm import browse_record, browse_null
from tools.translate import _

import decimal_precision as dp
import netsvc
import pooler
import time


class tender(osv.osv):
    '''
    tender class
    '''
    _name = 'tender'
    _description = 'Tender'
    
    _columns = {'name': fields.char('Tender Reference', size=64, required=True, select=True,),
                'sale_order_id': fields.many2one('sale.order', string="Sale Order"), # function ?
                'state': fields.selection([('draft', 'Draft'),('comparison', 'Comparison'), ('done', 'Done'),], string="State", readonly=True),
                'supplier_ids': fields.many2many('res.partner', 'tender_supplier_rel', 'tender_id', 'supplier_id', string="Suppliers",),
                }
    
    _defaults = {'state': 'draft',}
    
    def wkf_generate_rfq(self, cr, uid, ids, context=None):
        '''
        wogenerate the 
        '''
        self.write(cr, uid, ids, {'state':'comparison'}, context=context)
        return True
    
    def wkf_action_done(self, cr, uid, ids, context=None):
        '''
        wogenerate the 
        '''
        self.write(cr, uid, ids, {'state':'done'}, context=context)
        return True
    
    def compare_rfqs(self, cr, uid, ids, context=None):
        '''
        compare rfqs button
        '''
        return True

tender()


class tender_line(osv.osv):
    '''
    tender lines
    '''
    _name = 'tender.line'
    _description= 'Tender Line'
    
    def _get_total_price(self, cr, uid, ids, field_name, arg, context=None):
        '''
        return the total price
        '''
        result = {}
        for line in self.browse(cr, uid, ids, context=context):
            if line.price_unit and line.qty:
                result[line.id] = line.price_unit * line.qty
            else:
                result[line.id] = 0.0
                
        return result
    
    _columns = {'name': fields.char(string="Name", size=1024,),
                'product_id': fields.many2one('product.product', string="Product", readonly=True),
                'qty': fields.float(string="Qty", readonly=True),
                'supplier_id': fields.many2one('res.partner', string="Supplier", domain=[('supplier', '=', True)], readonly=True),
                'price_unit': fields.float(string="Price Unit", readonly=True),
                'total_price': fields.function(_get_total_price, method=True, type='float', string="Total Price", readonly=True),
                'purchase_order_id': fields.many2one('purchase.order', string="Related RfQ", readonly=True),
                'proc_id': fields.many2one('procurement.order', string="Related Procurement", readonly=True),
                'tender_id': fields.many2one('tender', string="Tender", readonly=True),
                # sale order line id ?
                }
    
tender_line()


class tender(osv.osv):
    '''
    tender class
    '''
    _inherit = 'tender'
    _columns = {'tender_line_ids': fields.one2many('tender.line', 'tender_id', string="Tender lines"),
                }

tender()


class procurement_order(osv.osv):
    '''
    
    '''
    _inherit = 'procurement.order'
    
    def _is_tender(self, cr, uid, ids, field_name, arg, context=None):
        '''
        tell if the corresponding sale order line is tender sourcing or not
        '''
        result = {}
        for id in ids:
            result[id] = False
            
        for proc in self.browse(cr, uid, ids, context=context):
            for line in proc.sale_order_line_ids:
                result[proc.id] = line.po_cft == 'cft'
                                
        return result
    
    _columns = {'is_tender': fields.function(_is_tender, method=True, type='boolean', string='Is Tender', readonly=True,),
                'sale_order_line_ids': fields.one2many('sale.order.line', 'procurement_id', string="Sale Order Lines"),
                'is_tender_done': fields.boolean(string="Tender Done"),
                'state': fields.selection([
                                           ('draft','Draft'),
                                           ('confirmed','Confirmed'),
                                           ('exception','Exception'),
                                           ('running','Running'),
                                           ('cancel','Cancel'),
                                           ('ready','Ready'),
                                           ('done','Done'),
                                           ('tender', 'Tender'),
                                           ('waiting','Waiting'),], 'State', required=True,
                                          help='When a procurement is created the state is set to \'Draft\'.\n If the procurement is confirmed, the state is set to \'Confirmed\'.\
                                                \nAfter confirming the state is set to \'Running\'.\n If any exception arises in the order then the state is set to \'Exception\'.\n Once the exception is removed the state becomes \'Ready\'.\n It is in \'Waiting\'. state when the procurement is waiting for another one to finish.'),
                'price_unit': fields.float('Unit Price from Tender', digits_compute= dp.get_precision('Purchase Price')),
        }
    _defaults = {'is_tender_done': False,}
    
    def wkf_action_tender_create(self, cr, uid, ids, context=None):
        '''
        creation of tender from procurement workflow
        '''
        tender_obj = self.pool.get('tender')
        sale_order_id = False
        # find the corresponding sale order id for tender
        for proc in self.browse(cr, uid, ids, context=context):
            for sol in proc.sale_order_line_ids:
                sale_order_id = sol.order_id.id
        # find the tender
        tender_id = False
        tender_ids = tender_obj.search(cr, uid, [('sale_order_id', '=', sale_order_id),('state', '=', 'draft'),], context=context)
        if tender_ids:
            tender_id = tender_ids[0]
        # create if not found
        if not tender_id:
            tender_id = tender_obj.create(cr, uid, {'name': 'test_tender',
                                                    'sale_order_id': sale_order_id,}, context=context)
        # add a line to the tender
        
        # log message concerning tender creation
        tender_obj.log(cr, uid, tender_id, 'The sale order line is "Call For Tender". A tender has been created and must be completed before purchase order creation.')
        # state of procurement is Tender
        self.write(cr, uid, ids, {'state': 'tender'}, context=context)
        
        return tender_id
    
    def wkf_action_tender_done(self, cr, uid, ids, context=None):
        '''
        set is_tender_done value
        '''
        self.write(cr, uid, ids, {'is_tender_done': True, 'state': 'exception',}, context=context)
        return True
    
    def action_po_assign(self, cr, uid, ids, context=None):
        '''
        add message at po creation during on_order workflow
        '''
        po_obj = self.pool.get('purchase.order')
        result = super(procurement_order, self).action_po_assign(cr, uid, ids, context=context)
        # The quotation 'SO001' has been converted to a sales order.
        if result:
            po_obj.log(cr, uid, result, "The Purchase Order '%s' has been created following 'on order' sale order line."%po_obj.browse(cr, uid, result, context=context).name)
            if self.browse(cr, uid, ids[0], context=context).price_unit:
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'purchase.order', result, 'purchase_confirm', cr)
        return result
    
procurement_order()
