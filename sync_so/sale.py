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
import so_po_common
pp = pprint.PrettyPrinter(indent=4)

class sale_order_sync(osv.osv):
    _inherit = "sale.order"
    
    _columns = {
                'received': fields.boolean('Received by Client', readonly=True),
    }
    
    def create_so(self, cr, uid, source, po_info, context=None):
        if not context:
            context = {}
        po_dict = po_info.to_dict()
        so_po_common = self.pool.get('so.po.common')
        
        header_result = {}
        so_po_common.retrieve_so_header_data(cr, uid, source, header_result, po_dict, context)
        header_result['order_line'] = so_po_common.get_lines(cr, uid, po_info, False, context)
        
        default = {}
        default.update(header_result)

        res_id = self.create(cr, uid, default , context=context)
        return True

    def validated_po_update_validated_so(self, cr, uid, source, po_info, context=None):
        if not context:
            context = {}
        po_dict = po_info.to_dict()
        so_po_common = self.pool.get('so.po.common')
        
        header_result = {}
        so_po_common.retrieve_so_header_data(cr, uid, source, header_result, po_dict, context)
        header_result['order_line'] = so_po_common.get_lines(cr, uid, po_info, False, context)
        
        default = {}
        default.update(header_result)

        res_id = self.write(cr, uid, default , context=context)
        return True

    def update_sub_so_ref(self, cr, uid, source, po_info, context=None):
        if not context:
            context = {}
            
        so_po_common = self.pool.get('so.po.common')
        so_id = so_po_common.get_original_so_id(cr, uid, po_info.partner_ref, context)
        
        client_order_ref = source + "." + po_info.name
        res_id = self.write(cr, uid, so_id, {'client_order_ref': client_order_ref} , context=context)
        return True

sale_order_sync()

