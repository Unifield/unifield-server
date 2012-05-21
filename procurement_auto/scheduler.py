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
from datetime import datetime
from tools.translate import _

import time
import pooler
import netsvc



class procurement_order(osv.osv):
    _name = 'procurement.order'
    _inherit = 'procurement.order'
    
    def run_automatic_supply(self, cr, uid, use_new_cursor=False, batch_id=False, context=None):
        '''
        Create procurement on fixed date
        '''
        if use_new_cursor:
            cr = pooler.get_db(use_new_cursor).cursor()
            
        request_obj = self.pool.get('res.request')
        auto_sup_obj = self.pool.get('stock.warehouse.automatic.supply')
        proc_obj = self.pool.get('procurement.order')
        freq_obj = self.pool.get('stock.frequence')

        start_date = time.strftime('%Y-%m-%d %H:%M:%S')
        auto_sup_ids = auto_sup_obj.search(cr, uid, [('next_date', '<=', datetime.now())])
        
        created_proc = []
        report = []
        report_except = 0
        
        # Cache for product/location
        # TODO : To confirm by Magali, cache system is very strange
        # @JF : do not integrate this if a TODO is present in the previous line, please tell QT
        cache = {}
        
        # We start with only category Automatic Supply
        for auto_sup in auto_sup_obj.browse(cr, uid, auto_sup_ids):
            # We define the replenish location
            location_id = False
            if not auto_sup.location_id or not auto_sup.location_id.id:
                location_id = auto_sup.warehouse_id.lot_input_id.id
            else:
                location_id = auto_sup.location_id.id
               
            # We create a procurement order for each line of the rule
            for line in auto_sup.line_ids:
                proc_id = self.create_proc_order(cr, uid, auto_sup, line.product_id,
                                                 line.product_uom_id.id, line.product_qty,
                                                 location_id, cache=cache, context=context)
                # If a procurement has been created, add it to the list
                if proc_id:
                    created_proc.append(proc_id)
            
            # Update the frequence to save the date of the last run
            if auto_sup.frequence_id:
                freq_obj.write(cr, uid, auto_sup.frequence_id.id, {'last_run': datetime.now()})


        ###
        # Add created document and exception in a request
        ###
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
                
        summary = '''Here is the procurement scheduling report for Automatic Supplies

        Start Time: %s
        End Time: %s
        Total Procurements processed: %d
        Procurements with exceptions: %d
        
        \n %s \n  Exceptions: \n'''% (start_date, end_date, len(created_proc), report_except, len(created_proc) > 0 and created_doc or '')
        
        summary += '\n'.join(report)
        if batch_id:
            self.pool.get('procurement.batch.cron').write(cr, uid, batch_id, {'last_run_on': time.strftime('%Y-%m-%d %H:%M:%S')})
            old_request = request_obj.search(cr, uid, [('batch_id', '=', batch_id), ('name', '=', 'Procurement Processing Report (Automatic supplies).')])
            request_obj.write(cr, uid, old_request, {'batch_id': False})
        request_obj.create(cr, uid,
                {'name': "Procurement Processing Report (Automatic supplies).",
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
    
    def create_proc_order(self, cr, uid, auto_sup, product_id, product_uom, qty, location_id, cache=None, context=None):
        '''
        Creates a procurement order for a product and a location
        '''
        proc_obj = self.pool.get('procurement.order')
        auto_sup_obj = self.pool.get('stock.warehouse.automatic.supply')
        wf_service = netsvc.LocalService("workflow")
        proc_id = False
        # TODO : To confirm by Magali, cache system is very strange
        if cache is None:
            cache = {}
        
        # Enter the stock location in cache to know which products has been already replenish for this location
        # TODO : To confirm by Magali, cache system is very strange
        # @JF : do not integrate this if a TODO is present in the previous line, please tell QT
        if not cache.get(location_id, False):
            cache.update({location_id: []})
        
        # TODO : To confirm by Magali, cache system is very strange
        # @JF : do not integrate this if a TODO is present in the previous line, please tell QT
        if product_id and product_id.id not in cache.get(location_id):
            newdate = datetime.today()
            proc_id = proc_obj.create(cr, uid, {
                                        'name': _('Automatic Supply: %s') % (auto_sup.name,),
                                        'origin': auto_sup.name,
                                        'date_planned': newdate.strftime('%Y-%m-%d %H:%M:%S'),
                                        'product_id': product_id.id,
                                        'product_qty': qty,
                                        'product_uom': product_uom,
                                        'location_id': location_id,
                                        'procure_method': 'make_to_order',
                })
            wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)
            wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_check', cr)
            auto_sup_obj.write(cr, uid, [auto_sup.id], {'procurement_id': proc_id}, context=context)
            
            # Fill the cache
            # TODO : To confirm by Magali, cache system is very strange
            # @JF : do not integrate this if a TODO is present in the previous line, please tell QT
            cache.get(location_id).append(product_id.id)
        
        return proc_id
        
procurement_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
