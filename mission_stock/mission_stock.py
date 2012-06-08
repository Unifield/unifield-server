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

import pooler
import time
import threading


class stock_mission_report(osv.osv):
    _name = 'stock.mission.report'
    _description = 'Mission stock report'
    
    def _get_local_report(self, cr, uid, ids, field_name, args, context=None):
        '''
        Check if the mission stock report is a local report or not
        '''
        res = {}
        
        local_instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.id
        
        for report in self.browse(cr, uid, ids, context=context):
            res[report.id] = False
            if not report.full_view and report.instance_id.id == local_instance_id:
                res[report.id] = True
                
        return res
    
    def _src_local_report(self, cr, uid, obj, name, args, context=None):
        '''
        Returns the local or not report mission according to args
        '''
        res = []
        
        local_instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.id
        
        for arg in args:
            if arg[0] == 'local_report':
                if (arg[1] == '=' and arg[2] in ('True', 'true', 't', 1)) or \
                    (arg[1] in ('!=', '<>') and arg[2] in ('False', 'false', 'f', 0)):
                    res.append(('instance_id', '=', local_instance_id))
                elif (arg[1] == '=' and arg[2] in ('False', 'false', 'f', 0)) or \
                    (arg[1] in ('!=', '<>') and arg[2] in ('True', 'true', 't', 1)):                     
                    res.append(('instance_id', '!=', local_instance_id))
                else:
                    raise osv.except_osv(_('Error', _('Bad operator')))
                
        return res
    
    _columns = {
        'name': fields.char(size=128, string='Name', required=True),
        'instance_id': fields.many2one('msf.instance', string='Instance', required=True),
        'full_view': fields.boolean(string='Is a full view report ?'),
        'local_report': fields.function(_get_local_report, fnct_search=_src_local_report, 
                                        type='boolean', method=True, store=False,
                                        string='Is a local report ?', help='If the report is a local report, it will be updated periodically'),
        'report_line': fields.one2many('stock.mission.report.line', 'mission_report_id', string='Lines'),
        'last_update': fields.datetime(string='Last update'),
    }
    
    _defaults = {
        'full_view': lambda *a: False,
    }
    
    def create(self, cr, uid, vals, context=None):
        '''
        Create lines at report creation
        '''
        res = super(stock_mission_report, self).create(cr, uid, vals, context=context)
        
        local_instance_id = self.pool.ges('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.id
        
        # Not update lines for full view or non local reports
        if (vals.get('instance_id', False) and vals['instance_id'] != local_instance_id) or not vals.get('full_view', False):
            self.update(cr, uid, res, context=context)
        
        return res
    
    def background_update(self, cr, uid, ids, context=None):
        """
        Run the update of local stock report in background 
        """
        threaded_calculation = threading.Thread(target=self.update, args=(cr, uid, ids, context))
        threaded_calculation.start()
        return {'type': 'ir.actions.act_window_close'}
    
    def update(self, cr, uid, ids, context=None):
        '''
        Create lines if new products exist or update the existing lines
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        cr = pooler.get_db(cr.dbname).cursor()
        
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
        
            # Update the update date on report
            self.write(cr, uid, [report.id], {'last_update': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
                
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
    
    def _get_request(self, cr, location_ids, product_id):
        '''
        Build the SQL request and give the result
        '''
        if isinstance(location_ids, (int, long)):
            location_ids = [location_ids]
            
        if not isinstance(product_id, (int, long)):
            raise osv.except_osv(_('Error'), _('You can\'t build the request for some products !'))
            
        where_location = ','.join(str(x) for x in location_ids)
            
        request = '''SELECT sum(qty) 
                 FROM 
                     stock_report_prodlots 
                 WHERE 
                    location_id in (%s)
                    AND
                    product_id = %s
                 GROUP BY product_id''' % (where_location, product_id)
                 
        cr.execute(request)
        
        return cr.fetchone()
    
    def update(self, cr, uid, ids, context=None):
        '''
        Update line values
        '''
        if not context:
            context = {}
            
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        location_obj = self.pool.get('stock.location')
        data_obj = self.pool.get('ir.model.data')
        
        stock_location_id = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
        
        # Search considered SLocation
        internal_loc = location_obj.search(cr, uid, [('usage', '=', 'internal')], context=context)
        stock_loc = location_obj.search(cr, uid, [('location_id', 'child_of', stock_location_id), ('central_location_ok', '=', False)], context=context)
        central_loc = location_obj.search(cr, uid, [('central_location_ok', '=', True)], context=context)
        cross_loc = location_obj.search(cr, uid, [('cross_docking_location_ok', '=', True)], context=context)
        cu_loc = location_obj.search(cr, uid, [('location_category', '=', 'consumption_unit')], context=context)
        secondary_location_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_intermediate_client_view')[1]
        
        for line in self.browse(cr, uid, ids, context=context):
            # Internal locations
            if internal_loc:
                internal_qty = self._get_request(cr, internal_loc, line.product_id.id)
                if internal_qty:
                    internal_qty = internal_qty[0]
            else:
                internal_qty = 0.00
            
            # Stock locations
            if stock_loc:
                stock_qty = self._get_request(cr, stock_loc, line.product_id.id)
                if stock_qty:
                    stock_qty = stock_qty[0]                                                           
            else:
                stock_qty = 0.00
            
            # Central stock locations
            if central_loc:
                central_loc = location_obj.search(cr, uid, [('location_id', 'child_of', central_loc)], context=context)
                central_qty = self._get_request(cr, central_loc, line.product_id.id)
                if central_qty:
                    central_qty = central_qty[0]
            else:
                central_qty = 0.00

            # Cross-docking locations
            if cross_loc:
                cross_loc = location_obj.search(cr, uid, [('location_id', 'child_of', cross_loc)], context=context)
                cross_qty = self._get_request(cr, cross_loc, line.product_id.id)
                if cross_qty:
                    cross_qty = cross_qty[0]
            else:
                cross_qty = 0.00

            # Secondary stock locations
            if secondary_location_id != False:
                secondary_qty = self._get_request(cr, secondary_location_id, line.product_id.id)
                if secondary_qty:
                    secondary_qty = secondary_qty[0]
            else:
                secondary_qty = 0.00
                
            # Consumption unit locations
            if cu_loc:
                cu_loc = location_obj.search(cr, uid, [('location_id', 'child_of', cu_loc)], context=context)
                cu_qty = self._get_request(cr, cu_loc, line.product_id.id)
                if cu_qty:
                    cu_qty = cu_qty[0]
            else:
                cu_qty = 0.00
            
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
        
        where = 'WHERE l.product_id in (%s)' % ','.join(str(x) for x in ids)
        report = self.pool.get('stock.mission.report').browse(cr, uid, report_id[0], context=context)
        if not report.full_view:
            where = 'AND l.mission_report_id = %s' % report.id    
        
        request = '''select l.product_id,
                            pt.standard_price,
                            sum(l.internal_qty), 
                            sum(l.stock_qty), 
                            sum(l.central_qty), 
                            sum(l.cross_qty), 
                            sum(l.secondary_qty), 
                            sum(l.cu_qty) 
                     from stock_mission_report_line l 
                         left join product_product pp on pp.id = l.product_id
                         left join product_template pt on pp.product_tmpl_id = pt.id
                     %s 
                     group by l.product_id, pt.standard_price
                     order by product_id''' % (where,)
                     
        cr.execute(request)
        for line in cr.fetchall():
            res[line[0]] = {'internal_qty': line[2],
                            'internal_val': line[2]*line[1],
                            'stock_qty': line[3],
                            'stock_val': line[3]*line[1],
                            'central_qty': line[4],
                            'central_val': line[4]*line[1],
                            'cross_qty': line[5],
                            'cross_val': line[5]*line[1],
                            'secondary_qty': line[6],
                            'secondary_val': line[6]*line[1],
                            'cu_qty': line[7],
                            'cu_val': line[7]*line[1],
                            }
        
        return res
                
    
    _columns = {
        'internal_qty': fields.function(_get_report_qty, method=True, type='float', string='Internal Qty.', store=False, multi='mission_report'),
        'internal_val': fields.function(_get_report_qty, method=True, type='float', string='Internal Val.', store=False, multi='mission_report'),
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