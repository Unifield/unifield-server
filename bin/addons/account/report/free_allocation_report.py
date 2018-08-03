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

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class free_allocation_report(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(free_allocation_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'lines': self._get_lines,
        })

    def _get_lines(self, data):
        """
        Returns the report lines as a list of dicts
        """
        res = []
        move_obj = self.pool.get('account.move')
        context = data.get('context', {})
        account_ids = data.get('account_ids', [])
        cost_center_ids = data.get('cost_center_ids', [])
        free1_ids = data.get('free1_ids', [])
        free2_ids = data.get('free2_ids', [])
        dom = []
        if data.get('fiscalyear_id', False):
            dom.append(('fiscalyear_id', '=', data['fiscalyear_id']))
        if data.get('period_id', False):
            dom.append(('period_id', '=', data['period_id']))
        if data.get('document_date_from', False):
            dom.append(('document_date', '>=', data['document_date_from']))
        if data.get('document_date_to', False):
            dom.append(('document_date', '<=', data['document_date_to']))
        if data.get('posting_date_from', False):
            dom.append(('date', '>=', data['posting_date_from']))
        if data.get('posting_date_to', False):
            dom.append(('date', '<=', data['posting_date_to']))
        if data.get('instance_id', False):
            dom.append(('instance_id', '=', data['instance_id']))
        if data.get('journal_ids', []):
            dom.append(('journal_id', 'in', data['journal_ids']))
        # get the JE matching the criteria sorted by Entry Sequence
        move_ids = move_obj.search(self.cr, self.uid, dom, order='name', context=context)
        return res


SpreadsheetReport('report.free.allocation.report.xls', 'account.analytic.line',
                  'addons/account/report/free_allocation_report.mako', parser=free_allocation_report)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
