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
from order_types import ORDER_PRIORITY, ORDER_CATEGORY
from osv import osv, fields
from osv.orm import browse_record, browse_null
from tools.translate import _

import decimal_precision as dp
import netsvc
import pooler
import time

from purchase_override import PURCHASE_ORDER_STATE_SELECTION

class tender(osv.osv):
    '''
    tender class
    '''
    _name = 'tender'
    _description = 'Tender'

    def copy(self, cr, uid, id, default=None, context=None, done_list=[], local=False):
        if not default:
            default = {}
        default['internal_state'] = 'draft' # UF-733: Reset the internal_state
        return super(osv.osv, self).copy(cr, uid, id, default, context=context)
    
    def unlink(self, cr, uid, ids, context=None):
        '''
        cannot delete tender not draft
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.state != 'draft':
                raise osv.except_osv(_('Warning !'), _("Cannot delete Tenders not in 'draft' state."))
        return super(tender, self).unlink(cr, uid, ids, context=context)
    
    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        return function values
        '''
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {'rfq_name_list': '',
                              }
            
            rfq_names = []
            for rfq in obj.rfq_ids:
                rfq_names.append(rfq.name)
            # generate string
            rfq_names.sort()
            result[obj.id]['rfq_name_list'] = ','.join(rfq_names)
            
        return result
    
    _columns = {'name': fields.char('Tender Reference', size=64, required=True, select=True, readonly=True),
                'sale_order_id': fields.many2one('sale.order', string="Sale Order", readonly=True),
                'state': fields.selection([('draft', 'Draft'),('comparison', 'Comparison'), ('done', 'Closed'), ('cancel', 'Cancelled'),], string="State", readonly=True),
                'supplier_ids': fields.many2many('res.partner', 'tender_supplier_rel', 'tender_id', 'supplier_id', string="Suppliers", domain="[('id', '!=', company_id)]",
                                                 states={'draft':[('readonly',False)]}, readonly=True,
                                                 context={'search_default_supplier': 1,}),
                'location_id': fields.many2one('stock.location', 'Location', required=True, states={'draft':[('readonly',False)]}, readonly=True, domain=[('usage', '=', 'internal')]),
                'company_id': fields.many2one('res.company','Company',required=True, states={'draft':[('readonly',False)]}, readonly=True),
                'rfq_ids': fields.one2many('purchase.order', 'tender_id', string="RfQs", readonly=True),
                'priority': fields.selection(ORDER_PRIORITY, string='Tender Priority', states={'draft':[('readonly',False)],}, readonly=True,),
                'categ': fields.selection(ORDER_CATEGORY, string='Tender Category', required=True, states={'draft':[('readonly',False)],}, readonly=True),
                'creator': fields.many2one('res.users', string="Creator", readonly=True, required=True,),
                'warehouse_id': fields.many2one('stock.warehouse', string="Warehouse", required=True, states={'draft':[('readonly',False)],}, readonly=True),
                'creation_date': fields.date(string="Creation Date", readonly=True, states={'draft':[('readonly',False)]}),
                'details': fields.char(size=30, string="Details", states={'draft':[('readonly',False)],}, readonly=True),
                'requested_date': fields.date(string="Requested Date", required=True, states={'draft':[('readonly',False)],}, readonly=True),
                'notes': fields.text('Notes'),
                'internal_state': fields.selection([('draft', 'Draft'),('updated', 'Rfq Updated'), ], string="Internal State", readonly=True),
                'rfq_name_list': fields.function(_vals_get, method=True, string='RfQs Ref', type='char', readonly=True, store=False, multi='get_vals',),
                'product_id': fields.related('tender_line_ids', 'product_id', type='many2one', relation='product.product', string='Product')
                }
    
    _defaults = {'state': 'draft',
                 'internal_state': 'draft',
                 'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'tender'),
                 'company_id': lambda obj, cr, uid, context: obj.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
                 'creator': lambda obj, cr, uid, context: uid,
                 'creation_date': lambda *a: time.strftime('%Y-%m-%d'),
                 'requested_date': lambda *a: time.strftime('%Y-%m-%d'),
                 'priority': 'normal',
                 'warehouse_id': lambda obj, cr, uid, context: len(obj.pool.get('stock.warehouse').search(cr, uid, [])) and obj.pool.get('stock.warehouse').search(cr, uid, [])[0],
                 }
    
    _order = 'name desc'
    
    def onchange_warehouse(self, cr, uid, ids, warehouse_id, context=None):
        '''
        on_change function for the warehouse
        '''
        result = {'value':{},}
        if warehouse_id:
            input_loc_id = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context).lot_input_id.id
            result['value'].update(location_id=input_loc_id)
        
        return result
    
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
            # check some supplier have been selected
            if not tender.supplier_ids:
                raise osv.except_osv(_('Warning !'), _('You must select at least one supplier!'))
            # check some products have been selected
            tender_line_ids = self.pool.get('tender.line').search(cr, uid, [('tender_id', '=', tender.id)], context=context)
            if not tender_line_ids:
                raise osv.except_osv(_('Warning !'), _('You must select at least one product!'))
            for supplier in tender.supplier_ids:
                # create a purchase order for each supplier
                address_id = partner_obj.address_get(cr, uid, [supplier.id], ['delivery'])['delivery']
                if not address_id:
                    raise osv.except_osv(_('Warning !'), _('The supplier "%s" has no address defined!')%(supplier.name,))
                pricelist_id = supplier.property_product_pricelist_purchase.id
                values = {'name': self.pool.get('ir.sequence').get(cr, uid, 'rfq'),
                          'origin': tender.sale_order_id and tender.sale_order_id.name + '/' + tender.name or tender.name,
                          'rfq_ok': True,
                          'partner_id': supplier.id,
                          'partner_address_id': address_id,
                          'location_id': tender.location_id.id,
                          'pricelist_id': pricelist_id,
                          'company_id': tender.company_id.id,
                          'fiscal_position': supplier.property_account_position and supplier.property_account_position.id or False,
                          'tender_id': tender.id,
                          'warehouse_id': tender.warehouse_id.id,
                          'categ': tender.categ,
                          'priority': tender.priority,
                          'details': tender.details,
                          'delivery_requested_date': tender.requested_date,
                          }
                # create the rfq - dic is udpated for default partner_address_id at purchase.order level
                po_id = po_obj.create(cr, uid, values, context=dict(context, partner_id=supplier.id))
                
                for line in tender.tender_line_ids:
                    # create an order line for each tender line
                    price = pricelist_obj.price_get(cr, uid, [pricelist_id], line.product_id.id, line.qty, supplier.id, {'uom': line.product_uom.id})[pricelist_id]
                    newdate = datetime.strptime(line.date_planned, '%Y-%m-%d')
                    #newdate = (newdate - relativedelta(days=tender.company_id.po_lead)) - relativedelta(days=int(supplier.default_delay)) # requested by Magali uf-489
                    values = {'name': line.product_id.partner_ref,
                              'product_qty': line.qty,
                              'product_id': line.product_id.id,
                              'product_uom': line.product_uom.id,
                              'price_unit': 0.0, # was price variable - uf-607
                              'date_planned': newdate.strftime('%Y-%m-%d'),
                              'notes': line.product_id.description_purchase,
                              'order_id': po_id,
                              }
                    # create purchase order line
                    pol_id = pol_obj.create(cr, uid, values, context=context)
                    message = "Request for Quotation '%s' has been created."%po_obj.browse(cr, uid, po_id, context=context).name
                    # create the log message
                    self.pool.get('res.log').create(cr, uid,
                                                           {'name': message,
                                                            'res_model': po_obj._name,
                                                            'secondary': False,
                                                            'res_id': po_id,
                                                            'domain': [('rfq_ok', '=', True)],
                                                            }, context={'rfq_ok': True})
            
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
                if rfq.state not in ('rfq_updated', 'cancel',):
                    rfq_list.append(rfq.id)
                else:
                    wf_service.trg_validate(uid, 'purchase.order', rfq.id, 'rfq_done', cr)
                
            # if some rfq have wrong state, we display a message
            if rfq_list:
                raise osv.except_osv(_('Warning !'), _("Generated RfQs must be Updated or Cancelled."))
            
            # integrity check, all lines must have purchase_order_line_id
            if not all([line.purchase_order_line_id.id for line in tender.tender_line_ids]):
                raise osv.except_osv(_('Error !'), _('All tender lines must have been compared!'))
        
        # update product supplierinfo and pricelist
        self.update_supplier_info(cr, uid, ids, context=context, integrity_test=False,)
        # change tender state
        self.write(cr, uid, ids, {'state':'done'}, context=context)
        return True
    
    def tender_integrity(self, cr, uid, tender, context=None):
        '''
        check the state of corresponding RfQs
        '''
        po_obj = self.pool.get('purchase.order')
        # no rfq in done state
        rfq_ids = po_obj.search(cr, uid, [('tender_id', '=', tender.id),
                                          ('state', 'in', ('done',)),], context=context)
        if rfq_ids:
            raise osv.except_osv(_('Error !'), _("Some RfQ are already Closed. Integrity failure."))
        # all rfqs must have been treated
        rfq_ids = po_obj.search(cr, uid, [('tender_id', '=', tender.id),
                                          ('state', 'in', ('draft', 'rfq_sent',)),], context=context)
        if rfq_ids:
            raise osv.except_osv(_('Warning !'), _("Generated RfQs must be Updated or Cancelled."))
        # at least one rfq must be updated and not canceled
        rfq_ids = po_obj.search(cr, uid, [('tender_id', '=', tender.id),
                                          ('state', 'in', ('rfq_updated',)),], context=context)
        if not rfq_ids:
            raise osv.except_osv(_('Warning !'), _("At least one RfQ must be in state Updated."))
        
        return rfq_ids
    
    def compare_rfqs(self, cr, uid, ids, context=None):
        '''
        compare rfqs button
        '''
        if len(ids) > 1:
            raise osv.except_osv(_('Warning !'), _('Cannot compare rfqs of more than one tender at a time!'))
        po_obj = self.pool.get('purchase.order')
        wiz_obj = self.pool.get('wizard.compare.rfq')
        for tender in self.browse(cr, uid, ids, context=context):
            # check if corresponding rfqs are in the good state
            rfq_ids = self.tender_integrity(cr, uid, tender, context=context)
            # gather the product_id -> supplier_id relationship to display it back in the compare wizard
            suppliers = {}
            for line in tender.tender_line_ids:
                if line.product_id and line.supplier_id:
                    suppliers.update({line.product_id.id:line.supplier_id.id,})
            # rfq corresponding to this tender with done state (has been updated and not canceled)
            # the list of rfq which will be compared
            c = dict(context, active_ids=rfq_ids, tender_id=tender.id, end_wizard=False, suppliers=suppliers,)
            # open the wizard
            action = wiz_obj.start_compare_rfq(cr, uid, ids, context=c)
        return action
    
    def update_supplier_info(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        update the supplier info of corresponding products
        '''
        info_obj = self.pool.get('product.supplierinfo')
        pricelist_info_obj = self.pool.get('pricelist.partnerinfo')
        # integrity check flag
        integrity_test = kwargs.get('integrity_test', False)
        for tender in self.browse(cr, uid, ids, context=context):
            # flag if at least one update
            updated = tender.tender_line_ids and False or True
            # check if corresponding rfqs are in the good state
            if integrity_test:
                self.tender_integrity(cr, uid, tender, context=context)
            for line in tender.tender_line_ids:
                # if a supplier has been selected
                if line.purchase_order_line_id:
                    # set the flag
                    updated = True
                    # get the product
                    product = line.product_id
                    # find the corresponding suppinfo with sequence -99
                    info_99_list = info_obj.search(cr, uid, [('product_id', '=', product.product_tmpl_id.id),
                                                        ('sequence', '=', -99),], context=context)
                    
                    if info_99_list:
                        # we drop it
                        info_obj.unlink(cr, uid, info_99_list, context=context)
                    
                    # create the new one
                    values = {'name': line.supplier_id.id,
                              'product_name': False,
                              'product_code': False,
                              'sequence' : -99,
                              #'product_uom': line.product_uom.id,
                              #'min_qty': 0.0,
                              #'qty': function
                              'product_id' : product.product_tmpl_id.id,
                              'delay' : int(line.supplier_id.default_delay),
                              #'pricelist_ids': created just after
                              #'company_id': default value
                              }
                    
                    new_info_id = info_obj.create(cr, uid, values, context=context)
                    # price lists creation - 'pricelist.partnerinfo
                    values = {'suppinfo_id': new_info_id,
                              'min_quantity': 1.00,
                              'price': line.price_unit,
                              'uom_id': line.product_uom.id,
                              'currency_id': line.purchase_order_line_id.currency_id.id,
                              'valid_till': line.purchase_order_id.valid_till,
                              'purchase_order_line_id': line.purchase_order_line_id.id,
                              'comment': 'RfQ original quantity for price : %s' % line.qty,
                              }
                    new_pricelist_id = pricelist_info_obj.create(cr, uid, values, context=context)
            
            # warn the user if no update has been performed
            if not updated:
                raise osv.except_osv(_('Warning !'), _('No information available for update!'))
                    
        return True
    
    def done(self, cr, uid, ids, context=None):
        '''
        method to perform checks before call to workflow
        '''
        po_obj = self.pool.get('purchase.order')
        wf_service = netsvc.LocalService("workflow")
        for tender in self.browse(cr, uid, ids, context=context):
            # check if corresponding rfqs are in the good state
            self.tender_integrity(cr, uid, tender, context=context)
            wf_service.trg_validate(uid, 'tender', tender.id, 'button_done', cr)
            # trigger all related rfqs
            rfq_ids = po_obj.search(cr, uid, [('tender_id', '=', tender.id),], context=context)
            for rfq_id in rfq_ids:
                wf_service.trg_validate(uid, 'purchase.order', rfq_id, 'rfq_done', cr)
            
        return True
    
    def create_po(self, cr, uid, ids, context=None):
        '''
        create a po from the updated RfQs
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        partner_obj = self.pool.get('res.partner')
        po_obj = self.pool.get('purchase.order')
        wf_service = netsvc.LocalService("workflow")
        
        for tender in self.browse(cr, uid, ids, context=context):
            # check if corresponding rfqs are in the good state
            self.tender_integrity(cr, uid, tender, context=context)
            # integrity check, all lines must have purchase_order_line_id
            if not all([line.purchase_order_line_id.id for line in tender.tender_line_ids]):
                raise osv.except_osv(_('Error !'), _('All tender lines must have been compared!'))
            data = {}
            for line in tender.tender_line_ids:
                data.setdefault(line.supplier_id.id, {}) \
                    .setdefault('order_line', []).append((0,0,{'name': line.product_id.partner_ref,
                                                               'product_qty': line.qty,
                                                               'product_id': line.product_id.id,
                                                               'product_uom': line.product_uom.id,
                                                               'change_price_manually': 'True',
                                                               'price_unit': line.price_unit,
                                                               'date_planned': line.date_planned,
                                                               'move_dest_id': False,
                                                               'notes': line.product_id.description_purchase,
                                                               }))
                    
                # fill data corresponding to po creation
                address_id = partner_obj.address_get(cr, uid, [line.supplier_id.id], ['delivery'])['delivery']
                po_values = {'origin': (tender.sale_order_id and tender.sale_order_id.name or "") + '/' + tender.name,
                             'partner_id': line.supplier_id.id,
                             'partner_address_id': address_id,
                             'location_id': tender.location_id.id,
                             'pricelist_id': line.supplier_id.property_product_pricelist_purchase.id,
                             'company_id': tender.company_id.id,
                             'fiscal_position': line.supplier_id.property_account_position and line.supplier_id.property_account_position.id or False,
                             'categ': tender.categ,
                             'priority': tender.priority,
                             'origin_tender_id': tender.id,
                             #'tender_id': tender.id, # not for now, because tender_id is the flag for a po to be considered as RfQ
                             'warehouse_id': tender.warehouse_id.id,
                             'details': tender.details,
                             'delivery_requested_date': tender.requested_date,
                             }
                data[line.supplier_id.id].update(po_values)
            
            # create the pos, one for each selected supplier
            for po_data in data.values():
                po_id = po_obj.create(cr, uid, po_data, context=context)
                po = po_obj.browse(cr, uid, po_id, context=context)
                po_obj.log(cr, uid, po_id, 'The Purchase order %s for supplier %s has been created.'%(po.name, po.partner_id.name))
                #UF-802: the PO created must be in draft state, and not validated!
                #wf_service.trg_validate(uid, 'purchase.order', po_id, 'purchase_confirm', cr)
                
            # when the po is generated, the tender is done - no more modification or comparison
            self.done(cr, uid, [tender.id], context=context)
        
        return po_id
    
    def wkf_action_cancel(self, cr, uid, ids, context=None):
        '''
        cancel all corresponding rfqs
        '''
        po_obj = self.pool.get('purchase.order')
        wf_service = netsvc.LocalService("workflow")
        # set state
        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        for tender in self.browse(cr, uid, ids, context=context):
            # trigger all related rfqs
            rfq_ids = po_obj.search(cr, uid, [('tender_id', '=', tender.id),], context=context)
            for rfq_id in rfq_ids:
                wf_service.trg_validate(uid, 'purchase.order', rfq_id, 'purchase_cancel', cr)
                
        return True

    def set_manually_done(self, cr, uid, ids, all_doc=True, context=None):
        '''
        Set the tender and all related documents to done state
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")

        for tender in self.browse(cr, uid, ids, context=context):
            line_updated = False
            if tender.state not in ('done', 'cancel'):
                for line in tender.tender_line_ids:
                    if line.purchase_order_line_id:
                        line_updated = True
                # Cancel or done all RfQ related to the tender
                for rfq in tender.rfq_ids:
                    if rfq.state not in ('done', 'cancel'):
                        if rfq.state == 'draft' or not line_updated:
                            wf_service.trg_validate(uid, 'purchase.order', rfq.id, 'purchase_cancel', cr)
                        else:
                            wf_service.trg_validate(uid, 'purchase.order', rfq.id, 'rfq_sent', cr)
                            if not rfq.valid_till:
                                self.pool.get('purchase.order').write(cr, uid, [rfq.id], {'valid_till': time.strftime('%Y-%m-%d')}, context=context)
                            wf_service.trg_validate(uid, 'purchase.order', rfq.id, 'rfq_updated', cr)

                if all_doc:
                    if tender.state == 'draft' or not tender.tender_line_ids or not line_updated:
                        # Call the cancel method of the tender
                        wf_service.trg_validate(uid, 'tender', tender.id, 'tender_cancel', cr)
                    else:
                        # Call the cancel method of the tender
                        wf_service.trg_validate(uid, 'tender', tender.id, 'button_done', cr)

        return True

tender()


class tender_line(osv.osv):
    '''
    tender lines
    '''
    _name = 'tender.line'
    _description= 'Tender Line'
    
    _SELECTION_TENDER_STATE = [('draft', 'Draft'),('comparison', 'Comparison'), ('done', 'Closed'),]
    
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
                'tender_id': fields.many2one('tender', string="Tender", required=True),
                'purchase_order_line_id': fields.many2one('purchase.order.line', string="Related RfQ line", readonly=True),
                'sale_order_line_id': fields.many2one('sale.order.line', string="Sale Order Line"),
                'product_uom': fields.many2one('product.uom', 'Product UOM', required=True),
                'date_planned': fields.related('tender_id', 'requested_date', type='date', string='Requested Date', store=False,),
                # functions
                'supplier_id': fields.related('purchase_order_line_id', 'order_id', 'partner_id', type='many2one', relation='res.partner', string="Supplier", readonly=True),
                'price_unit': fields.related('purchase_order_line_id', 'price_unit', type="float", string="Price unit", readonly=True),
                'total_price': fields.function(_get_total_price, method=True, type='float', string="Total Price"),
                'purchase_order_id': fields.related('purchase_order_line_id', 'order_id', type='many2one', relation='purchase.order', string="Related RfQ", readonly=True,),
                'purchase_order_line_number': fields.related('purchase_order_line_id', 'line_number', type="integer", string="Related Line Number", readonly=True,),
                'state': fields.related('tender_id', 'state', type="selection", selection=_SELECTION_TENDER_STATE, string="State",),
                }
    _defaults = {'qty': lambda *a: 1.0,
                 'state': lambda *a: 'draft',
                 }
    
tender_line()


class tender2(osv.osv):
    '''
    tender class
    '''
    _inherit = 'tender'
    _columns = {'tender_line_ids': fields.one2many('tender.line', 'tender_id', string="Tender lines", states={'draft':[('readonly',False)], 'comparison': [('readonly',False)]}, readonly=True),
                }
    
    def copy(self, cr, uid, id, default=None, context=None):
        '''
        reset the name to get new sequence number
        
        the copy method is here because upwards it goes in infinite loop
        '''
        line_obj = self.pool.get('tender.line')
        if default is None:
            default = {}
        
        default.update(name=self.pool.get('ir.sequence').get(cr, uid, 'tender'),
                       rfq_ids=[],
                       sale_order_line_id=False,)
            
        result = super(tender2, self).copy(cr, uid, id, default, context)
        
        return result
    
    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        reset the tender line
        '''
        result = super(tender, self).copy_data(cr, uid, id, default=default, context=context)
        # reset the tender line
        for line in result['tender_line_ids']:
            line[2].update(sale_order_line_id=False,
                           purchase_order_line_id=False,)
        return result

tender2()


class procurement_order(osv.osv):
    '''
    tender capabilities
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
                'tender_id': fields.many2one('tender', string='Tender', readonly=True),
                'is_tender_done': fields.boolean(string="Tender Closed"),
                'state': fields.selection([('draft','Draft'),
                                           ('confirmed','Confirmed'),
                                           ('exception','Exception'),
                                           ('running','Converted'),
                                           ('cancel','Cancelled'),
                                           ('ready','Ready'),
                                           ('done','Closed'),
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
            sale_order = False
            sale_order_line = False
            for sol in proc.sale_order_line_ids:
                sale_order = sol.order_id
                sale_order_line = sol
            # find the tender
            tender_id = False
            tender_ids = tender_obj.search(cr, uid, [('sale_order_id', '=', sale_order.id),('state', '=', 'draft'),], context=context)
            if tender_ids:
                tender_id = tender_ids[0]
            # create if not found
            if not tender_id:
                tender_id = tender_obj.create(cr, uid, {'sale_order_id': sale_order.id,
                                                        'location_id': proc.location_id.id,
                                                        'categ': sale_order.categ,
                                                        'priority': sale_order.priority,
                                                        'warehouse_id': sale_order.shop_id.warehouse_id.id,
                                                        'requested_date': proc.date_planned,
                                                        }, context=context)
            # add a line to the tender
            tender_line_obj.create(cr, uid, {'product_id': proc.product_id.id,
                                             'qty': proc.product_qty,
                                             'tender_id': tender_id,
                                             'sale_order_line_id': sale_order_line.id,
                                             'location_id': proc.location_id.id,
                                             'product_uom': proc.product_uom.id,
                                             #'date_planned': proc.date_planned, # function at line level
                                             }, context=context)
            
            self.write(cr, uid, ids, {'tender_id': tender_id}, context=context)
            
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
        - convert the created rfq by the tender to a po
        - add message at po creation during on_order workflow
        '''
        po_obj = self.pool.get('purchase.order')
        result = super(procurement_order, self).action_po_assign(cr, uid, ids, context=context)
        # The quotation 'SO001' has been converted to a sales order.
        if result:
            po_obj.log(cr, uid, result, "The Purchase Order '%s' has been created following 'on order' sourcing."%po_obj.browse(cr, uid, result, context=context).name)
            if self.browse(cr, uid, ids[0], context=context).is_tender:
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'purchase.order', result, 'purchase_confirm', cr)
        return result
    
    def create_po_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        if the procurement corresponds to a tender, the created po is confirmed but not validated
        '''
        po_obj = self.pool.get('purchase.order')
        procurement = kwargs['procurement']
        purchase_id = super(procurement_order, self).create_po_hook(cr, uid, ids, context=context, *args, **kwargs)
        if purchase_id:
            # if tender
            if procurement.is_tender:
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'purchase.order', purchase_id, 'purchase_confirm', cr)
        return purchase_id
    
    def po_values_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        data for the purchase order creation
        '''
        values = super(procurement_order, self).po_values_hook(cr, uid, ids, context=context, *args, **kwargs)
        procurement = kwargs['procurement']
        
        values['date_planned'] = procurement.date_planned 
        
        return values
    
procurement_order()


class purchase_order(osv.osv):
    '''
    add link to tender
    '''
    _inherit = 'purchase.order'
    
    def _check_valid_till(self, cr, uid, ids, context=None):
        """ Checks if valid till has been completed
        """
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.state == 'rfq_updated' and not obj.valid_till:
                return False
        return True
    _columns = {'tender_id': fields.many2one('tender', string="Tender", readonly=True),
                'origin_tender_id': fields.many2one('tender', string='Tender', readonly=True),
                'rfq_ok': fields.boolean(string='Is RfQ ?'),
                'state': fields.selection(PURCHASE_ORDER_STATE_SELECTION, 'State', readonly=True, help="The state of the purchase order or the quotation request. A quotation is a purchase order in a 'Draft' state. Then the order has to be confirmed by the user, the state switch to 'Confirmed'. Then the supplier must confirm the order to change the state to 'Approved'. When the purchase order is paid and received, the state becomes 'Closed'. If a cancel action occurs in the invoice or in the reception of goods, the state becomes in exception.", select=True),
                'valid_till': fields.date(string='Valid Till', states={'rfq_updated': [('required', True), ('readonly', True)], 'rfq_sent':[('required',False), ('readonly', False),]}, readonly=True,),
                # add readonly when state is Done
                }

    _defaults = {
                'rfq_ok': lambda self, cr, uid, c: c.get('rfq_ok', False),
                'name': lambda obj, cr, uid, c: obj.pool.get('ir.sequence').get(cr, uid, c.get('rfq_ok', False) and 'rfq' or 'purchase.order'),
                 }
    
    _constraints = [
        (_check_valid_till,
            'You must specify a Valid Till date.',
            ['valid_till']),]
    
    def unlink(self, cr, uid, ids, context=None):
        '''
        Display an error message if the PO has associated IN
        '''
        in_ids = self.pool.get('stock.picking').search(cr, uid, [('purchase_id', 'in', ids)], context=context)
        if in_ids:
            raise osv.except_osv(_('Error !'), _('Cannot delete a document if its associated ' \
            'document remains open. Please delete it (associated IN) first.'))
            
        # Copy a part of purchase_order standard unlink method to fix the bad state on error message
        purchase_orders = self.read(cr, uid, ids, ['state'], context=context)
        unlink_ids = []
        for s in purchase_orders:
            if s['state'] in ['draft','cancel']:
                unlink_ids.append(s['id'])
            else:
                raise osv.except_osv(_('Invalid action !'), _('Cannot delete Purchase Order(s) which are in %s State!')  % _(dict(PURCHASE_ORDER_STATE_SELECTION).get(s['state'])))
            
        return super(purchase_order, self).unlink(cr, uid, ids, context=context)
    
    def _hook_copy_name(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        HOOK from purchase>purchase.py for COPY function. Modification of default copy values
        define which name value will be used
        '''
        result = super(purchase_order, self)._hook_copy_name(cr, uid, ids, context=context, *args, **kwargs)
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.rfq_ok:
                result.update(name=self.pool.get('ir.sequence').get(cr, uid, 'rfq'))
        return result

    def rfq_sent(self, cr, uid, ids, context=None):
        for rfq in self.browse(cr, uid, ids, context=context):
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'purchase.order', rfq.id, 'rfq_sent', cr)

        datas = {'ids': ids}

        return {'type': 'ir.actions.report.xml',
                'report_name': 'purchase.quotation',
                'datas': datas}

    def check_rfq_updated(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")
        for rfq in self.browse(cr, uid, ids, context=context):
            if not rfq.valid_till:
                raise osv.except_osv(_('Error'), _('You must specify a Valid Till date.'))

            wf_service.trg_validate(uid, 'purchase.order', rfq.id, 'rfq_updated', cr)

        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_mode': 'form,tree,graph,calendar',
                'view_type': 'form',
                'target': 'crush',
                'context': {'rfq_ok': True, 'search_default_draft_rfq': 1,},
                'domain': [('rfq_ok', '=', True)],
                'res_id': rfq.id}
        
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        columns for the tree
        """
        if context is None:
            context = {}
        # the search view depends on the type we want to display
        if view_type == 'search':
            if context.get('rfq_ok', False):
                # rfq search view
                view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'tender_flow', 'view_rfq_filter')
                if view:
                    view_id = view[1]
        if view_type == 'tree':
            # the view depends on po type
            if context.get('rfq_ok', False):
                # rfq search view
                view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'tender_flow', 'view_rfq_tree')
                if view:
                    view_id = view[1]
                 
        # call super
        result = super(purchase_order, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            if context.get('rfq_ok', False):
                # the title of the screen depends on po type
                arch = result['arch']
                arch = arch.replace('<form string="Purchase Order">', '<form string="Requests for Quotation">')
                result['arch'] = arch
        
        return result

purchase_order()


class purchase_order_line(osv.osv):
    '''
    add a tender_id related field
    '''
    _inherit = 'purchase.order.line'
    _columns = {'tender_id': fields.related('order_id', 'tender_id', type='many2one', relation='tender', string='Tender',),
                'rfq_ok': fields.related('order_id', 'rfq_ok', type='boolean', string='RfQ ?'),
                }
    
purchase_order_line()


class sale_order_line(osv.osv):
    '''
    add link one2many to tender.line
    '''
    _inherit = 'sale.order.line'
    
    _columns = {'tender_line_ids': fields.one2many('tender.line', 'sale_order_line_id', string="Tender Lines", readonly=True),}
    
sale_order_line()


class pricelist_partnerinfo(osv.osv):
    '''
    add new information from specifications
    '''
    _inherit = 'pricelist.partnerinfo'
    _columns = {'currency_id': fields.many2one('res.currency', string='Currency', required=True),
                'valid_till': fields.date(string="Valid Till",),
                'comment': fields.char(size=128, string='Comment'),
                'purchase_order_id': fields.related('purchase_order_line_id', 'order_id', type='many2one', relation='purchase.order', string="Related RfQ", readonly=True,),
                'purchase_order_line_id': fields.many2one('purchase.order.line', string="RfQ Line Ref",),
                'purchase_order_line_number': fields.related('purchase_order_line_id', 'line_number', type="integer", string="Related Line Number", readonly=True,),
                }
pricelist_partnerinfo()

