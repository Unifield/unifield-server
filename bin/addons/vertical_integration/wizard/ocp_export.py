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
from tools.translate import _
from account_override import finance_export

import time
from time import strftime
from time import strptime

#from . import wizard_export_vi_finance
from . import wizard_hq_report_oca

class ocp_export_wizard(wizard_hq_report_oca.wizard_export_vi_finance):
    _name = "ocp.export.wizard"
    _export_filename = '{instance}_Y{year}P{month:02d}_formatted_data_workday_{date}.zip'
    _export_report_name = 'report.hq.ocp.workday'
    _export_extra_data = {
        'export_type': 'workday'
    }

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Top proprietary instance'),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal year', required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True),
        'all_missions': fields.boolean('All Missions', help="Generate the Monthly Export (only) for all missions at once"),
        # a warning is displayed in case the DB name is not "OCP_HQ" (export done from a coordo or from a test environment),
        # as this impacts the DB ID column
        'warning_db_name': fields.boolean('Display a warning on database name', invisible=True, readonly=True),
        'export_type': fields.selection([('arcole', 'Arcole'), ('workday', 'Workday')], string='export type', readonly=True),
    }

    _defaults = {
        'fiscalyear_id': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, strftime('%Y-%m-%d'), context=c),
        'all_missions': False,
        'warning_db_name': lambda self, cr, uid, c: cr.dbname != 'OCP_HQ',
        'export_type': lambda self, cr, uid, c: c and c.get('export_type') or 'arcole',
    }

    def onchange_instance_id(self, cr, uid, ids, instance_id, context=None):
        """
        - Resets the period field when another prop. instance is selected.
          Covers the case when in HQ the user selects a period mission-closed in a coordo,
          and then select another coordo in which the period previously selected is not mission-closed.
        - Also resets the tick box "All Missions" as soon as a Prop. Instance is selected.
        """
        res = {}
        res['value'] = {'period_id': False}
        if instance_id:
            res['value'].update({'all_missions': False})
        return res

    def onchange_all_missions(self, cr, uid, ids, all_missions, context=None):
        """
        Resets the Prop. Instance field when "All Missions" is ticked
        """
        res = {}
        if all_missions:
            res['value'] = {'instance_id': False}
        return res

    def button_ocp_export_to_hq(self, cr, uid, ids, context=None):
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
        inst = None
        all_missions = False
        instance_ids = []
        period = None
        if wizard.all_missions:
            all_missions = True
            instance_ids = self.pool.get('msf.instance').search(cr, uid, [('level', '!=', 'section')], order='NO_ORDER', context=context)
        elif wizard.instance_id:
            # Get projects below instance
            inst = wizard.instance_id
            instance_ids = [inst.id] + [x.id for x in inst.child_ids]
        data['form'].update({
            'instance_id': inst and inst.id or None,
            'instance_ids': instance_ids,
            'all_missions': all_missions,
        })
        if wizard.period_id:
            period = wizard.period_id
            data['form'].update({'period_id': period.id})
        if wizard.fiscalyear_id:
            data['form'].update({'fiscalyear_id': wizard.fiscalyear_id.id})
        # The file name is composed of:
        # - the first 3 characters of the Prop. Instance code or "Allinstances"
        # - the year and month of the selected period
        # - the current datetime
        # Ex: KE1_201609_171116110306_Formatted_data_UF_to_OCP_HQ_System
        if all_missions:
            prefix = 'Allinstances'
        elif inst:
            prefix = inst.code[:3]
        else:
            prefix = ''
        selected_period = period and strftime('%Y%m', strptime(period.date_start, '%Y-%m-%d')) or ''
        current_time = time.strftime('%d%m%y%H%M%S')
        data['target_filename'] = '%s_%s_%s_Formatted_data_UF_to_OCP_HQ_System' % (prefix, selected_period, current_time)


        internal_report_name = 'hq.ocp'
        if wizard.export_type == 'workday':
            internal_report_name = 'hq.ocp.workday'

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': data['target_filename'],
            'report_name': internal_report_name,
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 2

        report_name = _("Export to HQ system (OCP)")
        finance_export.log_vi_exported(self, cr, uid, report_name, wizard.id, data['target_filename'])

        data['context'] = context
        return {
            'type': 'ir.actions.report.xml',
            'report_name': internal_report_name,
            'datas': data,
            'context': context,
        }

ocp_export_wizard()
