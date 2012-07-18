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
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        res = {}
        
        local_instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.id
        
        for report in self.browse(cr, uid, ids, context=context):
            res[report.id] = False
            if report.instance_id.id == local_instance_id:
                res[report.id] = True
                
        return res
    
    def _src_local_report(self, cr, uid, obj, name, args, context=None):
        '''
        Returns the local or not report mission according to args
        '''
        res = []
        
        local_instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.id
        
        for arg in args:
            if len(arg) > 2 and arg[0] == 'local_report':
                if (arg[1] == '=' and arg[2] in ('True', 'true', 't', 1)) or \
                    (arg[1] in ('!=', '<>') and arg[2] in ('False', 'false', 'f', 0)):
                    res.append(('instance_id', '=', local_instance_id))
                elif (arg[1] == '=' and arg[2] in ('False', 'false', 'f', 0)) or \
                    (arg[1] in ('!=', '<>') and arg[2] in ('True', 'true', 't', 1)):
                    res.append(('instance_id', '!=', local_instance_id))
                else:
                    raise osv.except_osv(_('Error'), _('Bad operator'))
                
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
        
        local_instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.id
        
        # Not update lines for full view or non local reports
        if (vals.get('instance_id', False) and vals['instance_id'] != local_instance_id) or not vals.get('full_view', False):
            if not context.get('no_update', False):
                self.update(cr, uid, res, context=context)
        
        return res
    
    def background_update(self, cr, uid, ids, context=None):
        """
        Run the update of local stock report in background 
        """
        if not ids:
            ids = []
        
        threaded_calculation = threading.Thread(target=self.update, args=(cr, uid, ids, context))
        threaded_calculation.start()
        return {'type': 'ir.actions.act_window_close'}
    
    def update(self, cr, uid, ids=[], context=None):
        '''
        Create lines if new products exist or update the existing lines
        '''
        if not context:
            context = {}
            
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # Open a new cursor : Don't forget to close it at the end of method   
        cr = pooler.get_db(cr.dbname).cursor()
        
        line_obj = self.pool.get('stock.mission.report.line')
        
        product_ids = self.pool.get('product.product').search(cr, uid, [], context=context)
        report_ids = self.search(cr, uid, [('local_report', '=', True)], context=context)
        full_report_ids = self.search(cr, uid, [('full_view', '=', True)], context=context)
        instance_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        line_ids = []
        
        if not report_ids and context.get('update_mode', False) not in ('update', 'init') and instance_id:
            c = context.copy()
            c.update({'no_update': True})
            report_ids = [self.create(cr, uid, {'name': instance_id.name,
                                               'instance_id': instance_id.id,
                                               'full_view': False}, context=c)]

        if not full_report_ids and context.get('update_mode', False) not in ('update', 'init') and instance_id:
            c = context.copy()
            c.update({'no_update': True})
            full_report_ids = [self.create(cr, uid, {'name': 'Full view',
                                               'instance_id': instance_id.id,
                                               'full_view': True}, context=c)]

        if context.get('update_full_report'):
            report_ids = full_report_ids
            

        # Check in each report if new products are in the database and not in the report
        for report in self.browse(cr, uid, report_ids, context=context):
            # Don't update lines for full view or non local reports
            if not report.local_report:
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
               
        if context.get('update_full_report'):
            line_obj.update_full_view_line(cr, uid, line_ids, context=context)
        else:
            # Update all lines
            line_obj.update(cr, uid, line_ids, context=context)

        cr.commit()
        cr.close()
        
        # After update of all normal reports, update the full view report
        if not context.get('update_full_report'):
            c = context.copy()
            c.update({'update_full_report': True})
            self.update(cr, uid, [], context=c)

        return True
                
    
stock_mission_report()


class stock_mission_report_line(osv.osv):
    _name = 'stock.mission.report.line'
    _description = 'Mission stock report line'
    
    def _get_product_type_selection(self, cr, uid, context=None):
        return self.pool.get('product.template').PRODUCT_TYPE
    
    def _get_product_subtype_selection(self, cr, uid, context=None):
        return self.pool.get('product.template').PRODUCT_SUBTYPE
    
    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=num, context=context)
    
    def _get_nomen_s(self, cr, uid, ids, fields, *a, **b):
        value = {}
        for f in fields:
            value[f] = False

        ret = {}
        for id in ids:
            ret[id] = value
        return ret
    
    def _search_nomen_s(self, cr, uid, obj, name, args, context=None):
        # Some verifications
        if context is None:
            context = {}
            
        if not args:
            return []
        narg = []
        for arg in args:
            el = arg[0].split('_')
            el.pop()
            narg=[('_'.join(el), arg[1], arg[2])]
        
        return narg
    
    def _get_template(self, cr, uid, ids, context=None):
        return self.pool.get('stock.mission.report.line').search(cr, uid, [('product_id.product_tmpl_id', 'in', ids)], context=context)
    
    _columns = {
        'product_id': fields.many2one('product.product', string='Name', required=True),
        'default_code': fields.related('product_id', 'default_code', string='Reference', type='char'),
        'old_code': fields.related('product_id', 'old_code', string='Old Code', type='char'),
        'name': fields.related('product_id', 'name', string='Name', type='char'),
        'categ_id': fields.related('product_id', 'categ_id', string='Category', type='many2one', relation='product.category',
                                   store={'product.template': (_get_template, ['type'], 10)}),
        'type': fields.related('product_id', 'type', string='Type', type='selection', selection=_get_product_type_selection, 
                               store={'product.template': (_get_template, ['type'], 10)}),
        'subtype': fields.related('product_id', 'subtype', string='Subtype', type='selection', selection=_get_product_subtype_selection),
        # mandatory nomenclature levels
        'nomen_manda_0': fields.related('product_id', 'nomen_manda_0', type='many2one', relation='product.nomenclature', string='Main Type'),
        'nomen_manda_1': fields.related('product_id', 'nomen_manda_1', type='many2one', relation='product.nomenclature', string='Group'),
        'nomen_manda_2': fields.related('product_id', 'nomen_manda_2', type='many2one', relation='product.nomenclature', string='Family'),
        'nomen_manda_3': fields.related('product_id', 'nomen_manda_3', type='many2one', relation='product.nomenclature', string='Root'),
        # optional nomenclature levels
        'nomen_sub_0': fields.related('product_id', 'nomen_sub_0', type='many2one', relation='product.nomenclature', string='Sub Class 1'),
        'nomen_sub_1': fields.related('product_id', 'nomen_sub_1', type='many2one', relation='product.nomenclature', string='Sub Class 2'),
        'nomen_sub_2': fields.related('product_id', 'nomen_sub_2', type='many2one', relation='product.nomenclature', string='Sub Class 3'),
        'nomen_sub_3': fields.related('product_id', 'nomen_sub_3', type='many2one', relation='product.nomenclature', string='Sub Class 4'),
        'nomen_sub_4': fields.related('product_id', 'nomen_sub_4', type='many2one', relation='product.nomenclature', string='Sub Class 5'),
        'nomen_sub_5': fields.related('product_id', 'nomen_sub_5', type='many2one', relation='product.nomenclature', string='Sub Class 6'),
        'nomen_manda_0_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Main Type', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_1_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Group', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_2_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Family', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_3_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Root', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_sub_0_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 1', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_sub_1_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 2', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_sub_2_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 3', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_sub_3_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 4', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_sub_4_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 5', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_sub_5_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 6', fnct_search=_search_nomen_s, multi="nom_s"),
        'product_amc': fields.float(digits=(16,2), string='AMC'),
        'reviewed_consumption': fields.float(digits=(16,2), string='FMC'),
        'currency_id': fields.related('product_id', 'currency_id', type='many2one', relation='res.currency', string='Func. cur.'),
        'uom_id': fields.related('product_id', 'uom_id', type='many2one', relation='product.uom', string='UoM',
                                store={'product.template': (_get_template, ['type'], 10)}),
        'mission_report_id': fields.many2one('stock.mission.report', string='Mission Report', required=True),
        'internal_qty': fields.float(digits=(16,2), string='Internal Qty.'),
        'internal_val': fields.float(digits=(16,2), string='Internal Val.'),
        'stock_qty': fields.float(digits=(16,2), string='Stock Qty.'),
        'stock_val': fields.float(digits=(16,2), string='Stock Val.'),
        'central_qty': fields.float(digits=(16,2), string='Central Stock Qty.'),
        'central_val': fields.float(digits=(16,2), string='Central Stock Val.'),
        'cross_qty': fields.float(digits=(16,3), string='Cross-docking Qty.'),
        'cross_val': fields.float(digits=(16,3), string='Cross-docking Val.'),
        'secondary_qty': fields.float(digits=(16,2), string='Secondary Stock Qty.'),
        'secondary_val': fields.float(digits=(16,2), string='Secondary Stock Val.'),
        'cu_qty': fields.float(digits=(16,2), string='Internal Cons. Unit Qty.'),
        'cu_val': fields.float(digits=(16,2), string='Internal Cons. Unit Val.'),
        'in_pipe_qty': fields.float(digits=(16,2), string='In Pipe Qty.'),
        'in_pipe_val': fields.float(digits=(16,2), string='In Pipe Val.'),
        'in_pipe_coor_qty': fields.float(digits=(16,2), string='In Pipe from Coord.'),
        'in_pipe_coor_val': fields.float(digits=(16,2), string='In Pipe from Coord.'),
        'updated': fields.boolean(string='Updated'),
        'full_view': fields.related('mission_report_id', 'full_view', string='Full view', type='boolean', store=True),
    }
    
    def _get_request(self, cr, uid, location_ids, product_id):
        '''
        Browse the good values and give the result
        '''
        obj = self.pool.get('report.stock.move')
        
        if isinstance(location_ids, (int, long)):
            location_ids = [location_ids]
            
        if not isinstance(product_id, (int, long)):
            raise osv.except_osv(_('Error'), _('You can\'t build the request for some products !'))
        
        minus_ids = obj.search(cr, uid, [('location_id', 'in', location_ids), 
                                         ('product_id', '=', product_id), 
                                         ('state', '=', 'done')])
        
        plus_ids = obj.search(cr, uid, [('location_dest_id', 'in', location_ids), 
                                        ('product_id', '=', product_id), 
                                        ('state', '=', 'done')])
        
        res = 0.00
        for r in obj.browse(cr, uid, plus_ids):
            res += r.product_qty
        for r in obj.browse(cr, uid, minus_ids):
            res -= r.product_qty
            
        return res

    def update_full_view_line(self, cr, uid, ids, context=None):
        for line in self.browse(cr, uid, ids, context=context):
            line_ids = self.search(cr, uid, [('mission_report_id', '!=', line.mission_report_id.id), ('product_id', '=', line.product_id.id)], context=context)
            lines = self.browse(cr, uid, line_ids, context=context)
    
            internal_qty = 0.00
            internal_val = 0.00
            stock_qty = 0.00
            stock_val = 0.00
            central_qty = 0.00
            central_val = 0.00
            cross_qty = 0.00
            cross_val = 0.00
            secondary_qty = 0.00
            secondary_val = 0.00
            cu_qty = 0.00
            cu_val = 0.00
            in_pipe_qty = 0.00
            in_pipe_val = 0.00
            in_pipe_not_coor_qty = 0.00
            in_pipe_not_coor_val = 0.00

            is_project = False
            if self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.level == 'project':
                is_project = True
    
            for l in lines:
                internal_qty += l.internal_qty
                internal_val += l.internal_val
                stock_qty += l.stock_qty
                stock_val += l.stock_val
                central_qty += l.central_qty
                central_val += l.central_val
                cross_qty += l.cross_qty
                cross_val += l.cross_val
                secondary_qty += l.secondary_qty
                secondary_val += l.secondary_val
                cu_qty += l.cu_qty
                cu_val += l.cu_val
                in_pipe_qty += l.in_pipe_qty
                in_pipe_val += l.in_pipe_val
                in_pipe_not_coor_qty += l.in_pipe_coor_qty
                in_pipe_not_coor_val += l.in_pipe_coor_qty

            if not is_project:
                in_pipe_qty = in_pipe_qty - in_pipe_not_coor_qty
                in_pipe_val = in_pipe_val - in_pipe_not_coor_val

            self.write(cr, uid, [line.id], {'product_amc': line.product_id.product_amc,
                                            'reviewed_consumption': line.product_id.reviewed_consumption,
                                            'internal_qty': internal_qty,
                                            'internal_val': internal_val,
                                            'stock_qty': stock_qty,
                                            'stock_val': stock_val,
                                            'central_qty': central_qty,
                                            'central_val': central_val,
                                            'cross_qty': cross_qty,
                                            'cross_val': cross_val,
                                            'secondary_qty': secondary_qty,
                                            'secondary_val': secondary_val,
                                            'cu_qty': cu_qty,
                                            'cu_val': cu_val,
                                            'in_pipe_qty': in_pipe_qty,
                                            'in_pipe_val': in_pipe_val,
                                            'in_pipe_coor_qty': in_pipe_not_coor_qty,
                                            'in_pipe_coor_val': in_pipe_not_coor_val}, context=context)
            
        return True
    
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
        
        stock_location_id = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_stock')
        if stock_location_id:
            stock_location_id = stock_location_id[1]
            
        # Check if the instance is a coordination or a project
        coordo_id = False
        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        coordo = self.pool.get('msf.instance').search(cr, uid, [('level', '=', 'coordo')], context=context)
        if company.instance_id.level == 'project' and coordo:
            coordo_id = self.pool.get('msf.instance').browse(cr, uid, coordo[0], context=context).instance
        
        # Search considered SLocation
        internal_loc = location_obj.search(cr, uid, [('usage', '=', 'internal')], context=context)
        central_loc = location_obj.search(cr, uid, [('central_location_ok', '=', True)], context=context)
        cross_loc = location_obj.search(cr, uid, [('cross_docking_location_ok', '=', True)], context=context)
        stock_loc = location_obj.search(cr, uid, [('location_id', 'child_of', stock_location_id),
                                                  ('id', 'not in', cross_loc), 
                                                  ('central_location_ok', '=', False)], context=context)
        cu_loc = location_obj.search(cr, uid, [('usage', '=', 'internal'), ('location_category', '=', 'consumption_unit')], context=context)
        secondary_location_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_intermediate_client_view')
        if secondary_location_id:
            secondary_location_id = secondary_location_id[1]
        secondary_location_ids = location_obj.search(cr, uid, [('location_id', 'child_of', secondary_location_id)], context=context)
        
        for line in self.browse(cr, uid, ids, context=context):
            # In case of full report
            if line.mission_report_id.full_view:
                continue
            
            standard_price = line.product_id.standard_price
            # Internal locations
            internal_qty = 0.00
            internal_val = 0.00
            if internal_loc:
                internal_qty = self._get_request(cr, uid, internal_loc, line.product_id.id)
                internal_val = internal_qty*standard_price
            
            # Stock locations
            stock_qty = 0.00
            stock_val = 0.00
            if stock_loc:
                stock_qty = self._get_request(cr, uid, stock_loc, line.product_id.id)
                stock_val = stock_qty*standard_price                                                    
            
            # Central stock locations
            central_qty = 0.00
            central_val = 0.00
            if central_loc:
                central_loc = location_obj.search(cr, uid, [('location_id', 'child_of', central_loc)], context=context)
                central_qty = self._get_request(cr, uid, central_loc, line.product_id.id)
                central_val = central_qty*standard_price
            
            # Cross-docking locations
            cross_qty = 0.00
            cross_val = 0.00
            if cross_loc:
                cross_loc = location_obj.search(cr, uid, [('location_id', 'child_of', cross_loc)], context=context)
                cross_qty = self._get_request(cr, uid, cross_loc, line.product_id.id)
                cross_val = cross_qty*standard_price

            # Secondary stock locations
            secondary_qty = 0.00
            secondary_val = 0.00
            if secondary_location_ids != False:
                secondary_qty = self._get_request(cr, uid, secondary_location_ids, line.product_id.id)
                secondary_val = secondary_qty*standard_price
                
            # Consumption unit locations
            cu_qty = 0.00
            cu_val = 0.00
            if cu_loc:
                cu_loc = location_obj.search(cr, uid, [('location_id', 'child_of', cu_loc)], context=context)
                cu_qty = self._get_request(cr, uid, cu_loc, line.product_id.id)
                cu_val = cu_qty*standard_price
                
            # In Pipe
            in_pipe_qty = 0.00
            in_pipe_not_coord_qty = 0.00
            cr.execute('''SELECT m.product_qty, m.product_uom, p.name
                          FROM stock_move m 
                              LEFT JOIN stock_picking s ON m.picking_id = s.id
                              LEFT JOIN res_partner p ON s.partner_id2 = p.id
                          WHERE type = 'in' AND state in ('confirmed', 'waiting', 'assigned')
                              AND product_id = %s''' % line.product_id.id)
            moves = cr.fetchall()
            for qty, uom, partner in moves:
                if uom != line.product_id.uom_id.id:
                    qty = self.pool.get('product.uom')._compute_qty(cr, uid, uom, qty, line.product_id.uom_id.id)
                
                in_pipe_qty += qty
                if partner == coordo_id:
                    in_pipe_not_coord_qty += qty
            
            in_pipe_val = in_pipe_qty*standard_price
            in_pipe_not_coord_val = in_pipe_not_coord_qty*standard_price
            
            values = {'product_amc': line.product_id.product_amc,
                      'reviewed_consumption': line.product_id.reviewed_consumption,
                      'internal_qty': internal_qty,
                      'internal_val': internal_val,
                      'stock_qty': stock_qty,
                      'stock_val': stock_val,
                      'central_qty': central_qty,
                      'central_val': central_val,
                      'cross_qty': cross_qty,
                      'cross_val': cross_val,
                      'secondary_qty': secondary_qty,
                      'secondary_val': secondary_val,
                      'cu_qty': cu_qty,
                      'cu_val': cu_val,
                      'in_pipe_qty': in_pipe_qty,
                      'in_pipe_val': in_pipe_val,
                      'in_pipe_coor_qty': in_pipe_not_coord_qty,
                      'in_pipe_coor_val': in_pipe_not_coord_val,
                      'updated': False}
            
            line_read = self.read(cr, uid, line.id, values.keys(), context=context)
            for k in values.keys():
                if line_read[k] != values[k]:
                    values.update({'updated': True})
            
            self.write(cr, uid, [line.id], values, context=context)
        return True
    
stock_mission_report_line()
