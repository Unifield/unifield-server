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

class wizard_hq_report_ocg(osv.osv_memory):
    _name = "wizard.hq.report.ocg"

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Top proprietary instance', required=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal year', required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True)
    }

    _defaults = {
        'fiscalyear_id': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, time.strftime('%Y-%m-%d'), context=c)
    }

    def onchange_instance_id(self, cr, uid, ids, context=None):
        """
        Resets the period field when another prop. instance is selected.
        Covers the case when in HQ the user selects a period closed in a coordo,
        and then select another coordo in which the period previously selected is not closed
        """
        return {'value': {'period_id': False}}

    def button_create_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        wizard = self.browse(cr, uid, ids[0], context=context)
        data = {}
        # add parameters
        data['form'] = {}
        if wizard.instance_id:
            # Get projects below instance
            data['form'].update({'instance_ids': [wizard.instance_id.id] + [x.id for x in wizard.instance_id.child_ids]})
        period_name = ''
        if wizard.period_id:
            data['form'].update({'period_id': wizard.period_id.id})
            period_name = time.strftime('%Y%m', time.strptime(wizard.period_id.date_start, '%Y-%m-%d'))

        data['target_filename'] = '%s_%s_formatted data AX import' % (wizard.instance_id and wizard.instance_id.code[0:3] or '', period_name)
        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': data['target_filename'],
            'report_name': 'hq.ocg',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 2

        data['context'] = context
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'hq.ocg',
            'datas': data,
            'context': context,
        }

wizard_hq_report_ocg()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
