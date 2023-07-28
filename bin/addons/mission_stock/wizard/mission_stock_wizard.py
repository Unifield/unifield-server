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
import time


class mission_stock_wizard(osv.osv_memory):
    _name = 'mission.stock.wizard'

    def _get_progression_state(self, cr, uid, report_id, context=None):
        """
        Returns the progression state of the update and the start_date of it in
        case of 'in_progress' state. None in case of other state.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param report_id: ID of mission.stock.report to compute
        :param context: Context of the call
        :return: The state of the progression and the start date in case of 'in_progress'
        """
        msr_in_progress = self.pool.get('msr_in_progress')
        msr_obj = self.pool.get('stock.mission.report')

        if context is None:
            context = {}

        if msr_in_progress._already_processed(cr, 1, report_id, context=context):
            return 'done', None

        msr_ids = msr_in_progress.search(cr, 1, [('report_id', '=', report_id)], context=context)
        if msr_ids:
            st_date = msr_in_progress.browse(cr, 1, msr_ids[0], context=context).start_date
            return 'in_progress', st_date

        export_state = msr_obj.read(cr, uid, report_id, ['export_state'],
                                    context=context)['export_state']
        return export_state, None

    _columns = {
        'report_id': fields.many2one(
            'stock.mission.report',
            string='Report',
            domain=[('instance_id.state', '!=', 'inactive'), '|', ('full_view', '=', False), '&', ('full_view', '=', True), ('instance_id.level', '!=', 'project')]
        ),
        'with_valuation': fields.selection(
            [('true', 'Yes'), ('false', 'No')],
            string='Display stock valuation ?',
            required=True,
        ),
        'display_only_in_stock': fields.selection(
            [('true', 'Yes'), ('false', 'No')],
            string='Display only products in stock and/or in pipe',
            required=True,
        ),
        'last_update': fields.datetime(
            string='Last update',
            readonly=True,
        ),
        'export_ok': fields.boolean(
            string='XML Export ready',
        ),
        'export_file': fields.binary(
            string='XML File',
        ),
        'fname': fields.char(
            string='Filename',
            size=256,
        ),
        'processed_start_date': fields.datetime(string='since', readonly=True),
        'processed_state': fields.selection([
                                            ('no_report_selected', 'No report selected'),
                                            ('draft', 'Draft'),
                                            ('not_started', 'Not started'),
                                            ('in_progress', 'In Progress'),
                                            ('done', 'Done'),
                                            ('error', 'Error')
                                            ], string="Processing", readonly=True),
        'export_error_msg': fields.text('Error message', readonly=True),
        'instance_level': fields.char('Instance Level', size=64),
        'local_report': fields.boolean('Local Report'),
        'full_view': fields.boolean('Full View'),
    }

    def _get_fname(self, cr, uid, context=None):
        if context is None:
            context = {}
        instance_name = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.name

        return _('Mission_Stock_Report_%s_%s') % (instance_name, time.strftime('%Y%m%d_%H%M%S'))

    _defaults = {
        'with_valuation': lambda *a: 'true',
        'display_only_in_stock': lambda *a: 'false',
        'fname': _get_fname,
        'processed_state': lambda *a: 'not_started',
        'export_error_msg': lambda *a: False,
        'local_report': True,
        'full_view': False,
    }

    def default_get(self, cr, uid, fields_list, context=None, from_web=False):
        '''
        Choose the first local report as default
        '''
        res = super(mission_stock_wizard, self).default_get(cr, uid, fields_list, context=context, from_web=from_web)

        instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
        if not instance_id:
            raise osv.except_osv(_('Error'), _('Mission stock report cannot be available if no instance was set on the company !'))

        local_id = self.pool.get('stock.mission.report').search(cr, uid, [('local_report', '=', True), ('full_view', '=', False)], context=context)
        if local_id:
            res['report_id'] = local_id[0]
            report = self.pool.get('stock.mission.report').browse(cr, uid, local_id[0], context=context)
            res['last_update'] = report.last_update
            progress_state, start_date = self._get_progression_state(cr, uid, local_id[0], context=context)
            if progress_state == 'in_progress':
                res['processed_start_date'] = start_date
            res['export_ok'] = report.export_ok and progress_state == 'done'
            res['export_error_msg'] = report.export_error_msg
            res['processed_state'] = progress_state

        res['instance_level'] = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id.level
        return res

    def report_change(self, cr, uid, ids, report_id, context=None):
        if isinstance(report_id, list):
            report_id = report_id[0]

        v = {}
        if report_id:
            report = self.pool.get('stock.mission.report').browse(cr, uid, report_id, context=context)

            progress_state, start_date = self._get_progression_state(cr, uid, report_id, context=context)
            v.update({
                'last_update': report.last_update,
                'export_ok': report.export_ok and progress_state == 'done',
                'export_error_msg': report.export_error_msg,
                'processed_state': progress_state,
                'local_report': report.local_report,
                'full_view': report.full_view,
            })
            if progress_state == 'in_progress':
                v.update({'processed_start_date': start_date})
        else:
            v.update({'last_update': False, 'export_ok': False, 'processed_state': 'no_report_selected'})

        return {'value': v}

    def open_products_view(self, cr, uid, ids, context=None):
        '''
        Open the product list with report information
        '''
        if isinstance(ids, list):
            ids = ids[0]

        if not context:
            context = {}

        wiz_id = self._check_status(cr, uid, ids, context=context)

        c = context.copy()
        c.update({
            'mission_report_id': wiz_id.report_id.id,
            'with_valuation': wiz_id.with_valuation == 'true',
            'hide_amc_fmc': wiz_id.report_id.full_view and (self.pool.get('res.users').browse(cr, uid, uid, c).company_id.instance_id.level in ['section', 'coordo']),
        })
        display_only_in_stock = wiz_id.display_only_in_stock == 'true'
        if display_only_in_stock:
            domain = ['&',
                      ('mission_report_id', '=', wiz_id.report_id.id),
                      '|', '|', '|', '|', '|', '|', '|', '|', '|', '|',
                      ('internal_qty', '!=', 0),
                      ('wh_qty', '!=', 0),
                      ('cross_qty', '!=', 0),
                      ('secondary_qty', '!=', 0),
                      ('eprep_qty', '!=', 0),
                      ('cu_qty', '!=', 0),
                      ('in_pipe_qty', '!=', 0),
                      ('stock_qty', '!=', 0),
                      ('quarantine_qty', '!=', 0),
                      ('input_qty', '!=', 0),
                      ('opdd_qty', '!=', 0)]
        else:
            domain = [('mission_report_id', '=', wiz_id.report_id.id)]

        return {'type': 'ir.actions.act_window',
                'name': '%s: %s' % (_('Mission Stock Report'), wiz_id.report_id.name),
                'res_model': 'stock.mission.report.line',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'domain': domain,
                'context': c,
                'target': 'current'}

    def go_previous(self, cr, uid, ids, context=None):
        context = context or {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        return {'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'target': 'new',
                'context': context}

    def _check_status(self, cr, uid, ids, context=None):
        '''
        Check if the wizard is linked to a report and if the report is available
        '''
        if not ids:
            raise osv.except_osv(
                _('Error'),
                _('You should choose a report to display.'),
            )

        wiz_id = self.browse(cr, uid, ids, context=context)
        if not wiz_id.report_id:
            raise osv.except_osv(
                _('Error'),
                _('You should choose a report to display.'),
            )
        if not wiz_id.report_id.last_update:
            raise osv.except_osv(
                _('Error'),
                _("""The generation of this report is in progress. You could open this
report when the last update field will be filled. Thank you for your comprehension."""),
            )

        return wiz_id

    def open_xls_file(self, cr, uid, ids, context=None):
        return self.open_file(cr, uid, ids, file_format='xls', context=context)

    def open_csv_file(self, cr, uid, ids, context=None):
        return self.open_file(cr, uid, ids, file_format='csv', context=context)

    def open_consolidated_xls(self, cr, uid, ids, context=None):
        instance_name = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.name

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'stock.mission.report_xls',
            'datas': {
                'file_name': 'consolidate_mission_stock.xls',
                'file_format': 'xls',
                'target_filename': _('Consolidated_Mission_Stock_Report_%s_%s') % (instance_name, time.strftime('%Y%m%d_%H%M%S'))
            },
            'nodestroy': True,
            'context': context,
        }

    def open_file(self, cr, uid, ids, file_format='xls', context=None):
        '''
        Open the file
        '''
        if isinstance(ids, list):
            ids = ids[0]

        if not context:
            context = {}

        self._check_status(cr, uid, ids, context=context)

        datas = {'ids': ids}

        # add the requested field name and report_id to the datas
        # to be used later on in the stock_mission_report_xls_parser
        ftf = ['with_valuation', 'report_id', 'display_only_in_stock', 'fname', 'local_report']
        res = self.read(cr, uid, ids, ftf, context=context)

        field_name = None
        if res['with_valuation'] == 'true':
            if res['local_report']:
                field_name = 's_v_mml_vals'
            else:
                field_name = 's_v_vals'
        elif res['with_valuation'] == 'false':
            if res['local_report']:
                field_name = 's_nv_mml_vals'
            else:
                field_name = 's_nv_vals'

        datas.update({
            'field_name': field_name,
            'report_id': res['report_id'],
            'file_format': file_format,
            'display_only_in_stock': (res['display_only_in_stock'] == 'true'),
            'target_filename': res['fname'],
        })

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'stock.mission.report_xls',
            'datas': datas,
            'nodestroy': True,
            'context': context,
        }

    def update(self, cr, uid, ids, context=None):
        msr_obj = self.pool.get('stock.mission.report')
        ids = msr_obj.search(cr, uid, [], context=context)
        return msr_obj.background_update(cr, uid, ids, context=context)

mission_stock_wizard()
