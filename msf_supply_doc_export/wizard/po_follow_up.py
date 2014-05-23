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
         'po_id':fields.many2one('purchase.order',string="Order Reference", help="Unique number of the Purchase Order. Optional", required=False),
         'state': fields.selection(STATE_SELECTION, 'State', help="The state of the purchase order. Optional", select=True, required=False),
         'po_date_from':fields.date("PO date from", required="False"),
         'po_date_thru':fields.date("PO date through", required="False"),
         'partner_id':fields.many2one('res.partner', 'Supplier', required=False),
         'project_ref':fields.char('Supplier reference', size=64, required=False),
         'export_format': fields.selection([('xls', 'Excel'), ('pdf', 'PDF')], string="Export format", required=True),     
    }
    
    def button_validate(self, cr, uid, ids, context=None):
        x = self.browse(cr,uid,ids)[0]
        
        # PO number
        if x.po_id:
            po_id_criteria = ('id','=', x.po_id.id)
        else:
            po_id_criteria = ('id','>',0)
   
        # State
        if x.state:
            state_criteria = ('state','=', x.state)
        else:
            state_criteria = ('state','in',['sourced','confirmed','confirmed_wait','approved'])
            
        # Dates
        if x.po_date_from:
            from_date_criteria = ('date_order','>=',x.po_date_from)
        else:
            from_date_criteria = (1,'=',1)
            
        if x.po_date_thru:
            thru_date_criteria = ('date_order','<=',x.po_date_thru)
        else:
            thru_date_criteria = (1,'=',1)
            
        
        # Supplier
        if x.partner_id:
            partner_criteria = ('supplier_id','=', x.supplier_id.id)
        else:
            partner_criteria = ('supplier_id','>',0)
            
        # Supplier Reference
        if x.project_ref:
            crit = x.project_ref
        else:
            crit = ''
        ref_criteria = ('project_ref','like',crit)
        
        # get the PO ids based on the selected criteria
        po_obj = self.pool.get('purchase.order')
        domain = [state_criteria, po_id_criteria, from_date_criteria, thru_date_criteria, ref_criteria]
        po_ids = po_obj.search(cr, uid, domain)
        
        
        if not po_ids:
            raise osv.except_osv(_('Error'), _('No Purchase Orders match the specified criteria.'))
            return True
        
        report_header = []
        report_header.append('MULTIPLE PURCHASE ORDER FOLLOW-UP')
        
        report_header_line2 = ''
        if x.partner_id:
            report_header_line2 += x.partner_id.name
        report_header_line2 += '  Report run date: ' + time.strftime("%d/%m/%Y")
        if x.po_date_from:
            report_header_line2 += x.po_date_from.strftime("%d/%m/%Y") + ' - ' + x.po_date_thru.strftime("%d/%m/%Y")
        report_header.append(report_header_line2)
      
        datas = {'ids': po_ids, 'report_header': report_header}       
        if x.export_format == 'xls':
            report_name = 'po.follow.up_xls'
        else:
            report_name = 'po.follow.up_rml'
            
                                                                                
        return {                                                                
            'type': 'ir.actions.report.xml',                                    
            'report_name': report_name,                                         
            'datas': datas,                                                     
            'nodestroy': True,                                                  
            'context': context,                                                 
        }
    
po_follow_up()