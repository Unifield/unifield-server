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

import logging

from osv import osv, fields
import so_po_common
from sync_client import get_sale_purchase_logger

class sale_order_line_sync(osv.osv):
    _inherit = "sale.order.line"
    
    _columns = {
        'source_sync_line_id': fields.text(string='Sync DB id of the PO origin line'),
    }
    
sale_order_line_sync()


class sale_order_sync(osv.osv):
    _inherit = "sale.order"
    _logger = logging.getLogger('------sync.sale.order')
    
    _columns = {
                'received': fields.boolean('Received by Client', readonly=True),
                'fo_created_by_po_sync': fields.boolean('FO created by PO after SYNC', readonly=True),
    }
    
    _defaults = {
        'fo_created_by_po_sync': False,
    }

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        if not default.get('name', False) or not '-2' in default.get('name', False).split('/')[-1]:
            default.update({'fo_created_by_po_sync': False})
        return super(sale_order_sync, self).copy(cr, uid, id, default, context=context)

    def create_so(self, cr, uid, source, po_info, context=None):
        self._logger.info("+++ Create an FO at %s from a PO (normal flow) at %s"%(cr.dbname, source))
        if not context:
            context = {}
            
        context['no_check_line'] = True
        po_dict = po_info.to_dict()
        so_po_common = self.pool.get('so.po.common')
        
        header_result = {}
        so_po_common.retrieve_so_header_data(cr, uid, source, header_result, po_dict, context)
        header_result['order_line'] = so_po_common.get_lines(cr, uid, po_info, False, False, False, True, context)
        # [utp-360] we set the confirmed_delivery_date to False directly in creation and not in modification
        order_line = []
        for line in header_result['order_line']:
            line[2].update({'confirmed_delivery_date': False, 'source_sync_line_id': line[2]['sync_order_line_db_id']})
            order_line.append((0, 0, line[2]))
        header_result['order_line'] = order_line
        
        default = {}
        default.update(header_result)

        so_id = self.create(cr, uid, default , context=context)

        if 'order_type' in header_result:
            if header_result['order_type'] == 'loan':
                # UTP-392: Look for the PO of this loan, and update the reference of source document of that PO to this new FO
                # First, search the original PO via the client_order_ref stored in the FO
                ref = po_info.origin
                if ref:
                    name = self.browse(cr, uid, so_id, context).name
                    ref = source + "." + ref
                    po_object = self.pool.get('purchase.order')
                    po_ids = po_object.search(cr, uid, [('partner_ref', '=', ref)], context=context)
                    
                    # in both case below, the FO become counter part
                    if po_ids: # IF the PO Loan has already been created, if not, just update the value reference, then when creating the PO loan, this value will be updated 
                        # link the FO loan to this PO loan
                        po_object.write(cr, uid, po_ids, {'origin': name}, context=context)
                        self.write(cr, uid, [so_id], {'fo_created_by_po_sync': True} , context=context)
                    else:
                        self.write(cr, uid, [so_id], {'origin': ref, 'fo_created_by_po_sync': True} , context=context)
                
        # reset confirmed_delivery_date to all lines
        so_line_obj = self.pool.get('sale.order.line')
        
        # [utp-360] we set the confirmed_delivery_date to False directly in creation and not in modification
#        for order in self.browse(cr, uid, [so_id], context=context):
#            for line in order.order_line:
#                so_line_obj.write(cr, uid, [line.id], {'confirmed_delivery_date': False})
        
        so_po_common.update_next_line_number_fo_po(cr, uid, so_id, self, 'sale_order_line', context)        
        return True

    def validated_po_update_validated_so(self, cr, uid, source, po_info, context=None):
        self._logger.info("+++ Update the validated FO at %s when the relevant PO got validated at %s"%(cr.dbname, source))
        if not context:
            context = {}
        context['no_check_line'] = True
            
        po_dict = po_info.to_dict()
        so_po_common = self.pool.get('so.po.common')
        
        header_result = {}
        so_po_common.retrieve_so_header_data(cr, uid, source, header_result, po_dict, context)
        so_id = so_po_common.get_original_so_id(cr, uid, po_info.partner_ref, context)
        
        header_result['order_line'] = so_po_common.get_lines(cr, uid, po_info, False, so_id, True, False, context)
        
        default = {}
        default.update(header_result)

        res_id = self.write(cr, uid, so_id, default , context=context)
        return True

    def update_sub_so_ref(self, cr, uid, source, po_info, context=None):
        self._logger.info("+++ Update the PO references from %s to the FO, including its sub-FOs at %s"%(source, cr.dbname))
        if not context:
            context = {}
            
        context['no_check_line'] = True
        so_po_common = self.pool.get('so.po.common')
        so_id = so_po_common.get_original_so_id(cr, uid, po_info.partner_ref, context)
        
        ref = self.browse(cr, uid, so_id).client_order_ref
        client_order_ref = source + "." + po_info.name
        
        if not ref or client_order_ref != ref: # only issue a write if the client_order_reference is not yet set!
            res_id = self.write(cr, uid, so_id, {'client_order_ref': client_order_ref} , context=context)
        
        '''
            Now search all sourced-FOs and update the reference if they have not been set at the moment of sourcing
            The person at coordo just does the whole push flow FO process until the end (sourcing the FO without sync before and thus the client_ref 
            of the sourced FO will have no client_ref)
        '''    
        line_ids = self.search(cr, uid, [('original_so_id_sale_order', '=', so_id)], context=context)
        for line in line_ids:
            temp = self.browse(cr, uid, line).client_order_ref
            if not temp: # only issue a write if the client_order_reference is not yet set!
                res_id = self.write(cr, uid, line, {'client_order_ref': client_order_ref} , context=context)
            
        return True

    def on_create(self, cr, uid, id, values, context=None):
        if context is None \
           or not context.get('sync_message_execution') \
           or context.get('no_store_function'):
            return
        logger = get_sale_purchase_logger(cr, uid, self, id, context=context)
        logger.action_type = 'creation'
        logger.is_product_added |= (len(values.get('order_line', [])) > 0)

    def on_change(self, cr, uid, changes, context=None):
        if context is None \
           or not context.get('sync_message_execution') \
           or context.get('no_store_function'):
            return
        # create a useful mapping purchase.order ->
        #    dict_of_purchase.order.line_changes
        lines = {}
        if 'sale.order.line' in context['changes']:
            for rec_line in self.pool.get('sale.order.line').browse(
                    cr, uid,
                    context['changes']['sale.order.line'].keys(),
                    context=context):
                if self.pool.get('sale.order.line').exists(cr, uid, rec_line.id, context): # check the line exists
                    lines.setdefault(rec_line.order_id.id, {})[rec_line.id] = context['changes']['sale.order.line'][rec_line.id]
        # monitor changes on purchase.order
        for id, changes in changes.items():
            logger = get_sale_purchase_logger(cr, uid, self, id, \
                context=context)
            if 'order_line' in changes:
                old_lines, new_lines = map(set, changes['order_line'])
                logger.is_product_added |= (len(new_lines - old_lines) > 0)
                logger.is_product_removed |= (len(old_lines - new_lines) > 0)
            logger.is_date_modified |= ('date_order' in changes)
            logger.is_status_modified |= ('state' in changes)
            # handle line's changes
            for line_id, line_changes in lines.get(id, {}).items():
                logger.is_quantity_modified |= \
                    ('product_uom_qty' in line_changes)
                logger.is_product_price_modified |= \
                    ('price_unit' in line_changes)

sale_order_sync()
