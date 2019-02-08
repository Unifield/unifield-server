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

from osv import fields, osv
from tools.translate import _
assert _ # pyflakes
import time
from time import strptime


class wizard_hq_report_oca(osv.osv_memory):
    _name = "wizard.hq.report.oca"

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Top proprietary instance', required=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal year', required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True),
        'selection': fields.selection([('all', 'All lines'), ('unexported', 'Not yet exported')], string="Select", required=True),
    }

    _defaults = {
        'fiscalyear_id': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, time.strftime('%Y-%m-%d'), context=c),
        'selection': lambda *a: 'all',
    }

    def onchange_instance_id(self, cr, uid, ids, context=None):
        '''
        (US-226) Reset the period field when another prop. instance is selected.
        Cover the case when in HQ the user selects a period mission-closed in a coordo,
        and then select another coordo in which the period previously selected is not mission-closed
        '''
        res = {}
        res['value'] = {'period_id': False}
        return res

    def button_create_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        wizard = self.browse(cr, uid, ids[0], context=context)
        data = {}
        # add parameters
        data['form'] = {}
        mission_code = ''
        year = ''
        period_number = ''
        if wizard.instance_id:
            mission_code = "%s0" % wizard.instance_id.code[:2]
            # Get projects below instance
            data['form'].update({'instance_ids': [wizard.instance_id.id] + [x.id for x in wizard.instance_id.child_ids]})
        if wizard.period_id:
            tm = strptime(wizard.period_id.date_start, '%Y-%m-%d')
            year = str(tm.tm_year)
            period_number = wizard.period_id.number and '%02d' % wizard.period_id.number or ''
            data['form'].update({'period_id': wizard.period_id.id})
        # UFTP-375: Permit user to select all lines or only previous ones
        data['form'].update({'selection': wizard.selection})
        data['target_filename'] = '%s_%sP%s_formatted data D365 import' % (mission_code, year, period_number)

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': data['target_filename'],
            'report_name': 'hq.oca',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 2

        data['context'] = context
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'hq.oca',
            'datas': data,
            'context': context,
        }

wizard_hq_report_oca()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
