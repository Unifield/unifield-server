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
from osv import fields


class procurement_batch_cron(osv.osv):
    _name = 'procurement.batch.cron'
    _inherit = 'ir.cron'
    
    _columns = {
        'name': fields.char(size=64, string='Name'),
    }
    
    _defaults = {
        'name': lambda *a: 'Standard configuration',
    }
    
    def update_cron_tasks(self, cr, uid, ids, context={}):
        '''
        Update all scheduler cron tasks
        '''
        model_obj = self.pool.get('ir.model.data')
        cron_obj = self.pool.get('ir.cron')
        
        standard = model_obj.get_object_reference(cr, uid, 'procurement', 'ir_cron_scheduler_action')[1]
        cycle = model_obj.get_object_reference(cr, uid, 'procurement_cycle', 'ir_cron_proc_cycle_action')[1]
        auto = model_obj.get_object_reference(cr, uid, 'procurement_auto', 'ir_cron_auto_supply_action')[1]
        threshold = model_obj.get_object_reference(cr, uid, 'threshold_value', 'ir_cron_threshold_action')[1]
        
        for value in self.browse(cr, uid, ids, context=context):
            cron_obj.write(cr, uid, [standard, cycle, auto, threshold], {'active': value.active,
                                                                         'interval_number': value.interval_number,
                                                                         'interval_type': value.interval_type,
                                                                         'nextcall': value.nextcall}, context=context)
        
        return {'type': 'ir.actions.act_window_close'}
    
procurement_batch_cron()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
