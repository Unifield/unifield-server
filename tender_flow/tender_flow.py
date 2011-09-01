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
    
    _columns = {'name': fields.char('Tender Reference', size=64, required=True, select=True, readonly=True),
                'sale_order_id': fields.many2one('sale.order', string="Sale Order", readonly=True),
                'state': fields.selection([('draft', 'Draft'),('comparison', 'Comparison'), ('done', 'Done'),], string="State", readonly=True),
                'supplier_ids': fields.many2many('res.partner', 'tender_supplier_rel', 'tender_id', 'supplier_id', string="Suppliers",
                                                 states={'draft':[('readonly',False)]}, readonly=True),
                'location_id': fields.many2one('stock.location', 'Location', required=True, states={'draft':[('readonly',False)]}, readonly=True, domain=[('usage', '=', 'internal')]),
                'company_id': fields.many2one('res.company','Company',required=True, states={'draft':[('readonly',False)]}, readonly=True),
                'rfq_ids': fields.one2many('purchase.order', 'tender_id', string="RfQs", readonly=True),
                }
    
    _defaults = {'state': 'draft',
                 'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'tender'),
                 'company_id': lambda obj, cr, uid, context: obj.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,}
    
    def wkf_generate_rfq(self, cr, uid, ids, context=None):
        '''
        generate the rfqs for each specified supplier
        '''
        if context is None:
            context = {}
        po_obj = self.pool.get('purchase.order')
        pol_obj = self.pool.get('purchase.order.line')
        partner_obj = self.pool.get('res.partner')
        pricelist_obj = self.pool.get('product.pricelist')
        # no suppliers -> raise error
        for tender in self.browse(cr, uid, ids, context=context):
            if not tender.supplier_ids:
                raise osv.except_osv(_('Warning !'), _('You must select at least one supplier!'))
            for supplier in tender.supplier_ids:
                # create a purchase order for each supplier
                address_id = partner_obj.address_get(cr, uid, [supplier.id], ['delivery'])['delivery']
                if not address_id:
                    raise osv.except_osv(_('Warning !'), _('The supplier "%s" has no address defined!'%supplier.name))
                pricelist_id = supplier.property_product_pricelist_purchase.id
                values = {'origin': tender.name,
                          'partner_id': supplier.id,
                          'partner_address_id': address_id,
                          'location_id': tender.location_id.id,
                          'pricelist_id': pricelist_id,
                          'company_id': tender.company_id.id,
                          'fiscal_position': supplier.property_account_position and supplier.property_account_position.id or False,
                          'tender_id': tender.id,
                          }
                # create the rfq - dic is udpated for default partner_address_id at purchase.order level
                po_id = po_obj.create(cr, uid, values, context=dict(context, partner_id=supplier.id))
                
                for line in tender.tender_line_ids:
                    # create an order line for each tender line
                    price = pricelist_obj.price_get(cr, uid, [pricelist_id], line.product_id.id, line.qty, supplier.id, {'uom': line.product_uom.id})[pricelist_id]
                    newdate = datetime.strptime(line.date_planned, '%Y-%m-%d %H:%M:%S')
                    newdate = (newdate - relativedelta(days=tender.company_id.po_lead)) - relativedelta(days=int(supplier.default_delay))
                    values = {
                              'name': line.product_id.partner_ref,
                              'product_qty': line.qty,
                              'product_id': line.product_id.id,
                              'product_uom': line.product_uom.id,
                              'price_unit': price,
                              'date_planned': newdate.strftime('%Y-%m-%d %H:%M:%S'),
                              'notes': line.product_id.description_purchase,
                              'order_id': po_id,
                              }
                    # create purchase order line
                    pol_id = pol_obj.create(cr, uid, values, context=context)
                
                po_obj.log(cr, uid, po_id, "Request for Quotation '%s' has been created."%po_obj.browse(cr, uid, po_id, context=context).name)
            
        self.write(cr, uid, ids, {'state':'comparison'}, context=context)
        return True
    
    def wkf_action_done(self, cr, uid, ids, context=None):
        '''
        tender is done
        '''
        # done all related rfqs
        wf_service = netsvc.LocalService("workflow")
        for tender in self.browse(cr, uid, ids, context=context):
            rfq_list = []
            for rfq in tender.rfq_ids:
                if rfq.state not in ('rfq_done', 'cancel',):
                    rfq_list.append(rfq.id)
                
            # if some rfq have wrong state, we display a message
            if rfq_list:
                raise osv.except_osv(_('Warning !'), _("Generated RfQs must be Done or Canceled."))
            
        self.write(cr, uid, ids, {'state':'done'}, context=context)
        return True
    
    def compare_rfqs(self, cr, uid, ids, context=None):
        '''
        compare rfqs button
        '''
        if len(ids) > 1:
            raise osv.except_osv(_('Warning !'), _('Cannot compare rfqs of more than one tender at a time!'))
        po_obj = self.pool.get('purchase.order')
        wiz_obj = self.pool.get('wizard.compare.rfq')
        for tender in self.browse(cr, uid, ids, context=context):
            # all rfqs must have been treated
            rfq_ids = po_obj.search(cr, uid, [('tender_id', '=', tender.id), ('state', '=', 'draft'),], context=context)
            if rfq_ids:
                raise osv.except_osv(_('Warning !'), _("Generated RfQs must be Done or Canceled."))
            # rfq corresponding to this tender with done state (has been updated and not canceled)
            rfq_ids = po_obj.search(cr, uid, [('tender_id', '=', tender.id), ('state', '=', 'rfq_done'),], context=context)
            # the list of rfq which will be compared
            c = dict(context, active_ids=rfq_ids, tender_id=tender.id)
            # open the wizard
            action = wiz_obj.start_compare_rfq(cr, uid, ids, context=c)
        return action

tender()


class tender_line(osv.osv):
    '''
    tender lines
    '''
    _name = 'tender.line'
    _description= 'Tender Line'
    
    def on_product_change(self, cr, uid, id, product_id, context=None):
        '''
        product is changed, we update the UoM
        '''
        prod_obj = self.pool.get('product.product')
        result = {'value': {}}
        if product_id:
            result['value']['product_uom'] = prod_obj.browse(cr, uid, product_id, context=context).uom_po_id.id
            
        return result
    
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
    
    def name_get(self, cr, user, ids, context=None):
        result = self.browse(cr, user, ids, context=context)
        res = []
        for rs in result:
            code = rs.product_id and rs.product_id.name or ''
            res += [(rs.id, code)]
        return res
    
    _columns = {'product_id': fields.many2one('product.product', string="Product", required=True),
                'qty': fields.float(string="Qty", required=True),
                'supplier_id': fields.related('purchase_order_line_id', 'order_id', 'partner_id', type='many2one', relation='res.partner', string="Supplier", readonly=True),
                'price_unit': fields.related('purchase_order_line_id', 'price_unit', type="float", string="Price unit", readonly=True),
                'total_price': fields.function(_get_total_price, method=True, type='float', string="Total Price"),
                'tender_id': fields.many2one('tender', string="Tender", required=True),
                'purchase_order_id': fields.related('purchase_order_line_id', 'order_id', type='many2one', relation='purchase.order', string="Related RfQ", readonly=True,),
                'purchase_order_line_id': fields.many2one('purchase.order.line', string="Related RfQ line", readonly=True),
                'purchase_order_line_number': fields.related('purchase_order_line_id', 'line_number', type="integer", string="Related Line Number", readonly=True,),
                'sale_order_line_id': fields.many2one('sale.order.line', string="Sale Order Line"),
                'product_uom': fields.many2one('product.uom', 'Product UOM', required=True),
                'date_planned': fields.datetime('Scheduled date', required=True),
                }
    
tender_line()


class tender(osv.osv):
    '''
    tender class
    '''
    _inherit = 'tender'
    _columns = {'tender_line_ids': fields.one2many('tender.line', 'tender_id', string="Tender lines", states={'draft':[('readonly',False)]}, readonly=True),
                }
    
    def copy(self, cr, uid, id, default=None, context=None):
        '''
        reset the name to get new sequence number
        
        the copy method is here because upwards it goes in infinite loop
        '''
        if default is None:
            default = {}
        
        default.update(name=self.pool.get('ir.sequence').get(cr, uid, 'tender'), rfq_ids=[])
            
        result = super(tender, self).copy(cr, uid, id, default, context)
        return result

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
        tender_line_obj = self.pool.get('tender.line')
        # find the corresponding sale order id for tender
        for proc in self.browse(cr, uid, ids, context=context):
            sale_order_id = False
            sale_order_line_id = False
            for sol in proc.sale_order_line_ids:
                sale_order_id = sol.order_id.id
                sale_order_line_id = sol.id
            # find the tender
            tender_id = False
            tender_ids = tender_obj.search(cr, uid, [('sale_order_id', '=', sale_order_id),('state', '=', 'draft'),], context=context)
            if tender_ids:
                tender_id = tender_ids[0]
            # create if not found
            if not tender_id:
                tender_id = tender_obj.create(cr, uid, {'sale_order_id': sale_order_id,}, context=context)
            # add a line to the tender
            tender_line_obj.create(cr, uid, {'product_id': proc.product_id.id,
                                             'qty': proc.product_qty,
                                             'tender_id': tender_id,
                                             'sale_order_line_id': sale_order_line_id,
                                             'location_id': proc.location_id.id,
                                             'product_uom': proc.product_uom.id,
                                             'date_planned': proc.date_planned,}, context=context)
            # log message concerning tender creation
            tender_obj.log(cr, uid, tender_id, "The tender '%s' has been created and must be completed before purchase order creation."%tender_obj.browse(cr, uid, tender_id, context=context).name)
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


class purchase_order(osv.osv):
    '''
    add link to tender
    '''
    _inherit = 'purchase.order'
    
    STATE_SELECTION = [
                       ('draft', 'Request for Quotation'),
                       ('wait', 'Waiting'),
                       ('confirmed', 'Waiting Approval'),
                       ('approved', 'Approved'),
                       ('except_picking', 'Shipping Exception'),
                       ('except_invoice', 'Invoice Exception'),
                       ('done', 'Done'),
                       ('cancel', 'Cancelled'),
                       ('rfq_done', 'RfQ Done'),
    ]
    
    _columns = {'tender_id': fields.many2one('tender', string="Tender", readonly=True),
                'state': fields.selection(STATE_SELECTION, 'State', readonly=True, help="The state of the purchase order or the quotation request. A quotation is a purchase order in a 'Draft' state. Then the order has to be confirmed by the user, the state switch to 'Confirmed'. Then the supplier must confirm the order to change the state to 'Approved'. When the purchase order is paid and received, the state becomes 'Done'. If a cancel action occurs in the invoice or in the reception of goods, the state becomes in exception.", select=True),
                'valid_till': fields.date(string='Valid Till', states={'draft':[('readonly',False)]}, readonly=True,),
                }
    
purchase_order()


class sale_order_line(osv.osv):
    '''
    add link one2many to tender.line
    '''
    _inherit = 'sale.order.line'
    
    _columns = {'tender_line_ids': fields.one2many('tender.line', 'sale_order_line_id', string="Tender Lines", readonly=True),}
    
sale_order_line()

