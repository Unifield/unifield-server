#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
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
from tools.translate import _
from lxml import etree

import time

class po_follow_up(osv.osv_memory):
    _name = 'po.follow.up'
    _description = 'PO Follow up report wizard'
    
    STATE_SELECTION = [
         ('sourced', 'Sourced'),
         ('confirmed', 'Validated'),
         ('confirmed_wait', 'Confirmed (waiting)'),
         ('approved', 'Confirmed'),               
    ]
    
    _columns = {
         'name':fields.many2one('purchase.order',string="Order Reference", help="Unique number of the Purchase Order. Optional", required=False),
         'state': fields.selection(STATE_SELECTION, 'State', help="The state of the purchase order. Optional", select=True, required=False),
         'po_date_from':fields.date("PO date from", required="False"),
         'po_date_thru':fields.date("PO date through", required="False"),
         'partner_id':fields.many2one('res.partner', 'Supplier', required=False),
         'project_ref':fields.char('Supplier reference', size=64, required=False),
         'export_format': fields.selection([('xls', 'Excel'), ('pdf', 'PDF')], string="Export format", required=True),     
    }
    
    def button_validate(self, cr, uid, ids, context=None):
        for x in self.browse(cr,uid,ids):
            print x.name
            print x.state
        #return True
    
        datas = {'ids': ids}                                                    
                                                                                
        return {                                                                
            'type': 'ir.actions.report.xml',                                    
            'report_name': 'po.follow.up_xls',                                         
            'datas': datas,                                                     
            'nodestroy': True,                                                  
            'context': context,                                                 
        }
    
    
    
po_follow_up()