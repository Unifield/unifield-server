# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2013 MSF, TeMPO Consulting
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

from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from report import report_sxw


class report_open_invoices2(report_sxw.rml_parse):
    """
    Used for the reports "Open Invoices" and "Paid Invoices" (same display but the state of the docs displayed changes)
    """

    def __init__(self, cr, uid, name, context=None):
        if context is None:
            context = {}
        context.update({'paid_invoice': name == 'paid.invoices'})  # for the "Paid Invoices" report
        super(report_open_invoices2, self).__init__(cr, uid, name, context=context)
        self.percent = 0.0
        self.nb_lines = 0
        self.ratio_search = 0.25  # consider that the search in get_invoices takes 25% of the total time of the process
        self.funcCur = ''
        self.localcontext.update({
            'getConvert':self.getConvert,
            'getFuncCur':self.getFuncCur,
            'invoices': self.get_invoices,
            'update_percent': self.update_percent,
        })
        return

    def update_percent(self, current_line_position, context):
        """
        Update the percentage of the Report Generation
        """
        if context.get('background_id'):
            bg_obj = self.pool.get('memory.background.report')
            if current_line_position % 50 == 0:  # update percentage every 50 lines
                # self.ratio_search is the ratio already used for the search method
                self.percent = self.ratio_search + (current_line_position / float(self.nb_lines) * (1 - self.ratio_search))
                bg_obj.update_percent(self.cr, self.uid, [self.localcontext['background_id']], self.percent)

    def get_invoices(self, data):
        """
        Get only open invoices by default, or only paid invoices for the Paid Invoices Report
        """
        res = {}
        inv_obj = self.pool.get('account.invoice')
        bg_obj = self.pool.get('memory.background.report')
        beginning_date = data.get('form') and data['form'].get('beginning_date')
        ending_date = data.get('form') and data['form'].get('ending_date')
        context = self.localcontext or {}
        bg_id = False
        if context.get('background_id'):
            bg_id = context['background_id']
            self.percent = 0.05  # 5% of the process
            bg_obj.update_percent(self.cr, self.uid, [bg_id], self.percent)
        for option_type in ['out_invoice', 'in_invoice', 'out_refund', 'in_refund']:
            if context.get('paid_invoice') and beginning_date and ending_date:
                # paid invoices within the selected dates
                domain_paid_inv = [('state', '=', 'paid'),
                                   ('date_invoice', '>=', beginning_date),
                                   ('date_invoice', '<=', ending_date),
                                   ('type', '=', option_type)]
                type_ids = inv_obj.search(self.cr, self.uid, domain_paid_inv, context=context, order='move_name')
            else:
                # all open invoices
                domain_open_inv = [('state', '=', 'open'), ('type', '=', option_type)]
                type_ids = inv_obj.search(self.cr, self.uid, domain_open_inv, context=context)
            if isinstance(type_ids, (int, long)):
                type_ids = [type_ids]
            self.nb_lines += len(type_ids)
            res.update({option_type: inv_obj.browse(self.cr, self.uid, type_ids, context)})
        if bg_id:
            self.percent += 0.20  # 25% of the process
            bg_obj.update_percent(self.cr, self.uid, [bg_id], self.percent)
        return res

    def getConvert(self, amount, currency_id):
        company = self.localcontext['company']
        func_cur_id = company and company.currency_id and company.currency_id.id or False
        conv = self.pool.get('res.currency').compute(self.cr, self.uid, currency_id, func_cur_id, amount or 0.0, round=True)
        return conv

    def getFuncCur(self, ):
        company = self.localcontext['company']
        return company and company.currency_id and company.currency_id.name or ''


SpreadsheetReport('report.open.invoices.2','account.invoice','addons/account_override/report/open_invoices_xls.mako', parser=report_open_invoices2)
SpreadsheetReport('report.paid.invoices', 'account.invoice', 'addons/account_override/report/open_invoices_xls.mako', parser=report_open_invoices2)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
