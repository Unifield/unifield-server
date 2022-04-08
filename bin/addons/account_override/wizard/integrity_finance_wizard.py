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
        'filter': fields.selection([
            ('filter_no', 'No Filters'),
            ('filter_date_doc', 'Document Date'),
            ('filter_date', 'Posting Date'),
            ('filter_period', 'Period')
        ], "Filter by", required=True),
        'period_from': fields.many2one('account.period', 'Start period'),
        'period_to': fields.many2one('account.period', 'End period'),
        'date_from': fields.date("Start date"),
        'date_to': fields.date("End date"),
        'instance_ids': fields.many2many('msf.instance', 'integrity_finance_wizard_instance_rel',
                                         'wizard_id', 'instance_id',
                                         string='Proprietary Instances'),
        'move_state': fields.selection([('posted', 'Posted'), ('draft', 'Unposted')], string="Entry Status"),
    }

    _defaults = {
        'filter': 'filter_no',
    }

    def onchange_filter(self, cr, uid, ids, filter, context=None):
        """
        Adapts the date/period filter according to the selection made in "Filter by"
        """
        res = {}
        if filter == 'filter_no':
            res['value'] = {'period_from': False, 'period_to': False, 'date_from': False, 'date_to': False}
        elif filter in ('filter_date', 'filter_date_doc', ):
            res['value'] = {'period_from': False, 'period_to': False}
        elif filter == 'filter_period':
            res['value'] = {'date_from': False, 'date_to': False}
        return res

    def onchange_fiscalyear_id(self, cr, uid, ids, fiscalyear_id, context=None):
        """
        (Only) if a FY is selected: resets the periods selected and restricts their domain to within the FY
        """
        res = {}
        if fiscalyear_id:
            res = {
                'value': {
                    'period_from': False,
                    'period_to': False,
                },
                'domain': {
                    'period_from': [('fiscalyear_id', '=', fiscalyear_id)],
                    'period_to': [('fiscalyear_id', '=', fiscalyear_id)],
                }
            }
        return res

    def print_integrity_finance_report(self, cr, uid, ids, context=None):
        """
        Prints the "Entries Data Integrity" report
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        user_obj = self.pool.get('res.users')
        wiz = self.browse(cr, uid, ids[0], context=context)
        data = {
            'form': {},
            'context': context,
        }
        # store the selected criteria
        data['form'].update({
            'fiscalyear_id': wiz.fiscalyear_id and wiz.fiscalyear_id.id or False,
            'filter': wiz.filter,
            'period_from': wiz.period_from and wiz.period_from.id or False,
            'period_to': wiz.period_to and wiz.period_to.id or False,
            'date_from': wiz.date_from or False,
            'date_to': wiz.date_to or False,
            'instance_ids': wiz.instance_ids and [inst.id for inst in wiz.instance_ids],
            'move_state': wiz.move_state or '',
        })
        company = user_obj.browse(cr, uid, uid, fields_to_fetch=['company_id'], context=context).company_id
        current_instance = company.instance_id and company.instance_id.code or ''
        current_date = datetime.today()
        data['target_filename'] = "%s %s %s" % (_('Entries Data Integrity'), current_instance, current_date.strftime('%Y%m%d'))
        selected_fisc = ''
        if wiz.fiscalyear_id:
            selected_fisc = wiz.fiscalyear_id.name or ''
        data['selected_fisc'] = selected_fisc
        filter_used = _('No Filters')
        if wiz.filter == 'filter_date_doc' or wiz.filter == 'filter_date':
            data['date_from'] = datetime.strptime(wiz.date_from, '%Y-%m-%d').strftime('%d/%m/%Y')
            data['date_to'] = datetime.strptime(wiz.date_to, '%Y-%m-%d').strftime('%d/%m/%Y')
            if wiz.filter == 'filter_date_doc':
                filter_used = _('Document Date')
            if wiz.filter == 'filter_date':
                filter_used = _('Posting Date')
        elif wiz.filter == 'filter_period':
            filter_used = _('Period')
            period_from = wiz.period_from.name or ''
            period_to = wiz.period_to.name or ''
            data['period_from'] = period_from
            data['period_to'] = period_to
        data['filter_used'] = filter_used
        entry_status = ''
        if wiz.move_state == 'posted':
            entry_status = _('Posted')
        elif wiz.move_state == 'draft':
            entry_status = _('Unposted')
        data['entry_status'] = entry_status
        data['reportdate'] = current_date.strftime('%d/%m/%Y')
        selected_instances = company.instance_id.code or ''
        if wiz.instance_ids:
            selected_instances = ', '.join([inst.name for inst in wiz.instance_ids])
        data['selected_instances'] = selected_instances

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'integrity.finance',
            'datas': data,
            'context': context,
        }


integrity_finance_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
