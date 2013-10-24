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
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator 

import pooler
import time
import threading
import base64                                                                   


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
        'move_ids': fields.many2many('stock.move', 'mission_move_rel', 'mission_id', 'move_id', string='Noves'),
        'export_ok': fields.boolean(string='Export file possible ?'),
        'ns_nv_file': fields.binary(string='XML export'),
        'ns_v_file': fields.binary(string='XML export'),
        's_nv_file': fields.binary(string='XML export'),
        's_v_file': fields.binary(string='XML export'),
    }
    
    _defaults = {
        'full_view': lambda *a: False,
        #'export_ok': False,
    }
    
    def create(self, cr, uid, vals, context=None):
        '''
        Create lines at report creation
        '''
        res = super(stock_mission_report, self).create(cr, uid, vals, context=context)
        
        local_instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.id
        
        # Not update lines for full view or non local reports
        if vals.get('instance_id', False) and vals['instance_id'] == local_instance_id and not vals.get('full_view', False):
            if not context.get('no_update', False):
                self.update(cr, uid, res, context=context)
        
        return res
    
    def background_update(self, cr, uid, ids, context=None):
        """
        Run the update of local stock report in background 
        """
        if not ids:
            ids = []
        
        threaded_calculation = threading.Thread(target=self.update_newthread, args=(cr, uid, ids, context))
        threaded_calculation.start()
        return {'type': 'ir.actions.act_window_close'}
    
    def update_newthread(self, cr, uid, ids=[], context=None):
        # Open a new cursor : Don't forget to close it at the end of method
        cr = pooler.get_db(cr.dbname).cursor()
        a = time.strftime('%H-%M-%S')
        try:
            self.update(cr, uid, ids=[], context=None)
            cr.commit()
        finally:
            cr.close()

    def update(self, cr, uid, ids=[], context=None):
        '''
        Create lines if new products exist or update the existing lines
        '''
        if not context:
            context = {}
            
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        line_obj = self.pool.get('stock.mission.report.line')
        
        report_ids = self.search(cr, uid, [('local_report', '=', True)], context=context)
        full_report_ids = self.search(cr, uid, [('full_view', '=', True)], context=context)
        instance_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
        line_ids = []
        
        # Create a local report if no exist
        if not report_ids and context.get('update_mode', False) not in ('update', 'init') and instance_id:
            c = context.copy()
            c.update({'no_update': True})
            report_ids = [self.create(cr, uid, {'name': instance_id.name,
                                               'instance_id': instance_id.id,
                                               'full_view': False}, context=c)]

        # Create a full view report if no exist
        if not full_report_ids and context.get('update_mode', False) not in ('update', 'init') and instance_id:
            c = context.copy()
            c.update({'no_update': True})
            full_report_ids = [self.create(cr, uid, {'name': 'Full view',
                                               'instance_id': instance_id.id,
                                               'full_view': True}, context=c)]

        cr.commit()

        if context.get('update_full_report'):
            report_ids = full_report_ids
            

        # Check in each report if new products are in the database and not in the report
        for report in self.browse(cr, uid, report_ids, context=context):
            #self.write(cr, uid, [report.id], {'export_ok': False}, context=context)
            # Create one line by product
            cr.execute('''SELECT id FROM product_product
                        EXCEPT
                          SELECT product_id FROM stock_mission_report_line WHERE mission_report_id = %s''' % report.id)
            for product in cr.fetchall():
                line_ids.append(line_obj.create(cr, uid, {'product_id': product, 'mission_report_id': report.id}, context=context))
            
            # Don't update lines for full view or non local reports
            if not report.local_report:
                continue
        
            # Update the update date on report
            self.write(cr, uid, [report.id], {'last_update': time.strftime('%Y-%m-%d %H:%M:%S'),
                                              'export_ok': False}, context=context)
               
            if context.get('update_full_report'):
                full_view = self.search(cr, uid, [('full_view', '=', True)])
                if full_view:
                    line_ids = line_obj.search(cr, uid, [('mission_report_id', 'in', full_view)])
                    line_obj.update_full_view_line(cr, uid, line_ids, context=context)
            elif not report.full_view:
                # Update all lines
                self.update_lines(cr, uid, [report.id])

            self._get_export_csv(cr, uid, report.id, context=context)

            #self._get_export_csv(cr, uid, report.id, context=context)

        # After update of all normal reports, update the full view report
        if not context.get('update_full_report'):
            c = context.copy()
            c.update({'update_full_report': True})
            self.update(cr, uid, [], context=c)

        return True
    
    def update_lines(self, cr, uid, ids, context=None):
        location_obj = self.pool.get('stock.location')
        data_obj = self.pool.get('ir.model.data')
        line_obj = self.pool.get('stock.mission.report.line')
        product_obj = self.pool.get('product.product')
        # Search considered SLocation
        stock_location_id = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_stock')
        if stock_location_id:
            stock_location_id = stock_location_id[1]
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
        
        cu_loc = location_obj.search(cr, uid, [('location_id', 'child_of', cu_loc)], context=context)
        central_loc = location_obj.search(cr, uid, [('location_id', 'child_of', central_loc)], context=context)
        
        # Check if the instance is a coordination or a project
        coordo_id = False
        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        coordo = self.pool.get('msf.instance').search(cr, uid, [('level', '=', 'coordo')], context=context)
        if company.instance_id.level == 'project' and coordo:
            coordo_id = self.pool.get('msf.instance').browse(cr, uid, coordo[0], context=context).instance
        
        for id in ids:
            # In-Pipe moves
            cr.execute('''SELECT m.product_id, m.product_qty, m.product_uom, p.name, m.id
                          FROM stock_move m
                              LEFT JOIN stock_picking s ON m.picking_id = s.id
                              LEFT JOIN res_partner p ON s.partner_id2 = p.id
                          WHERE s.type = 'in' AND m.state in ('confirmed', 'waiting', 'assigned')''')
            
            in_pipe_moves = cr.fetchall()
            for product_id, qty, uom, partner, move_id in in_pipe_moves:
                line_id = line_obj.search(cr, uid, [('product_id', '=', product_id),
                                                    ('mission_report_id', '=', id)])
                if line_id:
                    line = line_obj.browse(cr, uid, line_id[0])
                    if uom != line.product_id.uom_id.id:
                        qty = self.pool.get('product.uom')._compute_qty(cr, uid, uom, qty, line.product_id.uom_id.id)
                        
                    vals = {'in_pipe_qty': 0.00,
                            'in_pipe_coor_qty': 0.00,
                            'updated': True}
                    
                    vals['in_pipe_qty'] = vals['in_pipe_qty'] + qty
                    
                    if partner == coordo_id:
                        vals['in_pipe_coor_qty'] = vals['in_pipe_coor_qty'] + qty

                    line_obj.write(cr, uid, line.id, vals)
            
            # All other moves
            cr.execute('''
                        SELECT id, product_id, product_uom, product_qty, location_id, location_dest_id
                        FROM stock_move 
                        WHERE state = 'done'
                        AND id not in (SELECT move_id FROM mission_move_rel WHERE mission_id = %s)
            ''' % (id))
            res = cr.fetchall()
            for move in res:
                cr.execute('INSERT INTO mission_move_rel VALUES (%s, %s)' % (id, move[0]))
                product = product_obj.browse(cr, uid, move[1])
                line_id = line_obj.search(cr, uid, [('product_id', '=', move[1]),
                                                    ('mission_report_id', '=', id)])
                if line_id:
                    line = line_obj.browse(cr, uid, line_id[0])
                    qty = self.pool.get('product.uom')._compute_qty(cr, uid, move[2], move[3], product.uom_id.id)
                    vals = {'internal_qty': line.internal_qty or 0.00,
                            'stock_qty': line.stock_qty or 0.00,
                            'central_qty': line.central_qty or 0.00,
                            'cross_qty': line.cross_qty or 0.00,
                            'secondary_qty': line.secondary_qty or 0.00,
                            'cu_qty': line.cu_qty or 0.00,
                            'updated': True}
                    
                    if move[4] in internal_loc:
                        vals['internal_qty'] = vals['internal_qty'] - qty
                    if move[4] in stock_loc:
                        vals['stock_qty'] = vals['stock_qty'] - qty
                    if move[4] in central_loc:
                        vals['central_qty'] = vals['central_qty'] - qty
                    if move[4] in cross_loc:
                        vals['cross_qty'] = vals['cross_qty'] - qty
                    if move[4] in secondary_location_ids:
                        vals['secondary_qty'] = vals['secondary_qty'] - qty
                    if move[4] in cu_loc:
                        vals['cu_qty'] = vals['cu_qty'] - qty
                        
                    if move[5] in internal_loc:
                        vals['internal_qty'] = vals['internal_qty'] + qty
                    if move[5] in stock_loc:
                        vals['stock_qty'] = vals['stock_qty'] + qty
                    if move[5] in central_loc:
                        vals['central_qty'] = vals['central_qty'] + qty
                    if move[5] in cross_loc:
                        vals['cross_qty'] = vals['cross_qty'] + qty
                    if move[5] in secondary_location_ids:
                        vals['secondary_qty'] = vals['secondary_qty'] + qty
                    if move[5] in cu_loc:
                        vals['cu_qty'] = vals['cu_qty'] + qty

                    vals.update({'internal_val': vals['internal_qty'] * product.standard_price})
                    line_obj.write(cr, uid, line.id, vals)
                
        return True

    def _get_export_csv(self, cr, uid, ids, context=None):
        '''
        Get the XML files of the stock mission report.
        This method generates 4 files (according to option set) :
            * 1 file with no split of WH and no valuation
            * 1 file with no split of WH and valuation
            * 1 file with split of WH and valuation
            * 1 file with split aof WH and valuation
        '''
        context = context or {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        def set_data(line, headers, h_nb):
            res = []
            for h in headers:
                if h[h_nb] == 1:
                    obj = line
                    value = False
                    for v in h[2].split('.'):
                        value = obj.__getitem__(v)
                        obj = value
                        if not value:
                            value = False
                            break
                    if not value and h[1] == 'number':
                        value = 0.00
                    res.append(value)

            return res

        # ns_nv => No split, no valuation
        # ns_v => No split, valuation
        # s_nv => Split, no valuation
        # s_v => Split, valuation
        # headers (_(Field name), Field type, Technical field name, ns_nv, ns_v, s_nv, s_v
        headers = [(_('Reference'), 'string', 'default_code', 1, 1, 1, 1),
                   (_('Name'), 'string', 'name', 1, 1, 1, 1),
                   (_('UoM'), 'string', 'product_id.uom_id.name', 1, 1, 1, 1),
                   (_('Cost price'), 'number', 'cost_price', 0, 1, 0, 1),
                   (_('Func. Cur.'), 'string', 'currency_id.name', 0, 1, 0, 1),
                   (_('Instance stock'), 'number', 'internal_qty', 1, 1, 1, 1),
                   (_('Instance stock val.'), 'number', 'internal_val', 0, 1, 0, 1),
                   (_('Warehouse stock'), 'number', 'wh_qty', 1, 1, 0, 0),
                   (_('Stock Qty.'), 'number', 'stock_qty', 0, 0, 1, 1),
                   (_('Unallocated Stock Qty.'), 'number', 'central_qty', 0, 0, 1, 1),
                   (_('Cross-Docking Qty.'), 'number', 'cross_qty', 1, 1, 1, 1),
                   (_('Secondary Stock Qty.'), 'number', 'secondary_qty', 1, 1, 1, 1),
                   (_('Internal Cons. Unit Qty.'), 'number', 'cu_qty', 1, 1, 1, 1),
                   (_('AMC'), 'number', 'product_id.product_amc', 1, 1, 1, 1),
                   (_('FMC'), 'number', 'product_id.reviewed_consumption', 1, 1, 1, 1),
                   (_('In Pipe Qty.'), 'number', 'in_pipe_qty', 1, 1, 1, 1),]

        for report in self.browse(cr, uid, ids, context=context):
            # No split, no valuation
            ns_nv_headers = [(x[0], x[1]) for x in headers if x[3] == 1]
            ns_nv_data = []
            # No split, valuation
            ns_v_headers = [(x[0], x[1]) for x in headers if x[4] == 1]
            ns_v_data = []
            # Split, no valuation
            s_nv_headers = [(x[0], x[1]) for x in headers if x[5] == 1]
            s_nv_data = []
            # Split, valuation
            s_v_headers = [(x[0], x[1]) for x in headers if x[6] == 1]
            s_v_data = []

            for line in report.report_line:
                # No split, no valuation
                ns_nv_data.append(set_data(line, headers, 3))
                # No split, valuation
                ns_v_data.append(set_data(line, headers, 4))
                # Split, no valuation
                s_nv_data.append(set_data(line, headers, 5))
                # Split, valuation
                s_v_data.append(set_data(line, headers, 6))

            ns_nv_tmpl = SpreadsheetCreator('Template of Mission stock - No split - No valuation', ns_nv_headers, ns_nv_data)
            ns_v_tmpl = SpreadsheetCreator('Template of Mission stock - No split - Valuation', ns_v_headers, ns_v_data)
            s_nv_tmpl = SpreadsheetCreator('Template of Mission stock - Split - No valuation', s_nv_headers, s_nv_data)
            s_v_tmpl = SpreadsheetCreator('Template of Mission stock - Split - Valuation', s_v_headers, s_v_data)

            ns_nv_file = base64.encodestring(ns_nv_tmpl.get_xml(default_filters=['decode.utf8']))
            ns_v_file = base64.encodestring(ns_v_tmpl.get_xml(default_filters=['decode.utf8']))
            s_nv_file = base64.encodestring(s_nv_tmpl.get_xml(default_filters=['decode.utf8']))
            s_v_file = base64.encodestring(s_v_tmpl.get_xml(default_filters=['decode.utf8']))
            
            self.write(cr, uid, [report.id], {'ns_nv_file': ns_nv_file,
                                              'ns_v_file': ns_v_file,
                                              's_nv_file': s_nv_file,
                                              's_v_file': s_v_file,
                                              'export_ok': True}, context=context)

        return True

stock_mission_report()


class stock_mission_report_line(osv.osv):
    _name = 'stock.mission.report.line'
    _description = 'Mission stock report line'
    _order = 'default_code'
    
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
            narg = [('_'.join(el), arg[1], arg[2])]
        
        return narg
    
    def _get_template(self, cr, uid, ids, context=None):
        return self.pool.get('stock.mission.report.line').search(cr, uid, [('product_id.product_tmpl_id', 'in', ids)], context=context)

    def _get_wh_qty(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = line.stock_qty + line.central_qty

        return res

    def _get_internal_val(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = line.internal_qty * line.cost_price

        return res
    
    _columns = {
        'product_id': fields.many2one('product.product', string='Name', required=True, ondelete="cascade"),
        'default_code': fields.related('product_id', 'default_code', string='Reference', type='char', size=64, store=True),
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
        'product_amc': fields.related('product_id', 'product_amc', type='float', string='AMC'),
        'reviewed_consumption': fields.related('product_id', 'reviewed_consumption', type='float', string='FMC'),
        'currency_id': fields.related('product_id', 'currency_id', type='many2one', relation='res.currency', string='Func. cur.'),
        'cost_price': fields.related('product_id', 'standard_price', type='float', string='Cost price'),
        'uom_id': fields.related('product_id', 'uom_id', type='many2one', relation='product.uom', string='UoM',
                                store={'product.template': (_get_template, ['type'], 10)}),
        'mission_report_id': fields.many2one('stock.mission.report', string='Mission Report', required=True),
        'internal_qty': fields.float(digits=(16,2), string='Instance Stock'),
        'internal_val': fields.function(_get_internal_val, method=True, type='float', string='Instance Stock Val.'),
        #'internal_val': fields.float(digits=(16,2), string='Instance Stock Val.'),
        'stock_qty': fields.float(digits=(16,2), string='Stock Qty.'),
        'stock_val': fields.float(digits=(16,2), string='Stock Val.'),
        'central_qty': fields.float(digits=(16,2), string='Unallocated Stock Qty.'),
        'central_val': fields.float(digits=(16,2), string='Unallocated Stock Val.'),
        'wh_qty': fields.function(_get_wh_qty, method=True, type='float', string='Warehouse stock', 
                                  store={'stock.mission.report.line': (lambda self, cr, uid, ids, c=None: ids, ['stock_qty', 'central_qty'], 10),}),
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
        'move_ids': fields.many2many('stock.move', 'mission_line_move_rel', 'line_id', 'move_id', string='Noves'),
    }

    _defaults = {
        'internal_qty': 0.00,
        'internal_val': 0.00,
        'stock_qty': 0.00,
        'stock_val': 0.00,
        'wh_qty': 0.00,
        'central_qty': 0.00,
        'central_val': 0.00,
        'cross_qty': 0.00,
        'cross_val': 0.00,
        'secondary_qty': 0.00,
        'secondary_val': 0.00,
        'cu_qty': 0.00,
        'cu_val': 0.00,
        'in_pipe_qty': 0.00,
        'in_pipe_val': 0.00,
        'in_pipe_coor_qty': 0.00,
        'in_pipe_coor_val': 0.00,
    }

    def update_full_view_line(self, cr, uid, ids, context=None):
        is_project = False
        if self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.level == 'project':
            is_project = True


        request = '''SELECT l.product_id AS product_id,
                            sum(l.internal_qty) AS internal_qty,
                            sum(l.stock_qty) AS stock_qty,
                            sum(l.central_qty) AS central_qty,
                            sum(l.cross_qty) AS cross_qty,
                            sum(l.secondary_qty) AS secondary_qty,
                            sum(l.cu_qty) AS cu_qty,
                            sum(l.in_pipe_qty) AS in_pipe_qty,
                            sum(l.in_pipe_coor_qty) AS in_pipe_coor_qty,
                            sum(l.internal_qty)*t.standard_price AS internal_val
                     FROM stock_mission_report_line l
                       LEFT JOIN 
                          stock_mission_report m 
                       ON l.mission_report_id = m.id
                       LEFT JOIN
                          product_product p 
                       ON l.product_id = p.id
                       LEFT JOIN
                          product_template t
                       ON p.product_tmpl_id = t.id
                     WHERE m.full_view = False 
                       AND (l.internal_qty != 0.00
                       OR l.stock_qty != 0.00
                       OR l.central_qty != 0.00
                       OR l.cross_qty != 0.00
                       OR l.secondary_qty != 0.00
                       OR l.cu_qty != 0.00
                       OR l.in_pipe_qty != 0.00
                       OR l.in_pipe_coor_qty != 0.00)
                     GROUP BY l.product_id, t.standard_price'''

        cr.execute(request)

        vals = cr.fetchall()
        mission_report_id = self.pool.get('stock.mission.report').search(cr, uid, [('full_view', '=', True)], context=context)
        for line in vals:
            line_ids = self.search(cr, uid, [('mission_report_id.full_view', '=', True), ('product_id', '=', line[0])], context=context)
            if not line_ids:
                if not mission_report_id:
                    continue
                line_id = self.create(cr, uid, {'mission_report_id': mission_report_id[0],
                                                'product_id': line[0]}, context=context)
            else:
                line_id = line_ids[0]
            
            in_pipe = line[7] or 0.00
            if not is_project:
                in_pipe = (line[7] or 0.00) - (line[8] or 0.00)

            self.write(cr, uid, [line_id], {'internal_qty': line[1] or 0.00,
                                            'internal_val': line[9] or 0.00,
                                            'stock_qty': line[2] or 0.00,
                                            'central_qty': line[3] or 0.00,
                                            'cross_qty': line[4] or 0.00,
                                            'secondary_qty': line[5] or 0.00,
                                            'cu_qty': line[6] or 0.00,
                                            'in_pipe_qty': line[7] or 0.00,
                                            'in_pipe_coor_qty': line[8] or 0.00,}, context=context)
            
        return True
    
stock_mission_report_line()
