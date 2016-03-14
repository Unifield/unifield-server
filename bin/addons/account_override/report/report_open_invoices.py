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
            'getConvert':self.getConvert,
            'getFuncCur':self.getFuncCur,
            'invoices': self.get_invoices(cr, uid, context)
        })
        return

    def get_invoices(self, cr, uid, context):
        """
        Get only open invoices
        """
        res = {}
        for option_type in ['out_invoice', 'in_invoice', 'out_refund', 'in_refund']:
            type_ids = self.pool.get('account.invoice').search(cr, uid, [('state', '=', 'open'), ('type', '=', option_type)], context=context)
            if isinstance(type_ids, (int, long)):
                type_ids = [type_ids]
            res.update({option_type: self.pool.get('account.invoice').browse(cr, uid, type_ids, context)})
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
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
