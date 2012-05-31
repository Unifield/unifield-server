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


class stock_mission_report(osv.osv):
    _name = 'stock.mission.report'
    _description = 'Mission stock report'
    
    _columns = {
        'name': fields.char(size=128, string='Name', required=True),
        'full_view': fields.boolean(string='Is a full view report ?'),
        'local_report': fields.boolean(string='Is a local report ?', help='If the report is a local report, it wiil be updated periodically'),
        'report_line': fields.one2many('stock.mission.report.line', 'mission_report_id', string='Lines'),
    }
    
    _defaults = {
        'full_view': lambda *a: False,
        'local_report': lambda *a: False,
    }
    
    def create(self, cr, uid, vals, context=None):
        '''
        Create lines at report creation
        '''
        res = super(stock_mission_report, self).create(cr, uid, vals, context=context)
        
        # Not update lines for full view or non local reports
        if vals.get('local_report', False) or not vals.get('full_view', False):
            self.update(cr, uid, res, context=context)
        
        return res
    
    def update(self, cr, uid, ids, context=None):
        '''
        Create lines if new products exist or update the existing lines
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        line_obj = self.pool.get('stock.mission.report.line')
        
        product_ids = self.pool.get('product.product').search(cr, uid, [], context=context)
        line_ids = []
        
        # Check in each report if new products are in the database and not in the report
        for report in self.browse(cr, uid, ids, context=context):
            # Don't update lines for full view or non local reports
            if not report.local_report or report.full_view:
                continue
            
            product_in_report = []
            if report.report_line:
                for line in report.report_line:
                    line_ids.append(line.id)
                    product_in_report.append(line.product_id.id)
        
            # Difference between product list and products in report
            product_diff = filter(lambda x:x not in product_in_report, product_ids)
            for product in product_diff:
                line_ids.append(line_obj.create(cr, uid, {'product_id': product, 'mission_report_id': report.id}, context=context))
                
        # Update all lines
        line_obj.update(cr, uid, line_ids, context=context)
        
        return True
                
    
stock_mission_report()


class stock_mission_report_line(osv.osv):
    _name = 'stock.mission.report.line'
    _description = 'Mission stock report line'
    
    _columns = {
        'product_id': fields.many2one('product.product', string='Name', required=True),
        'mission_report_id': fields.many2one('stock.mission.report', string='Mission Report', required=True),
        'internal_qty': fields.float(digits=(16,2), string='Internal Qty.'),
        'stock_qty': fields.float(digits=(16,2), string='Stock Qty.'),
        'central_qty': fields.float(digits=(16,2), string='Central Stock Qty.'),
        'cross_qty': fields.float(digits=(16,3), string='Cross-docking Qty.'),
        'secondary_qty': fields.float(digits=(16,3), string='Secondary Stock Qty.'),
        'cu_qty': fields.float(digits=(16,3), string='Internal Cons. Unit Qty.'),
    }
    
    def update(self, cr, uid, ids, context=None):
        '''
        Update line values
        '''
        if not context:
            context = {}
            
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        location_obj = self.pool.get('stock.location')
        product_obj = self.pool.get('product.product')
        data_obj = self.pool.get('ir.model.data')
        
        stock_location_id = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
        
        # Search considered SLocation
        internal_loc = location_obj.search(cr, uid, [('usage', '=', 'internal')], context=context)
        stock_loc = location_obj.search(cr, uid, [('location_id', 'child_of', stock_location_id), ('central_location_ok', '=', False)], context=context)
        central_loc = location_obj.search(cr, uid, [('central_location_ok', '=', True)], context=context)
        cross_loc = location_obj.search(cr, uid, [('cross_docking_location_ok', '=', True)], context=context)
        cu_loc = location_obj.search(cr, uid, [('location_category', '=', 'consumption_unit')], context=context)
        secondary_location_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_intermediate_client_view')
        
        for line in self.browse(cr, uid, ids, context=context):
            internal_qty = product_obj.get_product_available(cr, uid, [line.product_id.id], context={'location': internal_loc, 
                                                                                                   'compute_child': False,
                                                                                                   'states': ('done',), 
                                                                                                   'what': ('in', 'out')})[line.product_id.id]
                                                                                                   
            stock_qty = product_obj.get_product_available(cr, uid, [line.product_id.id], context={'location': stock_loc, 
                                                                                                   'compute_child': False,
                                                                                                   'states': ('done',), 
                                                                                                   'what': ('in', 'out')})[line.product_id.id]
            central_qty = product_obj.get_product_available(cr, uid, [line.product_id.id], context={'location': central_loc, 
                                                                                                   'compute_child': True,
                                                                                                   'states': ('done',), 
                                                                                                   'what': ('in', 'out')})[line.product_id.id]
            cross_qty = product_obj.get_product_available(cr, uid, [line.product_id.id], context={'location': cross_loc, 
                                                                                                   'compute_child': True,
                                                                                                   'states': ('done',), 
                                                                                                   'what': ('in', 'out')})[line.product_id.id]
            secondary_qty = product_obj.get_product_available(cr, uid, [line.product_id.id], context={'location': secondary_location_id, 
                                                                                                   'compute_child': False,
                                                                                                   'states': ('done',), 
                                                                                                   'what': ('in', 'out')})[line.product_id.id]
            cu_qty = product_obj.get_product_available(cr, uid, [line.product_id.id], context={'location': cu_loc, 
                                                                                                   'compute_child': True,
                                                                                                   'states': ('done',), 
                                                                                                   'what': ('in', 'out')})[line.product_id.id]
            
            self.write(cr, uid, [line.id], {'internal_qty': internal_qty,
                                            'stock_qty': stock_qty,
                                            'central_qty': central_qty,
                                            'cross_qty': cross_qty,
                                            'secondary_qty': secondary_qty,
                                            'cu_qty': cu_qty}, context=context)
            
        return True
    
stock_mission_report_line()


class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'
    
    def _get_report_qty(self, cr, uid, ids, field_name, args, context=None):
        '''
        Get the values for the mission report in context
        '''
        if not context:
            context = {}
            
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        res = {}
        
        report_id = self.pool.get('stock.mission.report').search(cr, uid, [('id', '=', context.get('mission_report_id'))])
        if not context.get('mission_report_id', False) or not report_id:
            raise osv.except_osv(_('Error'), _('No mission stock report found !'))
        
        report = self.pool.get('stock.mission.report').browse(cr, uid, report_id[0], context=context)            
        
        for product in ids:
            res[product] = {'internal_qty': 0.00,
                            'internal_val': 0.00,
                            'stock_qty': 0.00,
                            'stock_val': 0.00,
                            'central_qty': 0.00,
                            'central_val': 0.00,
                            'cross_qty': 0.00,
                            'cross_val': 0.00,
                            'secondary_qty': 0.00,
                            'secondary_val': 0.00,
                            'cu_qty': 0.00,
                            'cu_val': 0.00,}
            
        for line in report.report_line:
            res[line.product_id.id] = {'internal_qty': line.internal_qty,
                                       'internal_val': line.internal_qty*line.product_id.standard_price,
                                       'stock_qty': line.stock_qty,
                                       'stock_val': line.stock_qty*line.product_id.standard_price,
                                       'central_qty': line.central_qty,
                                       'central_val': line.central_qty*line.product_id.standard_price,
                                       'cross_qty': line.cross_qty,
                                       'cross_val': line.cross_qty*line.product_id.standard_price,
                                       'secondary_qty': line.secondary_qty,
                                       'secondary_val': line.secondary_qty*line.product_id.standard_price,
                                       'cu_qty': line.cu_qty,
                                       'cu_val': line.cu_qty*line.product_id.standard_price,
                                       }
                
        return res
                
    
    _columns = {
        'internal_qty': fields.function(_get_report_qty, method=True, type='float', string='Internal Qty.', store=False, multi='mission_report'),
        'internal_val': fields.function(_get_report_qty, method=True, type='float', string='Internal Vàal.', store=False, multi='mission_report'),
        'stock_qty': fields.function(_get_report_qty, method=True, type='float', string='Stock Qty.', store=False, multi='mission_report'),
        'stock_val': fields.function(_get_report_qty, method=True, type='float', string='Stock Val.', store=False, multi='mission_report'),
        'central_qty': fields.function(_get_report_qty, method=True, type='float', string='Central Stock Qty.', store=False, multi='mission_report'),
        'central_val': fields.function(_get_report_qty, method=True, type='float', string='Central Stock Val.', store=False, multi='mission_report'),
        'cross_qty': fields.function(_get_report_qty, method=True, type='float', string='Cross-docking Qty.', store=False, multi='mission_report'),
        'cross_val': fields.function(_get_report_qty, method=True, type='float', string='Cross-docking Val.', store=False, multi='mission_report'),
        'secondary_qty': fields.function(_get_report_qty, method=True, type='float', string='Secondary Stock Qty.', store=False, multi='mission_report'),
        'secondary_val': fields.function(_get_report_qty, method=True, type='float', string='Secondary Stock Val.', store=False, multi='mission_report'),
        'cu_qty': fields.function(_get_report_qty, method=True, type='float', string='Internal Cons. Unit Qty.', store=False, multi='mission_report'),
        'cu_val': fields.function(_get_report_qty, method=True, type='float', string='Internal Cons. Unit Val.', store=False, multi='mission_report'),
    }
    
product_product()