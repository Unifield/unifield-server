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
        
        
        fields used for info and consistency check only:
        'update_version_from_in_stock_picking': 
        'partner_type_stock_picking'
        
        fields used for update:
        'move_lines/product_qty' -> used for update product_qty AND product_uos_qty
        
        dates:
        - we update both date and date_expected at line level. date_expected is sychronized because is the expected date
          and date is also synchronized for consistency. Date is updated with actual date when the picking is processed to done (action_done@stock_move) 
        
        rules:
        - we do not updated objects with state 'done'
        - 
        '''
        if context is None:
            context = {}
        print "call update In in PO from Out in FO", source
        
        pick_dict = out_info.to_dict()
        
        # objects
        so_po_common = self.pool.get('so.po.common')
        po_obj = self.pool.get('purchase.order')
        
        # update header
        
        
        # update lines
        if 'move_lines' in pick_dict:
            for line in pick_dict['move_lines']:
                
                pass
        
        pp.pprint(pick_dict)
        return True
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
