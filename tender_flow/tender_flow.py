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
        print 'generate rfq workflow'
        self.write(cr, uid, ids, {'state':'comparison'}, context=context)
        return True
    
    def wkf_action_done(self, cr, uid, ids, context=None):
        '''
        wogenerate the 
        '''
        print 'action done workflow'
        self.write(cr, uid, ids, {'state':'done'}, context=context)
        return True
    
    def compare_rfqs(self, cr, uid, ids, context=None):
        '''
        compare rfqs button
        '''
        print 'compare rfqs button'
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
                'is_tender_done': fields.boolean(string="Tender Done"),}
    _defaults = {'is_tender_done': False,}
    
    def wkf_action_tender_create(self, cr, uid, ids, context=None):
        '''
        creation of tender from procurement workflow
        '''
        tender_obj = self.pool.get('tender')
        tender_id = tender_obj.create(cr, uid, {''}, context=context)
        
        return tender_id
    
    def wkf_action_tender_done(self, cr, uid, ids, context=None):
        '''
        set is_tender_done value
        '''
        self.write(cr, uid, ids, {'is_tender_done': True}, context=context)
        return True
    
procurement_order()
