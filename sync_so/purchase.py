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
pp = pprint.PrettyPrinter(indent=4)

class purchase_order_sync(osv.osv):
    
    _inherit = "purchase.order"
    
    _columns = {
        'sended_by_supplier': fields.boolean('Sended by supplier', readonly=True),
    }
    
        
    def create_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        print "call purchase order", source
        partner_id = self.get_partner_id(cr, uid, source, context)
        address_id = self.get_partner_address_id(cr, uid, partner_id, context)
        lines = self.get_lines(cr, uid, so_info, context)
        default = self.default_get(cr, uid, ['name'], context=context)
        data = {                        'partner_ref' : source + "." + so_info.name,
                                        'partner_id' : partner_id,
                                        'partner_address_id' :  address_id,
                                        'pricelist_id' : self.get_price_list_id(cr, uid, partner_id, context),
                                        'location_id' : self.get_location(cr, uid, partner_id, context),
                                        'order_line' : lines}
        default.update(data)
        res_id = self.create(cr, uid, default , context=context)
        return res_id
        
    def validated_fo_to_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        print "The FO got validated, some info will be syncing to the original PO", source
        
        so_po_common = self.pool.get('so.po.common')
        partner_id = so_po_common.get_partner_id(cr, uid, source, context)
        address_id = so_po_common.get_partner_address_id(cr, uid, partner_id, context)
        lines = so_po_common.get_lines(cr, uid, so_info, context)
        
        #default = self.default_get(cr, uid, ['name'], context=context)
        
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
                                        'details' : so_info.details,
                                        
                                        'order_line' : lines}

                                        #'analytic_distribution_id' : self.ppol.dsdasas.copy(analytic_distrib.id),
        rec_id = so_po_common.get_record_id(cr, uid, context, so_info.analytic_distribution_id)
        if rec_id:
            data['analytic_distribution_id'] = rec_id 
        
        # Get the Id of the original PO to update these info back 
        po_ref = so_info.client_order_ref
        if not po_ref:
            return False
        po_split = po_ref.split('.')
        if len(po_split) != 2:
            return False

        po_name = po_split[1]
        ids = self.search(cr, uid, [('name', '=', po_name)], context=context)
        if not ids:
            return False
        
        default = {}
        default.update(data)
        
        res_id = self.write(cr, uid, ids, default , context=context)
        return res_id
        
    def confirm_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        name = so_info.client_order_ref.split('.')[1]
        ids = self.search(cr, uid, [('name', '=', name)])
        wf_service = netsvc.LocalService("workflow")
        return wf_service.trg_validate(uid, 'purchase.order', ids[0], 'purchase_confirm', cr)
    
    
    def picking_send(self, cr, uid, source, picking_info, context=None):
        if not context:
            context = {}
        name = picking_info.sale_id.client_order_ref.split('.')[1]
        ids = self.search(cr, uid, [('name', '=', name)])
        self.write(cr, uid, ids, {'sended_by_supplier' : True}, context=context)
        return True

purchase_order_sync()