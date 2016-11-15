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
from tools.translate import _

import time
from time import strftime
from time import strptime

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

    def _check_period_state(self, cr, uid, period, instance, context=None):
        '''
        Check that the selected instance is Mission-Closed for the selected period
        '''
        if context is None:
            context = {}
        if not period:
            raise osv.except_osv(_('Warning!'), _('You must select a period.'))
        elif not instance:
            raise osv.except_osv(_('Warning!'), _('You must select a proprietary instance.'))
        period_state_obj = self.pool.get('account.period.state')
        domain = [
            ('instance_id', '=', instance.id),
            ('period_id', '=', period.id),
            ('state', '=', 'mission-closed'),
        ]
        if not period_state_obj.search_exist(cr, uid, domain, context=context):
            raise osv.except_osv(_('Warning!'), _('The selected instance must be Mission-Closed.'))

    def button_ocp_export_to_hq(self, cr, uid, ids, context=None):
        """
        Launch a report to generate the ZIP file.
        """
        if context is None:
            context = {}
        wizard = self.browse(cr, uid, ids[0], context=context)
        data = {}
        data['form'] = {}
        inst = None
        period = None
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
        # Check that the export is run at HQ level
        user_obj = self.pool.get('res.users')
        company = user_obj.browse(cr, uid, uid).company_id
        if company.instance_id.level != 'section':
            raise osv.except_osv(_('Warning!'), _('The report can be run at HQ level only.'))
        # Check that the period state is ok
        self._check_period_state(cr, uid, period, inst, context)
        # The file name is composed of:
        # - the first 3 digits of the Prop. Instance code
        # - the year and month of the selected period
        # - the current datetime
        # Ex: KE1_201609_171116110306_Monthly Export
        instance_code = inst and inst.code[:3] or ''
        selected_period = period and strftime('%Y%m', strptime(period.date_start, '%Y-%m-%d')) or ''
        current_time = time.strftime('%d%m%y%H%M%S')
        data['target_filename'] = '%s_%s_%s_Monthly Export' % (instance_code, selected_period, current_time)
        return {'type': 'ir.actions.report.xml', 'report_name': 'hq.ocp', 'datas': data}

ocp_export_wizard()
