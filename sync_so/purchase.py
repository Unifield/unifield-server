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
        'push_fo': fields.boolean('The Push FO case', readonly=False),
    }

    _defaults = {
        'split_po': False,
        'push_fo': False
    }

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({'active': True, 'split_po' : False})
        return super(purchase_order_sync, self).copy(cr, uid, id, default, context=context)
        
    def create_split_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        print "call purchase order", source
        
        so_dict = so_info.to_dict()
        so_po_common = self.pool.get('so.po.common')
        
        header_result = {}
        so_po_common.retrieve_po_header_data(cr, uid, source, header_result, so_dict, context)
        
        header_result['order_line'] = so_po_common.get_lines(cr, uid, so_info, False, False, False, False, context)
        header_result['split_po'] = True
        
        po_id = so_po_common.get_original_po_id(cr, uid, so_info.client_order_ref, context)
        # Check if there is the location from the original PO
        
        wf_service = netsvc.LocalService("workflow")
        if so_info.state == 'sourced':
            header_result['state'] = 'sourced'

        # get the suffix of the FO and add it into the newly created PO to make sure the reference is consistent
        partner_ref = source
        so_name_split = so_info.name.split('-')
        if len(so_name_split) == 2:
            po_name = self.browse(cr, uid, po_id, context=context)['name']
            header_result['name'] = po_name + "-" + so_name_split[1]
            partner_ref = source + "." + so_name_split[0]
        
        # UTP-163: Get the 'source document' of the original PO, and add it into the split PO, if existed
        origin = self.browse(cr, uid, po_id, context=context)['origin']
        header_result['origin'] = origin
        
        default = {}
        default.update(header_result)
        
        res_id = self.create(cr, uid, default , context=context)
        so_po_common.update_next_line_number_fo_po(cr, uid, res_id, self, 'purchase_order_line', context)
        
        # after created this splitted PO, pass it to the confirmed, as the split SO has been done so too.
        if so_info.state == 'confirmed':
            wf_service.trg_validate(uid, 'purchase.order', res_id, 'purchase_confirm', cr)
        else:
            self.write(cr, uid, res_id, {'state': 'sourced' } , context=context)
        
        # Set the original PO to "split" state -- cannot do anything with this original PO
        res_id = self.write(cr, uid, po_id, {'state' : 'split', 'active': False, 'partner_ref': partner_ref} , context=context)
        return res_id

    def normal_fo_create_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        print "call purchase order", source
        
        so_dict = so_info.to_dict()
        so_po_common = self.pool.get('so.po.common')
        
        header_result = {}
        so_po_common.retrieve_po_header_data(cr, uid, source, header_result, so_dict, context)
        
        # check whether this FO has already been sent before! if it's the case, then just update the existing PO, and not creating a new one
        po_id = self.check_existing_po(cr, uid, source, so_dict)
        header_result['order_line'] = so_po_common.get_lines(cr, uid, so_info, po_id, False, False, False, context)
        header_result['push_fo'] = True

        default = {}
        default.update(header_result)
        
        if po_id: # only update the PO
            res_id = self.write(cr, uid, po_id, default, context=context)
        else:
            # create a new PO, then send it to Validated state
            po_id = self.create(cr, uid, default , context=context)
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'purchase.order', po_id, 'purchase_confirm', cr)
            
            # update the next line number for the PO if needed        
            so_po_common.update_next_line_number_fo_po(cr, uid, po_id, self, 'purchase_order_line', context)        

        return True

    def check_existing_po(self, cr, uid, source, so_dict):
        if not source:
            raise Exception, "The partner is missing!"

        name = source + '.' + so_dict.get('name')
        po_ids = self.search(cr, uid, [('partner_ref', '=', name), ('state', '!=', 'cancelled')])
        if not po_ids:
            return False
        return po_ids[0]

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
        header_result['order_line'] = so_po_common.get_lines(cr, uid, so_info, po_id, False, True, False, context)

        default = {}
        default.update(header_result)
        
        res_id = self.write(cr, uid, po_id, default, context=context)
        
        if so_info.original_so_id_sale_order:    
            wf_service = netsvc.LocalService("workflow")
            if so_info.state == 'validated':
                ret = wf_service.trg_validate(uid, 'purchase.order', po_id, 'purchase_confirm', cr)
            else:
                ret = wf_service.trg_validate(uid, 'purchase.order', po_id, 'purchase_confirm', cr)
                ret = wf_service.trg_validate(uid, 'purchase.order', po_id, 'purchase_approve', cr)
                
        return True

    def validated_fo_update_original_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        print "The validated FO (not yet split) updates the original PO", source

        so_po_common = self.pool.get('so.po.common')
        po_id = so_po_common.get_original_po_id(cr, uid, so_info.client_order_ref, context)
        so_dict = so_info.to_dict()
        
        header_result = {}
        so_po_common.retrieve_po_header_data(cr, uid, source, header_result, so_dict, context)
        header_result['order_line'] = so_po_common.get_lines(cr, uid, so_info, po_id, False, True, False, context)
        
        partner_ref = source + "." + so_info.name
        header_result['partner_ref'] = partner_ref

        default = {}
        default.update(header_result)
        
        res_id = self.write(cr, uid, po_id, default, context=context)
        return True

purchase_order_sync()