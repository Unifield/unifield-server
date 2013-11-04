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
import netsvc
import so_po_common
import logging


class purchase_order_line_sync(osv.osv):
    _inherit = 'purchase.order.line'
    
    _columns = {
        'original_purchase_line_id': fields.text(string='Original purchase line id'),
    }
    
purchase_order_line_sync()


class purchase_order_sync(osv.osv):
    _inherit = "purchase.order"
    _logger = logging.getLogger('------sync.purchase.order')
    
    
    _columns = {
        'sended_by_supplier': fields.boolean('Sended by supplier', readonly=True),
        'split_po': fields.boolean('Created by split PO', readonly=True),
        'push_fo': fields.boolean('The Push FO case', readonly=False),
        'from_sync': fields.boolean('Updated by synchronization', readonly=False),
        'po_updated_by_sync': fields.boolean('PO updated by sync', readonly=False),
    }

    _defaults = {
        'split_po': False,
        'push_fo': False,
        'sended_by_supplier': True,
        'po_updated_by_sync': False,
    }

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({'active': True, 'split_po' : False, 'po_updated_by_sync': False})
        return super(purchase_order_sync, self).copy(cr, uid, id, default, context=context)
        
    def create_split_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        self._logger.info("+++ Create the split PO at destination (at %s) from the split FO at supplier (at %s)"%(cr.dbname,source))
        
        so_dict = so_info.to_dict()
        so_po_common = self.pool.get('so.po.common')
        
        header_result = {}
        so_po_common.retrieve_po_header_data(cr, uid, source, header_result, so_dict, context)
        
        header_result['order_line'] = so_po_common.get_lines(cr, uid, so_info, False, False, False, False, context)
        header_result['split_po'] = True
        
        po_id = so_po_common.get_original_po_id(cr, uid, source, so_info, context)
        
        if so_info.state == 'sourced':
            header_result['state'] = 'sourced'

        # Name the new split PO to stick with the name of FO (FOxxxx-1, FOxxxx-2 or FOxxxx-3)
        if so_info.name[-2] == '-' and so_info.name[-1] in ['1', '2', '3']:
            po_name = self.browse(cr, uid, po_id, context=context)['name']
            header_result['name'] = po_name + so_info.name[-2:]
        
        # UTP-163: Get the 'source document' of the original PO, and add it into the split PO, if existed
        origin = self.browse(cr, uid, po_id, context=context)['origin']
        header_result['origin'] = origin
        
        default = {}
        default.update(header_result)
        
        line_obj = self.pool.get('purchase.order.line')
        for line in default['order_line']:
            orig_line = line_obj.search(cr, uid, [('sync_order_line_db_id', '=', line[2].get('original_purchase_line_id'))])
            if orig_line:
                orig_line = line_obj.browse(cr, uid, orig_line[0], context=context)
                line[2].update({'move_dest_id': orig_line.move_dest_id and orig_line.move_dest_id.id or False})
        
        res_id = self.create(cr, uid, default , context=context)
        so_po_common.update_next_line_number_fo_po(cr, uid, res_id, self, 'purchase_order_line', context)
        
        proc_ids = []
        order_ids = []
        order = self.browse(cr, uid, res_id, context=context)
        for order_line in order.order_line:
            if order_line.original_purchase_line_id:
                orig_line = line_obj.search(cr, uid, [('sync_order_line_db_id', '=', order_line.original_purchase_line_id)], context=context)
                if orig_line:
                    line = line_obj.browse(cr, uid, orig_line[0], context=context)
                    if line.procurement_id:
                        line_obj.write(cr, uid, [order_line.id], {'procurement_id': line.procurement_id.id})
                        proc_ids.append(line.procurement_id.id)
                    if line.order_id:
                        order_ids.append(line.order_id.id)
                    
        if proc_ids:
            self.pool.get('procurement.order').write(cr, uid, proc_ids, {'purchase_id': res_id}, context=context)
            netsvc.LocalService("workflow").trg_change_subflow(uid, 'procurement.order', proc_ids, 'purchase.order', order_ids, res_id, cr)

        fo_ids = self.pool.get('sale.order').search(cr, uid, [('loan_id', '=', po_id)], context=context)
        if fo_ids:
            netsvc.LocalService("workflow").trg_change_subflow(uid, 'sale.order', fo_ids, 'purchase.order', [po_id], res_id, cr)
        
        # after created this splitted PO, pass it to the confirmed, as the split SO has been done so too.
        if so_info.state in ('confirmed', 'progress'):
            netsvc.LocalService("workflow").trg_validate(uid, 'purchase.order', res_id, 'purchase_confirm', cr)
        else:
            self.write(cr, uid, res_id, {'state': 'sourced' } , context=context)
        
        # Set the original PO to "split" state -- cannot do anything with this original PO, and update the partner_ref
        partner_ref = so_po_common.get_full_original_fo_ref(source, so_info.name)
        self.write(cr, uid, po_id, {'state' : 'split', 'active': False, 'partner_ref': partner_ref} , context=context)
        
        # if it is a loan type, then update the source 
        if 'order_type' in header_result:
            if header_result['order_type'] == 'loan':
                # UTP-392: In the push flow, the FO counterpart could be created first by the sync, then the original PO will be created
                # so in this case, when creating the PO, the FO counterpart must be linked to the new split PO
                name = self.browse(cr, uid, res_id, context).partner_ref # get the partner_ref from Coordo
                so_object = self.pool.get('sale.order')
                so_ids = so_object.search(cr, uid, [('origin', '=', name)], context=context) # search the existing FO counterpart
                if so_ids and so_ids[0]: # if exist, then update the link to it with this new split PO
                    name = so_object.browse(cr, uid, so_ids[0], context).name
                    self.write(cr, uid, [res_id], {'origin': name}, context=context)
                    so_object.write(cr, uid, so_ids, {'origin': False} , context=context) # reset this origin value of the FO counterpart back to null
        
        return res_id

    def normal_fo_create_po(self, cr, uid, source, so_info, context=None):
        self._logger.info("+++ Create a PO (at %s) from an FO (push flow) (from %s)"%(cr.dbname, source))
        if not context:
            context = {}
        
        so_dict = so_info.to_dict()
        so_po_common = self.pool.get('so.po.common')
        
        header_result = {}
        so_po_common.retrieve_po_header_data(cr, uid, source, header_result, so_dict, context)
        
        # check whether this FO has already been sent before! if it's the case, then just update the existing PO, and not creating a new one
        po_id = self.check_existing_po(cr, uid, source, so_dict)
        header_result['order_line'] = so_po_common.get_lines(cr, uid, so_info, po_id, False, False, False, context)
        header_result['push_fo'] = True
        header_result['origin'] = so_dict.get('name', False)

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
        self._logger.info("+++ Update the split POs at %s when the sourced FO at %s got confirmed"%(cr.dbname, source))
        
        so_dict = so_info.to_dict()
        po_id = self.check_update(cr, uid, source, so_dict)
        self.check_mandatory_fields(cr, uid, so_dict)

        so_po_common = self.pool.get('so.po.common')
        
        header_result = {}
        so_po_common.retrieve_po_header_data(cr, uid, source, header_result, so_dict, context)
        header_result['order_line'] = so_po_common.get_lines(cr, uid, so_info, po_id, False, True, False, context)
        header_result['po_updated_by_sync'] = True

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
        self._logger.info("+++ Update the original PO at %s when the relevant FO at %s got validated"%(cr.dbname, source))

        so_po_common = self.pool.get('so.po.common')
        po_id = so_po_common.get_original_po_id(cr, uid, source, so_info, context)
        so_dict = so_info.to_dict()
        
        header_result = {}
        so_po_common.retrieve_po_header_data(cr, uid, source, header_result, so_dict, context)
        header_result['order_line'] = so_po_common.get_lines(cr, uid, so_info, po_id, False, True, False, context)
        
        partner_ref = source + "." + so_info.name
        header_result['partner_ref'] = partner_ref
        header_result['po_updated_by_sync'] = True

        default = {}
        default.update(header_result)
        
        res_id = self.write(cr, uid, po_id, default, context=context)
        return True
    
    def msg_close_filter(self, cr, uid, rule, context=None):
        """
        Called by PO close message rule at RW
        @return: list of ids of unclosed PO's whose pickings are all done
        """
        cr.execute("""\
            SELECT p.id from purchase_order p 
            left join stock_picking s on s.purchase_id = p.id 
            where p.state = 'approved' 
            group by p.id 
            having bool_and(s.state = 'done') = true;""")
        return [row[0] for row in cr.fetchall()]
    
    def msg_close(self, cr, uid, source, po, context=None):
        po_id = self.search(cr, uid, [('name','=',po.name)])
        self.action_done(cr, uid, po_id, context=context)

    def canceled_fo_cancel_po(self, cr, uid, source, so_info, context=None):
        if not context:
            context = {}
        self._logger.info("+++ Cancel the original PO at %s due to the cancel of the FO at %s"%(cr.dbname,source))
        wf_service = netsvc.LocalService("workflow")
        so_po_common = self.pool.get('so.po.common')
        po_id = so_po_common.get_original_po_id(cr, uid, source, so_info, context)
        self.write(cr, uid, po_id, {'from_sync': True}, context)
        # Cancel the PO
        wf_service.trg_validate(uid, 'purchase.order', po_id, 'purchase_cancel', cr)
        return True

purchase_order_sync()
