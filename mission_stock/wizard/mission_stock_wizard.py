# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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


class mission_stock_wizard(osv.osv_memory):
    _name = 'mission.stock.wizard'
    
    _columns = {
        'report_id': fields.many2one('stock.mission.report', string='Report', required=True),
#        'with_valuation': fields.boolean(string='Display stock valuation ?'),
        'with_valuation': fields.selection([('true', 'Yes'), ('false', 'No')], string='Display stock valuation ?', 
                                           required=True),
        'last_update': fields.datetime(string='Last update', readonly=True),
    }
    
    _defaults = {
        'with_valuation': lambda *a: 'false',
    }
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Choose the first local report as default
        '''
        res = super(mission_stock_wizard, self).default_get(cr, uid, fields, context=context)

        instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
        if not instance_id:
            raise osv.except_osv(_('Error'), _('Mission stock report cannot be available if no instance was set on the company !'))
        
        local_id = self.pool.get('stock.mission.report').search(cr, uid, [('local_report', '=', True), ('full_view', '=', False)], context=context)
        if local_id:
            res['report_id'] = local_id[0]
            res['last_update'] = self.pool.get('stock.mission.report').browse(cr, uid, local_id[0], context=context).last_update            

        return res
    
    def report_change(self, cr, uid, ids, report_id, context=None):
        if isinstance(report_id, list):
            report_id = report_id[0]
            
        v = {}
        
        if report_id:
            report = self.pool.get('stock.mission.report').browse(cr, uid, report_id, context=context)
            v.update({'last_update': report.last_update})
        else:
            v.update({'last_update': False})
        
        return {'value': v}
    
    def open_products_view(self, cr, uid, ids, context=None):
        '''
        Open the product list with report information
        '''
        if isinstance(ids, list):
            ids = ids[0]
            
        if not context:
            context = {}
            
        wiz_id = self.browse(cr, uid, ids, context=context)
        c = context.copy()
        c.update({'mission_report_id': wiz_id.report_id.id, 'with_valuation': wiz_id.with_valuation == 'true' and True or False})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.mission.report.line',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'domain': [('mission_report_id', '=', wiz_id.report_id.id)],
                'context': c,
                'target': 'current'}
        
    def update(self, cr, uid, ids, context=None):
        ids = self.pool.get('stock.mission.report').search(cr, uid, [], context=context)
        return self.pool.get('stock.mission.report').background_update(cr, uid, ids)
        
mission_stock_wizard()
