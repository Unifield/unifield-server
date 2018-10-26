# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2018 TeMPO Consulting, MSF. All Rights Reserved
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

from datetime import datetime


class integrity_finance_wizard(osv.osv_memory):
    _name = 'integrity.finance.wizard'

    _columns = {
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal year'),
    }

    def print_integrity_finance_report(self, cr, uid, ids, context=None):
        """
        Prints the "Entries Data Integrity" report
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        user_obj = self.pool.get('res.users')
        wiz = self.browse(cr, uid, ids[0], fields_to_fetch=['fiscalyear_id'], context=context)
        data = {
            'form': {},
            'context': context,
        }
        # get the selected fiscal year
        data['form'].update({
            'fiscalyear_id': wiz.fiscalyear_id and wiz.fiscalyear_id.id or False,
        })
        company = user_obj.browse(cr, uid, uid, fields_to_fetch=['company_id'], context=context).company_id
        current_instance = company.instance_id and company.instance_id.code or ''
        current_date = datetime.today().strftime('%Y%m%d')
        data['target_filename'] = "%s %s %s" % (_('Entries Data Integrity'), current_instance, current_date)
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'integrity.finance',
            'datas': data,
            'context': context,
        }


integrity_finance_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
