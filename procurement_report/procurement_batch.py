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
        'cycle_interval_number': fields.integer('Interval Number',help="Repeat every x."),
        'cycle_interval_type': fields.selection( [('minutes', 'Minutes'),
            ('hours', 'Hours'), ('work_days','Work Days'), ('days', 'Days'),('weeks', 'Weeks'), ('months', 'Months')], 'Interval Unit'),
        'cycle_nextcall' : fields.datetime('Next Execution Date', required=True, help="Next planned execution date for this scheduler"),
        'cycle_active': fields.boolean('Active'),
        'auto_interval_number': fields.integer('Interval Number',help="Repeat every x."),
        'auto_interval_type': fields.selection( [('minutes', 'Minutes'),
            ('hours', 'Hours'), ('work_days','Work Days'), ('days', 'Days'),('weeks', 'Weeks'), ('months', 'Months')], 'Interval Unit'),
        'auto_nextcall' : fields.datetime('Next Execution Date', required=True, help="Next planned execution date for this scheduler"),
        'auto_active': fields.boolean('Active'),
        'threshold_interval_number': fields.integer('Interval Number',help="Repeat every x."),
        'threshold_interval_type': fields.selection( [('minutes', 'Minutes'),
            ('hours', 'Hours'), ('work_days','Work Days'), ('days', 'Days'),('weeks', 'Weeks'), ('months', 'Months')], 'Interval Unit'),
        'threshold_nextcall' : fields.datetime('Next Execution Date', required=True, help="Next planned execution date for this scheduler"),
        'threshold_active': fields.boolean('Active'),
    }
    
    _defaults = {
        'name': lambda *a: 'Standard configuration',
    }
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Get the current values
        '''
        model_obj = self.pool.get('ir.model.data')
        cron_obj = self.pool.get('ir.cron')
        
        standard = model_obj.get_object_reference(cr, uid, 'procurement', 'ir_cron_scheduler_action')[1]
        cycle = model_obj.get_object_reference(cr, uid, 'procurement_cycle', 'ir_cron_proc_cycle_action')[1]
        auto = model_obj.get_object_reference(cr, uid, 'procurement_auto', 'ir_cron_auto_supply_action')[1]
        threshold = model_obj.get_object_reference(cr, uid, 'threshold_value', 'ir_cron_threshold_action')[1]
        
        standard_values = cron_obj.read(cr, uid, standard, ['interval_number', 'interval_type', 'nextcall', 'active'], context=context)
        cycle_values = cron_obj.read(cr, uid, cycle, ['interval_number', 'interval_type', 'nextcall', 'active'], context=context)
        auto_values = cron_obj.read(cr, uid, auto, ['interval_number', 'interval_type', 'nextcall', 'active'], context=context)
        threshold_values = cron_obj.read(cr, uid, threshold, ['interval_number', 'interval_type', 'nextcall', 'active'], context=context)
        
        res = super(procurement_batch_cron, self).default_get(cr, uid, fields, context=context)
        
        res.update({'interval_number': standard_values['interval_number'],
                    'interval_type': standard_values['interval_type'],
                    'nextcall': standard_values['nextcall'],
                    'active': standard_values['active'],
                    'cycle_interval_number': cycle_values['interval_number'],
                    'cycle_interval_type': cycle_values['interval_type'],
                    'cycle_nextcall': cycle_values['nextcall'],
                    'cycle_active': cycle_values['active'],
                    'auto_interval_number': auto_values['interval_number'],
                    'auto_interval_type': auto_values['interval_type'],
                    'auto_nextcall': auto_values['nextcall'],
                    'auto_active': auto_values['active'],
                    'threshold_interval_number': threshold_values['interval_number'],
                    'threshold_interval_type': threshold_values['interval_type'],
                    'threshold_nextcall': threshold_values['nextcall'],
                    'threshold_active': threshold_values['active'],})
        
        return res
        
    
    def update_cron_tasks(self, cr, uid, ids, context=None):
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
            cron_obj.write(cr, uid, [standard], {'active': value.active,
                                                                         'interval_number': value.interval_number,
                                                                         'interval_type': value.interval_type,
                                                                         'active': value.active,
                                                                         'nextcall': value.nextcall}, context=context)
            cron_obj.write(cr, uid, [cycle], {'active': value.active,
                                                                         'interval_number': value.cycle_interval_number,
                                                                         'interval_type': value.cycle_interval_type,
                                                                         'active': value.cycle_active,
                                                                         'nextcall': value.cycle_nextcall}, context=context)
            cron_obj.write(cr, uid, [auto], {'active': value.active,
                                                                         'interval_number': value.auto_interval_number,
                                                                         'interval_type': value.auto_interval_type,
                                                                         'active': value.auto_active,
                                                                         'nextcall': value.auto_nextcall}, context=context)
            cron_obj.write(cr, uid, [threshold], {'active': value.active,
                                                                         'interval_number': value.threshold_interval_number,
                                                                         'interval_type': value.threshold_interval_type,
                                                                         'active': value.threshold_active,
                                                                         'nextcall': value.threshold_nextcall}, context=context)
        
        return {'type': 'ir.actions.act_window_close'}
    
procurement_batch_cron()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
