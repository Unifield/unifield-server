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

from osv import osv, fields
from datetime import datetime
from tools.translate import _

import time
import pooler
import netsvc



class procurement_order(osv.osv):
    _name = 'procurement.order'
    _inherit = 'procurement.order'
    
    def run_threshold_value(self, cr, uid, use_new_cursor=False, context={}):
        '''
        Creates procurement for products where real stock is under threshold value
        '''
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
        start_date = datetime.now()
        
        wf_service = netsvc.LocalService("workflow")
        
        for threshold in threshold_obj.browse(cr, uid, threshold_ids, context=context):
            # Set location_id in context for tre AMC calculation
            context.update({'location_id': threshold.location_id and threshold.location_id.id or False,
                            'from_date': threshold.consumption_from,
                            'to_date': threshold.consumption_to})
            
            # Set the product list according to the category or product defined in the rule
            products = []
            if threshold.category_id:
                products.extend(product_obj.search(cr, uid, [('categ_id', '=', threshold.category_id.id)], context=context))
            elif threshold.product_id:
                products.append(threshold.product_id.id)
            
            # Set different data by products for calculation
            for product_id in products:
                product = product_obj.browse(cr, uid, product_id, context=context)
                amc = product_obj.compute_amc(cr, uid, product_id, context=context)
                
                # Set lead time according to choices in threshold rule (supplier or manual lead time)
                lead_time = threshold.supplier_lt and float(product.seller_delay)/30.0 or threshold.lead_time
                
                # Compute the threshold value
                threshold_value = threshold.threshold_manual_ok and threshold.threshold_value or amc * (lead_time + threshold.safety_month)
                threshold_value = self.pool.get('product.uom')._compute_qty(cr, uid, product.uom_id.id, threshold_value, product.uom_id.id)
                
                # Check if the quantity in stock needs a supply of products or not
                if product.virtual_available <= threshold_value:
                    # Compute the quantity to re-order
                    qty_to_order = threshold.qty_order_manual_ok and threshold.qty_to_order \
                                    or amc * (threshold.frequency + lead_time + threshold.safety_month)\
                                    - product.qty_available + product.incoming_qty - product.outgoing_qty 
                    qty_to_order = self.pool.get('product.uom')._compute_qty(cr, uid, threshold.uom_id and \
                                                                             threshold.uom_id.id or product.uom_id.id, qty_to_order,\
                                                                             product.uom_id.id)
                    
                    proc_id = proc_obj.create(cr, uid, {
                                        'name': _('Threshold value: %s') % (threshold.name,),
                                        'origin': threshold.name,
                                        'date_planned': time.strftime('%Y-%m-%d %H:%M:%S'),
                                        'product_id': product.id,
                                        'product_qty': qty_to_order,
                                        'product_uom': product.uom_id.id,
                                        'location_id': threshold.location_id.id,
                                        'procure_method': 'make_to_order',
                    })
                    wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)
                    wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_check', cr)
                    
                    created_proc.append(proc_id)
                
                
                    
        for proc in proc_obj.browse(cr, uid, created_proc):
            if proc.state == 'exception':
                report.append('PROC %d: from stock - %3.2f %-5s - %s' % \
                               (proc.id, proc.product_qty, proc.product_uom.name,
                                proc.product_id.name,))
                report_except += 1
                
        end_date = datetime.now()
                
        summary = '''Here is the procurement scheduling report for Threshold values

        Start Time: %s
        End Time: %s
        Total Procurements processed: %d
        Procurements with exceptions: %d
        \n'''% (start_date, end_date, len(created_proc), report_except)
        summary += '\n'.join(report)
        req_id = request_obj.create(cr, uid,
                {'name': "Procurement Processing Report (Threshold values).",
                 'act_from': uid,
                 'act_to': uid,
                 'body': summary,
                })
        if req_id:
            request_obj.request_send(cr, uid, [req_id])
        
        if use_new_cursor:
            cr.commit()
            cr.close()
            
        return {}

procurement_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
