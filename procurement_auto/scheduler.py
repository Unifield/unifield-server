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
import time
from datetime import datetime

from tools.translate import _


# Cache for product/location
cache = {}

class procurement_order(osv.osv):
    _name = 'procurement.order'
    _inherit = 'procurement.order'
    
    def run_automatic_supply(self, cr, uid, context={}):
        '''
        Create procurement on fixed date
        '''
        request_obj = self.pool.get('res.request')
        auto_sup_obj = self.pool.get('stock.warehouse.automatic.supply')
        auto_sup_ids = auto_sup_obj.search(cr, uid, [('next_date', '=', datetime.today().strftime('%Y-%m-%d')), ('product_id', '=', False)])
        
        
        created_proc = []
        report = []
        report_except = 0
        
        # We start with only category Automatic Supply
        for auto_sup in auto_sup_obj.browse(cr, uid, auto_sup_ids):
            # We define the replenish location
            location_id = False
            if not auto_sup.location_id or not auto_sup.location_id.id:
                location_id = auto_sup.warehouse_id.lot_input_id.id
            else:
                location_id = autop_sup.location_id.id
                
            for line in auto_sup.line_ids:
                proc_id = self.create_proc_order(cr, uid, auto_sup, line.product_id,
                                                 line.product_uom_id.id, line.product_qty,
                                                 location_id, context=context)
                if proc_id:
                    created_proc.append(proc_id)
        
        # Next, for one product automatic supply
        auto_sup_ids = auto_sup_obj.search(cr, uid, [('next_date', '=', datetime.today().strftime('%Y-%m-%d')), ('product_id', '!=', False)])
        for auto_sup in auto_sup_obj.browse(cr, uid, auto_sup_ids):
            # We define the replenish location
            location_id = False
            if not auto_sup.location_id or not auto_sup.location_id.id:
                location_id = auto_sup.warehouse_id.lot_input_id.id
            else:
                location_id = autop_sup.location_id.id
                
            proc_id = self.create_proc_order(cr, uid, auto_sup, product_id, product_uom_id.id, product_qty, location_id, context)
                    
        for proc in auto_sup_obj.browse(cr, uid, created_proc):
            if proc_id.state == 'exception':
                report.append('PROC %d: from stock - %3.2f %-5s - %s' % \
                               (proc.id, proc.product_qty, proc.product_uom.name,
                                proc.product_id.name,))
                report_except += 1
                
        summary = '''Here is the procurement scheduling report for Automatic Supplies

        Start Time: %s
        End Time: %s
        Total Procurements processed: %d
        Procurements with exceptions: %d

        Exceptions:\n'''% (start_date, end_date, len(created_proc), report_except)
        summary += '\n'.join(report)
        request.create(cr, uid,
                {'name': "Procurement Processing Report.",
                 'act_from': uid,
                 'act_to': uid,
                 'body': summary,
                })
            
        return {}
    
    def create_proc_order(self, cr, uid, auto_sup, product_id, product_uom, qty, location_id, context={}):
        '''
        Creates a procurement order for a product and a location
        '''
        proc_obj = self.pool.get('procurement.order')
        auto_sup_obj = self.pool.get('stock.warehouse.automatic.supply')
        wf_service = netsvc.LocalService("workflow")
        report = []
        # Enter the stock location in cache to know which products has been already replenish for this location
        if not cache.get(location_id, False):
            cache.update({location_id: []})
            
        if product_id.id not in cache.get(location_id):
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
            cache.get(location_id).append(product_id.id)
        
        return proc_id
        
procurement_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: