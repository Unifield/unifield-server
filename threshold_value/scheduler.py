# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF 
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
from tools.translate import _

import pooler
import netsvc
import time

class procurement_order(osv.osv):
    _name = 'procurement.order'
    _inherit = 'procurement.order'
    
    def run_threshold_value(self, cr, uid, use_new_cursor=False, batch_id=False, context=None):
        '''
        Creates procurement for products where real stock is under threshold value
        '''
        if context is None:
            context = {}

        if use_new_cursor:
            cr = pooler.get_db(use_new_cursor).cursor()
            
        request_obj = self.pool.get('res.request')
        threshold_obj = self.pool.get('threshold.value')
        proc_obj = self.pool.get('procurement.order')
        product_obj = self.pool.get('product.product')
        
        threshold_ids = threshold_obj.search(cr, uid, [], context=context)
                
        created_proc = []
        report = []
        report_except = 0
        start_date = time.strftime('%Y-%m-%d %H:%M:%S')
        
        wf_service = netsvc.LocalService("workflow")

        self.check_exception_proc(cr, uid, [], context=context)
        
        # Put a lock on thershold rules
        threshold_obj.write(cr, uid, threshold_ids, {}, context=context)
        for threshold in threshold_obj.browse(cr, uid, threshold_ids, context=context):
            c = context.copy()
            c.update({'location': threshold.location_id.id, 'compute_child': True, 'states': ['confirmed', 'waiting', 'assigned', 'done', 'hidden'], 'what': ['in', 'out']})
            line_ids = self.pool.get('threshold.value.line').search(cr, uid, [('threshold_value_id', '=', threshold.id)], context=c)
            for line in self.pool.get('threshold.value.line').browse(cr, uid, line_ids, context=c):
                product_av_qty = product_obj.get_product_available(cr, uid, [line.product_id.id], context=c)[line.product_id.id]
                if line.threshold_value >= product_av_qty and line.product_qty > 0.00:
                    proc_id = proc_obj.create(cr, uid, {
                                        'name': _('Threshold value: %s') % (threshold.name,),
                                        'origin': threshold.name,
                                        'unique_rule_type': 'threshold.value',
                                        'date_planned': line.required_date or time.strftime('%Y-%m-%d %H:%M:%S'),
                                        'product_id': line.product_id.id,
                                        'product_qty': line.product_qty,
                                        'product_uom': line.product_id.uom_id.id,
                                        'location_id': threshold.location_id.id,
                                        'procure_method': 'make_to_order',
                    })
                    wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)
                    wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_check', cr)
                    
                    created_proc.append(proc_id)
        
        created_doc = '''################################
Created documents : \n'''
                    
        for proc in proc_obj.browse(cr, uid, created_proc):
            if proc.state == 'exception':
                report.append('PROC %d: from stock - %3.2f %-5s - %s' % \
                               (proc.id, proc.product_qty, proc.product_uom.name,
                                proc.product_id.name,))
                report_except += 1
            elif proc.purchase_id:
                created_doc += "    * %s => %s \n" % (proc.name, proc.purchase_id.name)
                
        end_date = time.strftime('%Y-%m-%d %H:%M:%S')
                
        summary = '''Here is the procurement scheduling report for Threshold values

        Start Time: %s
        End Time: %s
        Total Procurements processed: %d
        Procurements with exceptions: %d
        \n %s \n  Exceptions: \n'''% (start_date, end_date, len(created_proc), report_except, len(created_proc) > 0 and created_doc or '')
        summary += '\n'.join(report)
        if batch_id:
            self.pool.get('procurement.batch.cron').write(cr, uid, batch_id, {'last_run_on': time.strftime('%Y-%m-%d %H:%M:%S')})
            old_request = request_obj.search(cr, uid, [('batch_id', '=', batch_id), ('name', '=', 'Procurement Processing Report (Threshold values).')])
            request_obj.write(cr, uid, old_request, {'batch_id': False})
        req_id = request_obj.create(cr, uid,
                {'name': "Procurement Processing Report (Threshold values).",
                 'act_from': uid,
                 'act_to': uid,
                 'batch_id': batch_id,
                 'body': summary,
                })
        # UF-952 : Requests should be in consistent state
#        if req_id:
#            request_obj.request_send(cr, uid, [req_id])
        
        if use_new_cursor:
            cr.commit()
            cr.close()
            
        return {}

procurement_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
