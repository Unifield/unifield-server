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

class ocp_export_wizard(osv.osv_memory):
    _name = "ocp.export.wizard"

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Top proprietary instance', required=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal year', required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True),
    }

    _defaults = {
        'fiscalyear_id': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, strftime('%Y-%m-%d'), context=c),
    }

    def button_export_ocp(self, cr, uid, ids, context=None):
        """
        Launch a report to generate the ZIP file.
        """
        if context is None:
            context = {}
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
            data['form'].update({'period_id': wizard.period_id.id})
        if wizard.fiscalyear_id:
            data['form'].update({'fiscalyear_id': wizard.fiscalyear_id.id})
        # First 3 digits of the Prop. Instance code (OCP_ABCDE => ABC):
        instance_code = inst and '_' in inst.code and inst.code.split('_')[1][:3] or ''
        target_file_name_pattern = '%s_%s_Monthly Export'
        data['target_filename'] = target_file_name_pattern % (instance_code, time.strftime('%Y%m'))
        return {'type': 'ir.actions.report.xml', 'report_name': 'hq.ocp', 'datas': data}

ocp_export_wizard()
