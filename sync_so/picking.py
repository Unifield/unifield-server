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

class stock_picking(osv.osv):
    '''
    synchronization methods related to stock picking objects
    '''
    _inherit = "stock.picking"

    def out_fo_updates_in_po(self, cr, uid, source, out_info, context=None):
        '''
        method called when the OUT at coordo level updates the corresponding IN at project level
        '''
        if context is None:
            context = {}
        print "call update In in PO from Out in FO", source
        
        so_dict = out_info.to_dict()
        # objects
        so_po_common = self.pool.get('so.po.common')
        po_obj = self.pool.get('purchase.order')
                
        # Look for the PO name, which has the reference to the FO on Coordo as source.out_info.origin
        so_ref = source + "." + out_info.origin
        po_id = so_po_common.get_po_id_by_so_ref(cr, uid, so_ref, context)
        po_name = po_obj.browse(cr, uid, po_id, context=context)['name']
        
        # Then from this PO, get the IN with the reference to that PO, and update the data received from the OUT of FO to this IN
        in_id = so_po_common.get_in_id(cr, uid, po_name, context)
        
        header_result = {}
        header_result['note'] = out_info.note
        header_result['min_date'] = out_info.min_date

        #header_result['move_lines'] = so_po_common.get_stock_move_lines(cr, uid, out_info, context)
        
        default = {}
        default.update(header_result)
        
        # Update the Incoming Shipment
        res_id = self.write(cr, uid, in_id, default, context=context)
        return res_id

stock_picking()
