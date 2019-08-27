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
    def __init__(self, cr, uid, name, context=None):
        super(report_open_invoices2, self).__init__(cr, uid, name, context=context)
        self.funcCur = ''
        self.localcontext.update({
            'getLines':self.getLines,
            'getConvert':self.getConvert,
            'getFuncCur':self.getFuncCur,
        })
        return

    def getLines(self,option):
        result = []
        sql_request = """
            SELECT DISTINCT invoice.id, invoice.document_date, invoice.date_invoice, move.name,
                            partner.name, invoice.name, responsible.name,
                            invoice.date_due, invoice.origin,
                            currency.name, invoice.residual,
                            invoice.amount_total, invoice.state,
                            currency.id
            FROM
                account_invoice invoice
                LEFT JOIN account_move move ON invoice.move_id = move.id
                LEFT JOIN res_partner partner ON invoice.partner_id = partner.id
                LEFT JOIN res_users responsible ON invoice.user_id = responsible.id
                LEFT JOIN res_currency currency ON invoice.currency_id = currency.id
            WHERE
                invoice.state NOT IN ('paid', 'inv_close', 'cancel') AND
                invoice.type = %s
            ORDER BY invoice.date_invoice
        """

        option_type = {'ci': 'out_invoice', 'si': 'in_invoice', 'cr': 'out_refund', 'sr': 'in_refund'}
        if option_type.get(option):
            self.cr.execute(sql_request, (option_type[option], ))
            result = self.cr.fetchall()

        return result

    def getConvert(self, amount, line):
        company = self.localcontext['company']
        func_cur_id = company and company.currency_id and company.currency_id.id or False
        conv = self.pool.get('res.currency').compute(self.cr, self.uid, line[13], func_cur_id, amount or 0.0, round=True)
        return conv

    def getFuncCur(self, ):
        company = self.localcontext['company']
        return company and company.currency_id and company.currency_id.name or ''


SpreadsheetReport('report.open.invoices.2','account.invoice','addons/account_override/report/open_invoices_xls.mako', parser=report_open_invoices2)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
