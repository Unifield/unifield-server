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
from osv import orm
from tools.translate import _
from datetime import datetime
import tools
import time
import pprint
import netsvc
import so_po_common
pp = pprint.PrettyPrinter(indent=4)

class purchase_order_line(osv.osv):
    
    _inherit = "purchase.order.line"
    
    _columns = {
        'sync_pol_db_id': fields.integer(string='PO line DB Id', required=False, readonly=True),
        'sync_sol_db_id': fields.integer(string='SO line DB Id', required=False, readonly=True),
    }
    
    def create(self, cr, uid, vals, context=None):
        '''
        update the name attribute if a product is selected
        '''
        po_line_ids = super(purchase_order_line, self).create(cr, uid, vals, context=context)

        sync_pol_db_id = po_line_ids
        if 'sync_pol_db_id' in vals:
            sync_pol_db_id = vals['sync_pol_db_id']
        
        super(purchase_order_line, self).write(cr, uid, po_line_ids, {'sync_pol_db_id': sync_pol_db_id,} , context=context)
        return po_line_ids

purchase_order_line()

class purchase_order_sync(osv.osv):
    
    _inherit = "purchase.order"
    
    _columns = {
        'sended_by_supplier': fields.boolean('Sended by supplier', readonly=True),
        'split_po': fields.boolean('Created by split PO', readonly=True),
    }
        
    def create_split_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        print "call purchase order", source
        so_po_common = self.pool.get('so.po.common')
        partner_id = so_po_common.get_partner_id(cr, uid, source, context)
        address_id = so_po_common.get_partner_address_id(cr, uid, partner_id, context)
        
        lines = so_po_common.get_lines(cr, uid, so_info, False, context)
        
        default = self.default_get(cr, uid, ['name'], context=context)
        
        data = {                        'partner_ref' : source + "." + so_info.name,
                                        'partner_id' : partner_id,
                                        'partner_address_id' :  address_id,
                                        'note' : so_info.notes,
                                        'details' : so_info.details,
                                        'location_id' : so_po_common.get_location(cr, uid, partner_id, context),
                                        'pricelist_id' : so_po_common.get_price_list_id(cr, uid, partner_id, context),
                                        
                                        'delivery_confirmed_date' : so_info.delivery_confirmed_date,
                                        'est_transport_lead_time' : so_info.est_transport_lead_time,
                                        'transport_type' : so_info.transport_type,
                                        'ready_to_ship_date' : so_info.ready_to_ship_date,
                                        'split_po' : True,
                                        
                                        'order_line' : lines}
        
        default.update(data)
        
        wf_service = netsvc.LocalService("workflow")
        if so_info.state == 'sourced':
            data['state'] = 'sourced'
        
        res_id = self.create(cr, uid, default , context=context)
        
        # after created this splitted PO, pass it to the confirmed, as the split SO has been done so too.
        if so_info.state == 'confirmed':
            wf_service.trg_validate(uid, 'purchase.order', res_id, 'purchase_confirm', cr)
        else:
            self.write(cr, uid, res_id, {'state': 'sourced'} , context=context)
        
        # Set the original PO to "split" state -- cannot do anything with this original PO
        po_ids = so_po_common.get_original_po_id(cr, uid, so_info.client_order_ref, context)
        if not po_ids:
            raise Exception, "The original PO does not exist! " + so_info.client_order_ref
        
        res_id = self.write(cr, uid, po_ids[0], {'state' : 'split'} , context=context)
        return res_id

    def update_split_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        print "Update the split PO when the sourced FO got confirmed", source
        
        name = source + '.' + so_info.name
        po_ids = self.search(cr, uid, [('partner_ref', '=', name), ('state', '!=', 'cancelled')])
        if not po_ids:
            raise Exception, "Original split PO not found " + name
        
        if not so_info.delivery_confirmed_date:
            raise Exception, "Delivery Confirmed Date missing! " + name
 
        values = {}
        values['delivery_confirmed_date'] = so_info.delivery_confirmed_date
        
        res_id = self.write(cr, uid, po_ids, values , context=context)
        if not res_id:
            raise Exception, "Delivery Confirmed Date missing! " + name
        
        wf_service = netsvc.LocalService("workflow")
        if so_info.state == 'validated':
            ret = wf_service.trg_validate(uid, 'purchase.order', po_ids[0], 'purchase_confirm', cr)
        else:
            ret = wf_service.trg_validate(uid, 'purchase.order', po_ids[0], 'purchase_confirm', cr)
            ret = wf_service.trg_validate(uid, 'purchase.order', po_ids[0], 'purchase_approve', cr)
        return ret
        
        
    def po_update_fo(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        print "PO updates FO on the state", source

        po_ids = so_po_common.get_original_po_id(cr, uid, so_info.client_order_ref, context)
        if not po_ids:
            raise Exception, "The original PO does not exist! " + so_info.client_order_ref
        
        wf_service = netsvc.LocalService("workflow")
        return wf_service.trg_validate(uid, 'purchase.order', po_ids[0], 'purchase_confirm', cr)
        
    def validated_fo_to_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        print "The FO got validated, some info will be syncing to the original PO", source
        
        so_po_common = self.pool.get('so.po.common')
        partner_id = so_po_common.get_partner_id(cr, uid, source, context)
        address_id = so_po_common.get_partner_address_id(cr, uid, partner_id, context)

        # get the PO id        
        po_ids = so_po_common.get_original_po_id(cr, uid, so_info.client_order_ref, context)
        if not po_ids:
            raise Exception, "The original PO does not exist! " + so_info.client_order_ref
        
        lines = so_po_common.get_lines(cr, uid, so_info, True, context)
        
        data = {                        #'partner_ref' : source + "." + so_info.name,
                                        'partner_id' : partner_id,
                                        'partner_address_id' :  address_id,
                                        'pricelist_id' : so_po_common.get_price_list_id(cr, uid, partner_id, context),
                                        'location_id' : so_po_common.get_location(cr, uid, partner_id, context),
                                        'note' : so_info.notes,
                                        'details' : so_info.details,
                                        'delivery_confirmed_date' : so_info.delivery_confirmed_date,
                                        'est_transport_lead_time' : so_info.est_transport_lead_time,
                                        'transport_type' : so_info.transport_type,
                                        'ready_to_ship_date' : so_info.ready_to_ship_date,
                                        'order_line' : lines}

        rec_id = so_po_common.get_record_id(cr, uid, context, so_info.analytic_distribution_id)
        if rec_id:
            data['analytic_distribution_id'] = rec_id 
        
        default = {}
        default.update(data)
        
        res_id = self.write(cr, uid, po_ids, default , context=context)
        return res_id
        
    def confirm_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        name = so_info.client_order_ref.split('.')[1]
        po_ids = self.search(cr, uid, [('name', '=', name)])
        values = {}
        values['delivery_confirmed_date'] = so_info.delivery_confirmed_date
        
        res_id = self.write(cr, uid, po_ids, values , context=context)
        if not res_id:
            raise Exception, "Delivery Confirmed Date missing! " + name
        
        wf_service = netsvc.LocalService("workflow")
        return wf_service.trg_validate(uid, 'purchase.order', po_ids[0], 'purchase_approve', cr)
    
    def picking_send(self, cr, uid, source, picking_info, context=None):
        if not context:
            context = {}
        name = picking_info.sale_id.client_order_ref.split('.')[1]
        ids = self.search(cr, uid, [('name', '=', name)])
        self.write(cr, uid, ids, {'sended_by_supplier' : True}, context=context)
        return True

purchase_order_sync()