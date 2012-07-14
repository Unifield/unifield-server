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
        
        so_dict = so_info.to_dict()
        so_po_common = self.pool.get('so.po.common')
        
        header_result = {}
        so_po_common.retrieve_po_header_data(cr, uid, source, header_result, so_dict, context)
        header_result['order_line'] = so_po_common.get_lines(cr, uid, so_info, False, context)

        wf_service = netsvc.LocalService("workflow")
        if so_info.state == 'sourced':
            header_result['state'] = 'sourced'

        default = {}
        default.update(header_result)
        
        res_id = self.create(cr, uid, default , context=context)
        
        # after created this splitted PO, pass it to the confirmed, as the split SO has been done so too.
        if so_info.state == 'confirmed':
            wf_service.trg_validate(uid, 'purchase.order', res_id, 'purchase_confirm', cr)
        else:
            self.write(cr, uid, res_id, {'state': 'sourced'} , context=context)
        
        # Set the original PO to "split" state -- cannot do anything with this original PO
        po_id = so_po_common.get_original_po_id(cr, uid, so_info.client_order_ref, context)
        res_id = self.write(cr, uid, po_id, {'state' : 'split'} , context=context)
        return res_id


    def check_update(self, cr, uid, source, so_dict):
        if not source:
            raise Exception, "The partner is missing!"

        name = so_dict.get('name')
        if not name:
            raise Exception, "The split PO name is missing - please check at the message rule!"
            
        name = source + '.' + name
        po_ids = self.search(cr, uid, [('partner_ref', '=', name), ('state', '!=', 'cancelled')])
        if not po_ids:
            raise Exception, "The split PO " + name + " not found!"
        return po_ids[0]

    def check_mandatory_fields(self, cr, uid, so_dict):
        if not so_dict.get('delivery_confirmed_date'):
            raise Exception, "The delivery confirmed date is missing - please check at the message rule!"

        if not so_dict.get('state'):
            raise Exception, "The state of the split FO is missing - please check at the message rule!"
    
    def update_split_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        print "Update the split PO when the sourced FO got confirmed", source
        
        so_dict = so_info.to_dict()
        po_id = self.check_update(cr, uid, source, so_dict)
        self.check_mandatory_fields(cr, uid, so_dict)

        so_po_common = self.pool.get('so.po.common')
        
        header_result = {}
        so_po_common.retrieve_po_header_data(cr, uid, source, header_result, so_dict, context)
        header_result['order_line'] = so_po_common.get_lines(cr, uid, so_info, po_id, context)

        default = {}
        default.update(header_result)
        
        res_id = self.write(cr, uid, po_id, default, context=context)
        
        wf_service = netsvc.LocalService("workflow")
        if so_info.state == 'validated':
            ret = wf_service.trg_validate(uid, 'purchase.order', po_id, 'purchase_confirm', cr)
        else:
            ret = wf_service.trg_validate(uid, 'purchase.order', po_id, 'purchase_confirm', cr)
            ret = wf_service.trg_validate(uid, 'purchase.order', po_id, 'purchase_approve', cr)
        return ret
        

purchase_order_sync()