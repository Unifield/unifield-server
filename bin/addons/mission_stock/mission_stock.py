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
import logging

REPLACE_DICT = {'cell': 'Cell',
                'row': 'Row',
                'data': 'Data'}

def replace_all(text):
    for i, j in REPLACE_DICT.iteritems():
        text = text.replace(i, j)
    return text


class msr_in_progress(osv.osv_memory):
    '''
        US-1218: This memory class is used to store temporary values regarding the report process, when a report is in progress, at it into the table
        so that it will not be reprocessed again in the same transaction.
        If a thread is already started, another one will be ignored if the current one is not done!
    '''
    _name = "msr_in_progress"

    _columns = {
        'report_id': fields.many2one('stock.mission.report', "Report"),
        'done_ok': fields.boolean(string='Processing done'),
        'start_date': fields.datetime(string='Start date'),
    }

    _defaults = {
        'done_ok': lambda *a: False,
        'start_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    def create(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            super(msr_in_progress, self).create(cr, 1, {'report_id': id}, context=None)
        return

    def _already_processed(self, cr, uid, id, context=None):
        report_ids = self.search(cr, 1, [('report_id', '=', id), ('done_ok', '=', True)], context=context)
        if report_ids:
            return True
        return False

    def _is_in_progress(self, cr, uid, context=None):
        report_ids = self.search(cr, 1, [], context=context)
        if report_ids:
            return True
        return False

    def _delete_all(self, cr, uid, context=None):
        report_ids = self.search(cr, 1, [], context=context)
        self.unlink(cr, 1, report_ids, context)
        return

msr_in_progress()

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

        for report in self.read(cr, uid, ids, ['instance_id'], context=context):
            res[report['id']] = False
            if report['instance_id'] \
                and report['instance_id'][0] == local_instance_id:
                res[report['id']] = True

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
        'ns_nv_vals': fields.text(string='XML values'),
        's_nv_vals': fields.text(string='XML values'),
        'ns_v_vals': fields.text(string='XML values'),
        's_v_vals': fields.text(string='XML values'),
    }

    def __init__(self, pool, cr):
        a = super(stock_mission_report, self).__init__(pool, cr)
        for col in ['ns_nv_vals', 's_nv_vals', 'ns_v_vals', 's_v_vals']:
            self._columns[col]._prefetch = False
        return a

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
        msr_in_progress = self.pool.get('msr_in_progress')
        try:
            if msr_in_progress._is_in_progress(cr, uid, context):
                logging.getLogger('MSR').info("""____________________ Another process is progress, this request is ignore: %s""" % time.strftime('%Y-%m-%d %H:%M:%S'))
                return

            logging.getLogger('MSR').info("""____________________ Start the update process of MSR, at %s""" % time.strftime('%Y-%m-%d %H:%M:%S'))
            self.update(cr, uid, ids=[], context=None)
            msr_in_progress._delete_all(cr, uid, context)
            cr.commit()
            logging.getLogger('MSR').info("""____________________ Finished the update process of MSR, at %s""" % time.strftime('%Y-%m-%d %H:%M:%S'))
        except Exception as e:
            cr.rollback()
            logging.getLogger('MSR').error("""____________________ Error while running the update process of MSR, at %s - Error: %s""" % (time.strftime('%Y-%m-%d %H:%M:%S'), str(e)))
            msr_in_progress._delete_all(cr, uid, context)
        finally:
            cr.close(True)

    def update(self, cr, uid, ids=[], context=None):
        '''
        Create lines if new products exist or update the existing lines
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        line_obj = self.pool.get('stock.mission.report.line')
        msr_in_progress = self.pool.get('msr_in_progress')

        report_ids = self.search(cr, uid, [('local_report', '=', True), ('full_view', '=', False)], context=context)
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

        if not context.get('update_full_report'):
            all_report_ids = report_ids + full_report_ids
            for report_id in all_report_ids:
                # register immediately this report id into the table temp
                msr_in_progress.create(cr, uid, report_id, context)

        product_ids = self.pool.get('product.product').search(cr, uid, [], context=context)
        product_values = {}
        temp_prods = self.pool.get('product.product').read(cr, uid, product_ids, ['product_amc', 'reviewed_consumption'], context=context)

        logging.getLogger('MSR').info("""___ Number of MSR lines to be updated: %s, at %s""" % (len(temp_prods), time.strftime('%Y-%m-%d %H:%M:%S')))

        for product in temp_prods:
            product_values.setdefault(product['id'], {})
            product_values[product['id']].setdefault('product_amc', product['product_amc'])
            product_values[product['id']].setdefault('reviewed_consumption', product['reviewed_consumption'])

        # Check in each report if new products are in the database and not in the report
        for report in self.read(cr, uid, report_ids, ['local_report', 'full_view'], context=context):
            #self.write(cr, uid, [report.id], {'export_ok': False}, context=context)
            # Create one line by product
            cr.execute('''SELECT id FROM product_product
                        EXCEPT
                          SELECT product_id FROM stock_mission_report_line WHERE mission_report_id = %s''' % report['id'])
            for product in cr.fetchall():
                line_ids.append(line_obj.create(cr, uid, {'product_id': product, 'mission_report_id': report['id']}, context=context))

            # Don't update lines for full view or non local reports
            if not report['local_report']:
                continue

            #US-1218: If this report is previously processed, then do not redo it again for this transaction!
            if msr_in_progress._already_processed(cr, uid, report['id'], context):
                continue

            logging.getLogger('MSR').info("""___ updating the report lines of the report: %s, at %s (this may take very long time!)""" % (report['id'], time.strftime('%Y-%m-%d %H:%M:%S')))
            if context.get('update_full_report'):
                full_view = self.search(cr, uid, [('full_view', '=', True)])
                if full_view:
                    line_ids = line_obj.search(cr, uid, [('mission_report_id', 'in', full_view)])
                    line_obj.update_full_view_line(cr, uid, line_ids, context=context)
            elif not report['full_view']:
                # Update all lines
                self.update_lines(cr, uid, [report['id']])

            msr_ids = msr_in_progress.search(cr, uid, [('report_id', '=', report['id'])], context=context)
            msr_in_progress.write(cr, uid, msr_ids, {'done_ok': True}, context=context)

            logging.getLogger('MSR').info("""___ exporting the report lines of the report %s to csv, at %s""" % (report['id'], time.strftime('%Y-%m-%d %H:%M:%S')))
            self._get_export_csv(cr, uid, report['id'], product_values, context=context)
            # Update the update date on report
            self.write(cr, uid, [report['id']], {'last_update': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
            logging.getLogger('MSR').info("""___ finished processing completely for the report: %s, at %s \n""" % (report['id'], time.strftime('%Y-%m-%d %H:%M:%S')))

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
            cr.execute('''SELECT m.product_id, sum(m.product_qty), m.product_uom, p.name
                          FROM stock_move m
                              LEFT JOIN stock_picking s ON m.picking_id = s.id
                              LEFT JOIN res_partner p ON s.partner_id2 = p.id
                          WHERE s.type = 'in' AND m.state in ('confirmed', 'waiting', 'assigned')
                          GROUP BY m.product_id, m.product_uom, p.name
                          ORDER BY m.product_id''')

            in_pipe_moves = cr.fetchall()
            current_product = None
            line = None
            vals = {}
            for product_id, qty, uom, partner in in_pipe_moves:
                if current_product != product_id:
                    if line and vals and (vals.get('in_pipe_qty', False) or vals.get('in_pipe_coor_qty', False)):
                        line_obj.write(cr, uid, [line.id], vals)
                    line_id = line_obj.search(cr, uid, [('product_id', '=', product_id),
                                                        ('mission_report_id', '=', id)])

                    vals = {'in_pipe_qty': 0.00,
                            'in_pipe_coor_qty': 0.00,
                            'updated': True}
                    current_product = product_id
                    if not line_id:
                        continue

                line = line_obj.browse(cr, uid, line_id[0])
                if uom != line.product_id.uom_id.id:
                    qty = self.pool.get('product.uom')._compute_qty(cr, uid, uom, qty, line.product_id.uom_id.id)

                vals['in_pipe_qty'] = vals['in_pipe_qty'] + qty

                if partner == coordo_id:
                    vals['in_pipe_coor_qty'] = vals['in_pipe_coor_qty'] + qty

            if line and vals and (vals.get('in_pipe_qty', False) or vals.get('in_pipe_coor_qty', False)):
                line_obj.write(cr, uid, [line.id], vals)

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

    def _get_export_csv(self, cr, uid, ids, product_values, context=None):
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

        def set_data(request, report_id, line, data_name,):
            data = ''
            cr.execute(request, (report_id, line['id']))
            try:
                product_amc = line['product_id'][0] in product_values and product_values[line['product_id'][0]]['product_amc'] or 0.00
                reviewed_consumption = line['product_id'][0] in product_values and product_values[line['product_id'][0]]['reviewed_consumption'] or 0.00
                for r in cr.dictfetchall():
                    data += r[data_name] % (product_amc, reviewed_consumption)
            except Exception, e:
                logging.getLogger('Mission stock report').warning("""An error is occured when compute the consumption values for product at mission stock report file generation. Data: \n %s""" % data_name)

            data += '\n'
            return data

#        for report in self.browse(cr, uid, ids, context=context):
        for report_id in ids:
            # No split, no valuation
            ns_nv_data = ''
            # No split, valuation
            ns_v_data = ''
            # Split, no valuation
            s_nv_data = ''
            # Split, valuation
            s_v_data = ''

            request = '''SELECT
                l.product_id AS product_id,
                xmlelement(name Row,

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('String' as "ss:Type"),
                replace(l.default_code, '%%', '%%%%'))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('String' as "ss:Type"),
                replace(pt.name, '%%', '%%%%'))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('String' as "ss:Type"),
                replace(pu.name, '%%', '%%%%'))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.internal_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.wh_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.cross_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.secondary_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.cu_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                '%%s')),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                '%%s')),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.in_pipe_qty, '999999999999.999'))))
                ) AS ns_nv_data,
                xmlelement(name Row,

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('String' as "ss:Type"),
                replace(l.default_code, '%%', '%%%%'))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('String' as "ss:Type"),
                replace(pt.name, '%%', '%%%%'))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('String' as "ss:Type"),
                replace(pu.name, '%%', '%%%%'))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.internal_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.stock_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.central_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.cross_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.secondary_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.cu_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                '%%s')),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                '%%s')),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.in_pipe_qty, '999999999999.999'))))
                ) AS s_nv_data,
                xmlelement(name Row,

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('String' as "ss:Type"),
                replace(l.default_code, '%%', '%%%%'))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('String' as "ss:Type"),
                replace(pt.name, '%%', '%%%%'))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('String' as "ss:Type"),
                replace(pu.name, '%%', '%%%%'))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(pt.standard_price, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('String' as "ss:Type"),
                rc.name)),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.internal_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char((l.internal_qty * pt.standard_price), '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.wh_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.cross_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.secondary_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.cu_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                '%%s')),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                '%%s')),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.in_pipe_qty, '999999999999.999'))))
                ) AS ns_v_data,
                xmlelement(name Row,

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('String' as "ss:Type"),
                replace(l.default_code, '%%', '%%%%'))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('String' as "ss:Type"),
                replace(pt.name, '%%', '%%%%'))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('String' as "ss:Type"),
                replace(pu.name, '%%', '%%%%'))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char((l.internal_qty * pt.standard_price), '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('String' as "ss:Type"),
                rc.name)),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.internal_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char((l.internal_qty * pt.standard_price), '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.stock_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.central_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.cross_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.secondary_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.cu_qty, '999999999999.999')))),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                '%%s')),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                '%%s')),

                xmlelement(name Cell, xmlattributes('ssBorder' as "ss:StyleID"),
                xmlelement(name Data, xmlattributes('Number' as "ss:Type"),
                trim(to_char(l.in_pipe_qty, '999999999999.999'))))
                ) AS s_v_data
            FROM stock_mission_report_line l
                 LEFT JOIN product_product pp ON l.product_id = pp.id
                 LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                 LEFT JOIN product_uom pu ON pt.uom_id = pu.id
                 LEFT JOIN res_currency rc ON pp.currency_id = rc.id
            WHERE l.mission_report_id = %s'''

            cr.execute(request, (report_id, ))
            res = cr.dictfetchall()
            for line in res:
                try:
                    product_amc = line['product_id'] in product_values and product_values[line['product_id']]['product_amc'] or 0.00
                    reviewed_consumption = line['product_id'] in product_values and product_values[line['product_id']]['reviewed_consumption'] or 0.00
                    ns_nv_data += replace_all(line['ns_nv_data'] % (product_amc, reviewed_consumption))
                    ns_v_data  += replace_all(line['ns_v_data'] % (product_amc, reviewed_consumption))
                    s_nv_data  += replace_all(line['s_nv_data'] % (product_amc, reviewed_consumption))
                    s_v_data   += replace_all(line['s_v_data'] % (product_amc, reviewed_consumption))
                except Exception, e:
                    logging.getLogger('Mission stock report').warning("""An error is occured when generate the mission stock report file. Data: \n %s""" % line)

            for data, field in [(ns_nv_data, 'ns_nv_vals'), (ns_v_data, 'ns_v_vals'), (s_nv_data, 's_nv_vals'), (s_v_data, 's_v_vals')]:
                self.write(cr, uid, [report_id], {field: data}, context=context)

            self.write(cr, uid, [report_id], {'export_ok': True}, context=context)

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

    def xmlid_code_migration(self, cr, ids):
        cr.execute('UPDATE stock_mission_report_line l set xmlid_code = (select xmlid_code from product_product p where p.id=l.product_id)')
        print 'UPDATE stock_mission_report_line l set xmlid_code = (select xmlid_code from product_product p where p.id=l.product_id)'
        print cr.statusmessage
        return True

    def is_migration(self, cr, ids):
        cr.execute('UPDATE stock_mission_report_line l set international_status = (select international_status from product_product p where p.id=l.product_id)')
        print 'UPDATE stock_mission_report_line l set international_status = (select international_status from product_product p where p.id=l.product_id)'
        print cr.statusmessage

        return True

    _columns = {
        'product_id': fields.many2one('product.product', string='Name', required=True, ondelete="cascade", select=1),
        'default_code': fields.related('product_id', 'default_code', string='Reference', type='char', size=64, store=True, write_relate=False),
        'xmlid_code': fields.related('product_id', 'xmlid_code', string='MSFID', type='char', size=18, store=True, write_relate=False, _fnct_migrate=xmlid_code_migration),
        'old_code': fields.related('product_id', 'old_code', string='Old Code', type='char'),
        'name': fields.related('product_id', 'name', string='Name', type='char'),
        'categ_id': fields.related('product_id', 'categ_id', string='Category', type='many2one', relation='product.category',
                                   store={'product.template': (_get_template, ['type'], 10),
                                          'stock.mission.report.line': (lambda self, cr, uid, ids, c={}: ids, ['product_id'], 10)},
                                   write_relate=False),
        'type': fields.related('product_id', 'type', string='Type', type='selection', selection=_get_product_type_selection,
                               store={'product.template': (_get_template, ['type'], 10),
                                      'stock.mission.report.line': (lambda self, cr, uid, ids, c={}: ids, ['product_id'], 10)},
                               write_relate=False),
        'subtype': fields.related('product_id', 'subtype', string='Subtype', type='selection', selection=_get_product_subtype_selection,
                                  store={'product.template': (_get_template, ['subtype'], 10),
                                         'stock.mission.report.line': (lambda self, cr, uid, ids, c={}: ids, ['product_id'], 10)},
                                  write_relate=False),
        'international_status': fields.related(
            'product_id',
            'international_status',
            type='many2one',
            relation='product.international.status',
            string='International status',
            store=True,
            write_relate=False,
            _fnct_migrate=is_migration,
        ),
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
                                store={
                                    'product.template': (_get_template, ['type'], 10),
                                    'stock.mission.report.line': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 10),
                                },
                                write_relate=False),
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
        'instance_id': fields.many2one(
            'msf.instance',
            string='HQ Instance',
            required=True,
        ),
    }

    def _get_default_destination_instance_id(self, cr, uid, context=None):
        instance = self.pool.get('res.users').get_browse_user_instance(cr, uid, context)
        if instance:
            if instance.parent_id:
                if instance.parent_id.parent_id:
                    return instance.parent_id.parent_id.id
                return instance.parent_id.id
            return instance.id

        return False

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
        'instance_id': _get_default_destination_instance_id,
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
