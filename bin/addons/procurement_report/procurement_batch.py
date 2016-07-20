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

import time

class procurement_batch_cron(osv.osv):
    _name = 'procurement.batch.cron'
#    _inherit = 'ir.cron'
    
    _columns = {
        'name': fields.char(size=64, string='Name', required=True),
        'active': fields.boolean('Active'),
        'type': fields.selection([('standard', 'POs creation Batch (from orders)'), ('rules', 'POs creation Batch (replenishment rules)')], string='Type', required=True),
        'request_ids': fields.one2many('res.request', 'batch_id', string='Associated Requests', readonly=True),
        'cron_ids': fields.one2many('ir.cron', 'batch_id', string='Associated Cron tasks'),
        'last_run_on': fields.datetime('Last run on', readonly=True),
        'interval_number': fields.integer('Interval Number',help="Repeat every x."),
        'interval_type': fields.selection( [('minutes', 'Minutes'),
            ('hours', 'Hours'), ('work_days','Work Days'), ('days', 'Days'),('weeks', 'Weeks'), ('months', 'Months')], 'Interval Unit'),
        'nextcall' : fields.datetime('Next Execution Date', required=True, help="Next planned execution date for this scheduler"),
    }

    _defaults = {
        'nextcall' : lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'interval_number' : lambda *a: 1,
        'interval_type' : lambda *a: 'weeks',
        'active' : lambda *a: 1, 
    }
    
    _constraints = [
    ]

    def open_request_view(self, cr, uid, ids, context=None):
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'procurement_report', 'batch_requests_view')[1]
        return {'type': 'ir.actions.act_window',
                'res_model': 'procurement.batch.cron',
                'res_id': ids[0],
                'view_id': [view_id],
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new'}
    
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
                'doall': False,
                'numbercall': -1,
                'batch_id': int(batch_id),
                'model': 'procurement.order',
                'args': '(False, %s)' % batch_id}
        
        if vals.get('type') == 'standard':
            # Create a cron task for the standard batch
            data.update({'function': 'procure_confirm',
                         'args': '(False, False, %s)' % batch_id,
                         'name': '%s - Run mrp scheduler' % vals.get('name', 'Run mrp scheduler')})
            cron_obj.create(cr, uid, data, context=context)
        else:
            # Create a cron for order cycle
            data.update({'function': 'run_automatic_cycle',
                         'name': '%s - Run automatic cycle' % vals.get('name', 'Run automatic cycle')})
            cron_obj.create(cr, uid, data, context=context)
            
            # Create a cron for auto supply
            data.update({'function': 'run_automatic_supply',
                         'name': '%s - Run automatic supply' % vals.get('name', 'Run automatic supply')})
            cron_obj.create(cr, uid, data, context=context)
            
            # Create a cron for threshold values
            data.update({'function': 'run_threshold_value',
                         'name': '%s - Run threshold value' % vals.get('name', 'Run threshold value')})
            cron_obj.create(cr, uid, data, context=context)
            
            # Create a cron for min/max rules
            data.update({'function': 'procure_orderpoint_confirm',
                         'args': '(False, False, %s)' % batch_id,
                         'name': '%s - Run Min/Max rules' % vals.get('name', 'Run Min/Max rules')})
            cron_obj.create(cr, uid, data, context=context)
        
    def create(self, cr, uid, vals, context=None):
        '''
        Create the associated cron tasks according to parameters
        '''
        vals.update({'args': '()'})
        # Get the id of the new batch
        batch_id = super(procurement_batch_cron, self).create(cr, uid, vals, context=context)
        
        self._create_associated_cron(cr, uid, batch_id, vals, context=context)
            
        return batch_id
    

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Set batch modifications on associated cron tasks 
        '''
        cron_obj = self.pool.get('ir.cron')
        
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        if vals is None:
            vals = {}

        cron_vals = vals.copy()
        if cron_vals.get('last_run_on'):
            del cron_vals['last_run_on']

        if cron_vals:
            for batch in self.browse(cr, uid, ids, context=context):
                if vals.get('type') and vals.get('type') != batch.type:
                    for cron in batch.cron_ids:
                        cron_obj.unlink(cr, uid, cron.id, context=context)
                    self._create_associated_cron(cr, uid, batch.id, vals, context=context)
                else:
                    for cron in batch.cron_ids:
                         if 'name' in vals:
                            vals.pop('name')
                         cron_obj.write(cr, uid, cron.id, vals, context=context)
                    
        return super(procurement_batch_cron, self).write(cr, uid, ids, vals, context=context)


    def read(self, cr, uid, ids, fields_to_read=None, context=None, load='_classic_read'):
        if not fields_to_read:
            fields_to_read = []

        res = super(procurement_batch_cron, self).read(cr, uid, ids, fields_to_read, context=context)

        if 'nextcall' in fields_to_read:
            for data in ([res] if isinstance(res, dict) else res):
                cron_ids = self.pool.get('ir.cron').search(cr, uid, [('batch_id', '=', data['id'])])
                if cron_ids:
                    nextcall = self.pool.get('ir.cron').browse(cr, uid, cron_ids[0]).nextcall
                    data.update({'nextcall': nextcall})

        return res
    
procurement_batch_cron()


class procurement_order(osv.osv):
    _name = 'procurement.order'
    _inherit = 'procurement.order'
    
    def procure_confirm(self, cr, uid, ids=None, use_new_cursor=False, batch_id=False, context=None):
        if not context:
            context = {}
        ctx = context.copy()
        ctx.update({'batch_id': batch_id})
        return self._procure_confirm(cr, uid, ids, use_new_cursor, context=ctx)
    
    def procure_orderpoint_confirm(self, cr, uid, automatic=False, use_new_cursor=False, \
                                    batch_id=False, context=None, user_id=False):
        if not context:
            context = {}
        ctx = context.copy()
        ctx.update({'batch_id': batch_id})
        return self._procure_orderpoint_confirm(cr, uid, automatic, use_new_cursor, context=ctx, user_id=user_id)
    
    def _hook_request_vals(self, cr, uid, *args, **kwargs):
        '''
        Add the batch_id in request
        '''
        request_obj = self.pool.get('res.request')
        res = super(procurement_order, self)._hook_request_vals(cr, uid, *args, **kwargs)
        if 'context' in kwargs:
            batch_id = kwargs['context'].get('batch_id', False)
            res.update({'batch_id': batch_id})
            
            # Remove the link between batch and old requests
            if batch_id:
                self.pool.get('procurement.batch.cron').write(cr, uid, batch_id, {'last_run_on': time.strftime('%Y-%m-%d %H:%M:%S')})
                old_request = request_obj.search(cr, uid, [('batch_id', '=', batch_id), ('name', '=', res.get('name', 'Procurement Processing Report.'))])
                request_obj.write(cr, uid, old_request, {'batch_id': False})
        return res
    
    def _hook_add_purchase_created(self, cr, uid, *args, **kwargs):
        '''
        Returns the created docs in report
        '''
        if not 'purchase_ids' in kwargs:
            return ''
        else:
            created_doc = '''################################
Created documents : \n'''
            for proc in self.browse(cr, uid, kwargs['purchase_ids']):
                created_doc += "    * %s => %s \n" % (proc.name, proc.purchase_id.name)
                
            return created_doc
        return ''
    
procurement_order()


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
