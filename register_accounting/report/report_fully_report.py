# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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
import pooler

class report_fully_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_fully_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getInvoiceLines': self.getLines,
            'getDirectInvoiceLines': self.getDirectInvoiceLines,
            'getAnalyticLines': self.getAnalyticLines,
        })
        return

    def getLines(self, invoice_ids):
        """
        Fetch invoice lines and tax lines (if exists)
        """
        # Prepare some value
        res = []
        # Do not check lines if no invoice given
        if not invoice_ids:
            return res
        if isinstance(invoice_ids, (int, long)):
            invoice_ids = [invoice_ids]
        for invoice in pooler.get_pool(self.cr.dbname).get('account.invoice').browse(self.cr, self.uid, invoice_ids):
            if invoice.invoice_line:
                res += [x for x in invoice.invoice_line]
            if invoice.tax_line:
                res += [x for x in invoice.tax_line]
        return res

    def getDirectInvoiceLines(self, move_ids):
        """
        Fetch all lines except the partner counterpart one
        """
        res = []
        if not move_ids:
            return res
        if isinstance(move_ids, (int, long)):
            move_ids = [move_ids]
        # We need move lines linked to the given move ID. Except the invoice counterpart.
        #+ Lines that have is_counterpart to True is the invoice counterpart. We do not need it.
        aml_obj = pooler.get_pool(self.cr.dbname).get('account.move.line')
        aml_ids = aml_obj.search(self.cr, self.uid, [('move_id', 'in', move_ids), ('is_counterpart', '=', False)])
        if aml_ids:
            res = aml_obj.browse(self.cr, self.uid, aml_ids)
        return sorted(res, key=lambda x: x.line_number)

    def getAnalyticLines(self, analytic_ids):
        """
        Get anlytic lines history from given analytic lines
        """
        res = []
        if not analytic_ids:
            return res
        if isinstance(analytic_ids, (int, long)):
            analytic_ids = [analytic_ids]
        al_obj = pooler.get_pool(self.cr.dbname).get('account.analytic.line')
        al_ids = al_obj.get_corrections_history(self.cr, self.uid, analytic_ids)
        if al_ids:
            res = al_obj.browse(self.cr, self.uid, al_ids)
        return res

SpreadsheetReport('report.fully.report','account.bank.statement','addons/register_accounting/report/fully_report_xls.mako', parser=report_fully_report)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
