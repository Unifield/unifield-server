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

import time
from time import strftime
from time import strptime


class ocp_matching_export_wizard(osv.osv_memory):
    _name = 'ocp.matching.export.wizard'

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Top proprietary instance', required=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal year', required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True),
    }

    _defaults = {
        'fiscalyear_id': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, strftime('%Y-%m-%d'), context=c),
    }

    def button_ocp_matching_export(self, cr, uid, ids, context=None):
        """
        Launch a report to generate the ZIP file.
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        wizard = self.browse(cr, uid, ids[0], context=context)
        data = {}
        data['form'] = {}
        if wizard.instance_id:
            # Get projects below instance
            inst = wizard.instance_id
            data['form'].update({'instance_id': inst.id, })
            data['form'].update(
                {'instance_ids': [inst.id] + [x.id for x in inst.child_ids]})
        if wizard.period_id:
            period = wizard.period_id
            data['form'].update({'period_id': period.id})
        if wizard.fiscalyear_id:
            data['form'].update({'fiscalyear_id': wizard.fiscalyear_id.id})
        # The file name is composed of:
        # - the first 3 digits of the Prop. Instance code
        # - the year and month of the selected period
        # - the current datetime
        # Ex: KE1_201610_171116110306_Check_on_reconcilable_entries
        instance_code = inst and inst.code[:3] or ''
        selected_period = period and strftime('%Y%m', strptime(period.date_start, '%Y-%m-%d')) or ''
        current_time = time.strftime('%d%m%y%H%M%S')
        data['target_filename'] = '%s_%s_%s_Check_on_reconcilable_entries' % (instance_code, selected_period, current_time)

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': data['target_filename'],
            'report_name': 'hq.ocp.matching',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 2

        data['context'] = context
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'hq.ocp.matching',
            'datas': data,
            'context': context,
        }

ocp_matching_export_wizard()
