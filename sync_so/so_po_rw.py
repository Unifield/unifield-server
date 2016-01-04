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
from sync_client import get_sale_purchase_logger
from sync_common import xmlid_to_sdref

class sale_order_rw(osv.osv):
    _inherit = "sale.order"
    _logger = logging.getLogger('------sync.sale.order')

    def usb_replicate_fo(self, cr, uid, source, sync_values, context=None):
        po_dict = sync_values.to_dict()
        fo_name = po_dict.get('name', False)
        self._logger.info("+++ RW: Replicate the FO/IR: %s from %s to %s" % (fo_name, source, cr.dbname))
        if not context:
            context = {}

        rw_type = self.pool.get('stock.picking')._get_usb_entity_type(cr, uid)
        if rw_type == self.pool.get('stock.picking').CENTRAL_PLATFORM:
            message = "Sorry, this feature is only available for Remote Warehouse Instances"
            self._logger.info(message)
            return message

        so_po_common = self.pool.get('so.po.common')
        context['no_check_line'] = True

        header_result = {}
        so_po_common.retrieve_so_header_data(cr, uid, source, header_result, po_dict, context)
        header_result['name'] = fo_name
        header_result['state'] = 'rw'
        
        # UF-2531: Only set the procurement request if it's a IR
        if 'IR' in fo_name:     
            context['procurement_request'] = True        
            header_result['procurement_request'] = True
        
        if po_dict.get('partner_id'):
            rec_id = self.pool.get('res.partner').find_sd_ref(cr, uid, xmlid_to_sdref(po_dict.get('partner_id')['id']), context=context)
            if rec_id:
                header_result['partner_id'] = rec_id

        # If there is a location requestor for IR, retrieve it
        if po_dict.get('location_requestor_id'):
            rec_id = self.pool.get('stock.location').find_sd_ref(cr, uid, xmlid_to_sdref(po_dict.get('location_requestor_id')['id']), context=context)
            if rec_id:
                header_result['location_requestor_id'] = rec_id

        default = {}
        default.update(header_result)
        context['offline_synchronization'] = True

        existing_ids = self.search(cr, uid, [('name', '=', fo_name),('state',
            '=', 'rw')], force_no_order=True, limit=1, context=context)
        if existing_ids:
            message = "Sorry, the FO: " + fo_name  + " existed already in " + cr.dbname
            self._logger.info(message)
            return message            

        so_id = self.create(cr, uid, default , context=context)
        rw_xmlid = so_po_common.get_xml_id_counterpart(cr, uid, self, context=context)        
        # get xmlid and create a new one with the same res
        self.pool.get('ir.model.data').manual_create_sdref(cr, uid, self, rw_xmlid, so_id, context=context)

        order_line = so_po_common.get_lines(cr, uid, source, sync_values, False, False, False, True, context)
        context['offline_synchronization'] = True
        line_obj = self.pool.get('sale.order.line')
        for line in order_line:
            line = line[2]
            line.update({'order_id': so_id})
            so_po_common.create_rw_xml_for_line(cr, uid, line_obj,line, context =context)
        
        # Just to print the result message when the sync message got executed
        message = "The IR/FO " + fo_name + " has been well replicated at " + cr.dbname
        self._logger.info(message)
        return message

sale_order_rw()



class purchase_order_rw(osv.osv):
    _inherit = "purchase.order"
    _logger = logging.getLogger('------sync.purchase.order')

    def usb_replicate_po(self, cr, uid, source, sync_values, context=None):
        so_dict = sync_values.to_dict()
        po_name = so_dict.get('name', False)
        self._logger.info("+++ RW: Replicate the PO: %s from %s to %s" % (po_name, source, cr.dbname))
        if not context:
            context = {}

        rw_type = self.pool.get('stock.picking')._get_usb_entity_type(cr, uid)
        if rw_type == self.pool.get('stock.picking').CENTRAL_PLATFORM:
            message = "Sorry, this feature is only available for Remote Warehouse Instances"
            self._logger.info(message)
            return message

        so_po_common = self.pool.get('so.po.common')
        header_result = {}
        so_po_common.retrieve_po_header_data(cr, uid, source, header_result, so_dict, context)
        
        header_result['state'] = 'rw'
        header_result['name'] = po_name
        if so_dict.get('partner_id'):
            rec_id = self.pool.get('res.partner').find_sd_ref(cr, uid, xmlid_to_sdref(so_dict.get('partner_id')['id']), context=context)
            if rec_id:
                header_result['partner_id'] = rec_id
                partner = self.pool.get('res.partner').browse(cr, uid, rec_id, context=context)
                
                # US-208: Retrieve the pricelist: if it's provided from sync, then use it
                if 'pricelist_id' in so_dict and so_dict.get('pricelist_id', True):
                    pl_xmlid = so_dict.get('pricelist_id')['id']
                    if pl_xmlid:
                        header_result['pricelist_id'] = self.pool.get('product.pricelist').find_sd_ref(cr, uid, xmlid_to_sdref(pl_xmlid), context=context)
                elif partner.property_product_pricelist_purchase:
                    header_result['pricelist_id'] = partner.property_product_pricelist_purchase.id
                # In any case, if the code does not enter in the block above, the default pricelist_id is still used 
        
        header_result['cross_docking_ok'] = so_dict.get('cross_docking_ok', False)
        
        # check whether this FO has already been sent before! if it's the case, then just update the existing PO, and not creating a new one
        partner_ref = source + "." + sync_values.name
        existing_ids = self.search(cr, uid, [('name', '=', po_name),
            ('partner_ref', '=', partner_ref), ('state', '=', 'rw')],
            force_no_order=True, limit=1, context=context)
        if existing_ids:
            message = "Sorry, the FO: " + po_name  + " with Supplier Ref " + partner_ref + " existed already in " + cr.dbname
            self._logger.info(message)
            return message
                    
        default = {}
        default.update(header_result)

        # create a new PO, then send it to Validated state
        po_id = self.create(cr, uid, default , context=context)
        rw_xmlid = so_po_common.get_xml_id_counterpart(cr, uid, self, context=context)        
        # get xmlid and create a new one with the same res
        self.pool.get('ir.model.data').manual_create_sdref(cr, uid, self, rw_xmlid, po_id, context=context)

        context['offline_synchronization'] = True
        line_obj = self.pool.get('purchase.order.line')
        order_line = so_po_common.get_lines(cr, uid, source, sync_values, False, False, False, False, context)
        for line in order_line:
            line = line[2]
            line.update({'order_id': po_id})
            so_po_common.create_rw_xml_for_line(cr, uid, line_obj,line, context =context)
            
        message = "The PO " + po_name + " has been well replicated at " + cr.dbname
        self._logger.info(message)
        return message
    
purchase_order_rw()


