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
        'type': fields.selection([('standard', 'From orders'), ('rules', 'Replenishment rules')], string='Type', required=True),
        'request_ids': fields.one2many('res.request', 'batch_id', string='Associated Requests'),
        'cron_ids': fields.one2many('ir.cron', 'batch_id', string='Associated Cron tasks'),
    }
    
    def _create_associated_cron(self, cr, uid, batch_id, vals, context=None):
        '''
        Create cron according to type
        '''
        cron_obj = self.pool.get('ir.cron')
        
        data = {'active': vals.get('active', True),
                'user_id': uid,
                'interval_number': vals.get('interval_number'),
                'interval_type': vals.get('interval_type'),
                'nextcall': vals.get('nextcall'),
                'batch_id': int(batch_id),
                'model': 'procurement.order',
                'args': '(False, %s)' % batch_id}
        
        if vals.get('type') == 'standard':
            # Create a cron task for the standard batch
            data.update({'function': 'run_scheduler',
                         'name': vals.get('name', 'Run mrp scheduler')})
            cron_obj.create(cr, uid, data, context=context)
        else:
            # Create a cron for order cycle
            data.update({'function': 'run_automatic_cycle',
                         'name': vals.get('name', 'Run automatic cycle')})
            cron_obj.create(cr, uid, data, context=context)
            
            # Create a cron for auto supply
            data.update({'function': 'run_automatic_supply',
                         'name': vals.get('name', 'Run automatic supply')})
            cron_obj.create(cr, uid, data, context=context)
            
            # Create a cron for threshold values
            data.update({'function': 'run_threshold_value',
                         'name': vals.get('name', 'Run threshold value')})
            cron_obj.create(cr, uid, data, context=context)
        
    def create(self, cr, uid, vals, context=None):
        '''
        Create the associated cron tasks according to parameters
        '''
        # Get the id of the new batch
        batch_id = super(procurement_batch_cron, self).create(cr, uid, vals, context=context)
        
        self._create_associated_cron(cr, uid, batch_id, vals, context=context)
            
        return batch_id
    

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Set batch modifications on associated cron tasks 
        '''
        cron_obj = self.pool.get('ir.cron')
        
        for batch in self.browse(cr, uid, ids, context=context):
            if vals.get('type') and vals.get('type') != batch.type:
                for cron in batch.cron_ids:
                    cron_obj.unlink(cr, uid, cron.id, context=context)
                self._create_associated_cron(cr, uid, batch.id, vals, context=context)
            else:
                for cron in batch.cron_ids:
                    cron_obj.write(cr, uid, vals, context=context)
                    
        return super(procurement_batch_cron, self).write(cr, uid, ids, vals, context=context)
    
procurement_batch_cron()


class ir_cron(osv.osv):
    _name = 'ir.cron'
    _inherit = 'ir.cron'
    
    _columns = {
        'batch_id': fields.many2one('procurement.batch.cron', string='Batch', ondelete='cascade'),
    }
    
ir_cron()


class res_request(osv.osv):
    _name = 'res.request'
    _inherit = 'res.request'
    
    _columns = {
        'batch_id': fields.many2one('procurement.batch.cron', string='Batch', ondelete='cascade'),
    }
    
res_request() 

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
