# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from osv import fields
from osv import osv
from account_override import finance_export

from time import strftime
from time import strptime

import netsvc
import base64

from . import wizard_hq_report_oca


class finance_hq_vi(osv.osv_memory):
    _name = 'finance.hq.vi'
    _columns = {
    }

    def get_ocb_export(self, cr, uid, instance_code, period_name, all_lines=True, context=None):
        if context is None:
            context = {}
        if not context.get('lang'):
            context['lang'] = 'en_MF'

        context['poc_export'] = True

        result = {
            'error': '',
            'success': False,
            'start_date': strftime('%Y-%m-%d %H:%M'),
            'content': '',
            'filename': '',
        }

        period_obj = self.pool.get('account.period')
        p_ids = period_obj.search(cr ,uid, [('name', '=ilike', period_name)], context=context)
        if not p_ids:
            result.update({'error': 'Period name %s not found' % (period_name, ), 'end_date': strftime('%Y-%m-%d %H:%M')})
            return result

        instance_ids = self.pool.get('msf.instance').search(cr, uid, [('code', '=ilike', instance_code), ('level', 'in', ['section', 'coordo'])], context=context)
        if not instance_ids:
            result.update({'error': 'No section/coordo instance code found for %s' % (instance_code,), 'end_date': strftime('%Y-%m-%d %H:%M')})
            return result


        p = period_obj.browse(cr, uid, p_ids[0], fields_to_fetch=['fiscalyear_id'], context=context)
        if not period_obj.search_exists(cr, uid, [('id', '=', p_ids[0]), ('child_mission_hq_closed', '=', [instance_ids[0], p.fiscalyear_id.id]), ('number', '<', 16)], context=context):
            result.update({'error': 'Period %s is not Mission-Closed or HQ-Closed' % (period_name,), 'end_date': strftime('%Y-%m-%d %H:%M')})
            return result

        wiz_id = self.pool.get('ocb.export.wizard').create(cr, uid, {
            'instance_id': instance_ids[0],
            'fiscalyear_id': p.fiscalyear_id.id,
            'period_id': p_ids[0],
            'selection': 'all' if all_lines else 'unexported',
        }, context=context)

        r_data = self.pool.get('ocb.export.wizard').button_export(cr, uid, wiz_id, context=context)
        obj = netsvc.LocalService('report.%s' % r_data['report_name'])
        content, file_format = obj.create(cr, uid, [], r_data['datas'], context=context)
        result.update({'content': base64.b64encode(content).decode('utf8'), 'success': True, 'end_date': strftime('%Y-%m-%d %H:%M'), 'filename': '%s.%s' % (r_data['datas'].get('target_filename'), file_format)})
        return result

    def get_ocb_matching_export(self, cr, uid, instance_code, period_name, context=None):
        if context is None:
            context = {}
        if not context.get('lang'):
            context['lang'] = 'en_MF'

        result = {
            'error': '',
            'success': False,
            'start_date': strftime('%Y-%m-%d %H:%M'),
            'content': '',
            'filename': '',
        }

        context['poc_export'] = True
        context['ocb_matching'] = True


        period_obj = self.pool.get('account.period')
        p_ids = period_obj.search(cr ,uid, [('name', '=ilike', period_name), ('state', '!=', 'created'), ('number', '<', 16)], context=context)
        if not p_ids:
            result.update({'error': 'Period name %s not found' % (period_name,), 'end_date': strftime('%Y-%m-%d %H:%M')})
            return result


        instance_ids = self.pool.get('msf.instance').search(cr, uid, [('code', '=ilike', instance_code), ('level', '=', 'coordo')], context=context)
        if not instance_ids:
            result.update({'error': 'No coordo instance code found for %s' % (instance_code,), 'end_date': strftime('%Y-%m-%d %H:%M')})
            return result


        p = period_obj.browse(cr, uid, p_ids[0], fields_to_fetch=['fiscalyear_id'], context=context)

        wiz_id = self.pool.get('ocp.matching.export.wizard').create(cr, uid, {
            'instance_id': instance_ids[0],
            'fiscalyear_id': p.fiscalyear_id.id,
            'period_id': p_ids[0],
        }, context=context)

        r_data = self.pool.get('ocp.matching.export.wizard').button_ocp_matching_export(cr, uid, wiz_id, context=context)
        obj = netsvc.LocalService('report.%s' % r_data['report_name'])
        content, file_format = obj.create(cr, uid, [], r_data['datas'], context=context)
        result.update({'content': base64.b64encode(content).decode('utf8'), 'success': True, 'end_date': strftime('%Y-%m-%d %H:%M'), 'filename': '%s.%s' % (r_data['datas'].get('target_filename'), file_format)})
        return result


finance_hq_vi()


class ocb_export_wizard(osv.osv_memory):
    _name = "ocb.export.wizard"

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Top proprietary instance', required=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal year', required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True),
        'selection': fields.selection([('all', 'All lines'), ('unexported', 'Not yet exported')], string="Select", required=True),
    }

    _defaults = {
        'fiscalyear_id': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, strftime('%Y-%m-%d'), context=c),
        'selection': lambda *a: 'all',
    }

    def onchange_instance_id(self, cr, uid, ids, context=None):
        return {'value': {'period_id': False}}

    def _prepare_report(self, cr, uid, ids, report_name, report_file_name, context=None):
        """
        Launch a report to generate the ZIP file.
        """
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        # Prepare some values
        wizard = self.browse(cr, uid, ids[0], context=context)
        data = {}
        # add parameters
        data['form'] = {}
        if wizard.instance_id:
            # Get projects below instance
            data['form'].update({'instance_id': wizard.instance_id.id,})
            data['form'].update({'instance_ids': [wizard.instance_id.id] + [x.id for x in wizard.instance_id.child_ids]})
        if wizard.period_id:
            data['form'].update({'period_id': wizard.period_id.id})
        if wizard.fiscalyear_id:
            data['form'].update({'fiscalyear_id': wizard.fiscalyear_id.id})
        data['form'].update({'selection': wizard.selection})

        data['target_filename'] = report_file_name

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': data['target_filename'],
            'report_name': report_name,
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 2

        finance_export.log_vi_exported(self, cr, uid, report_name, wizard.id, data['target_filename'])

        data['context'] = context
        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': data,
            'context': context,
        }

    def button_export(self, cr, uid, ids, context=None):
        report_name = 'hq.ocb'
        period_name = ''
        wizard = self.browse(cr, uid, ids[0], context=context)
        if wizard.period_id:
            period_name = strftime('%Y%m', strptime(wizard.period_id.date_start, '%Y-%m-%d'))

        report_file_name = '%s_%s_formatted data UF to OCB HQ system' % (
            wizard.instance_id and wizard.instance_id.code or '',
            period_name
        )
        return self._prepare_report(cr, uid, ids, report_name, report_file_name, context)

ocb_export_wizard()

class ubuntu_export_wizard(wizard_hq_report_oca.wizard_export_vi_finance):
    _name = 'ubuntu.export.wizard'
    _inherit = 'ocb.export.wizard'

    def button_export(self, cr, uid, ids, context=None):
        report_name = 'hq.ubuntu'
        period_name = ''
        wizard = self.browse(cr, uid, ids[0], context=context)
        if wizard.period_id:
            dt = strptime(wizard.period_id.date_start, '%Y-%m-%d')
            period_name = '%sP%02d' % (strftime('%Y', dt), wizard.period_id.number)
        report_file_name = '%s_%s_formatted data D365 import.zip' % (
            wizard.instance_id and wizard.instance_id.code[0:3] or '',
            period_name
        )
        return self._prepare_report(cr, uid, ids, report_name, report_file_name, context)

ubuntu_export_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
