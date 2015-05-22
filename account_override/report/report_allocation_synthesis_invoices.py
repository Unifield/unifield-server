# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2015 MSF, TeMPO Consulting
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


class report_allocation_synthesis_invoices(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_allocation_synthesis_invoices, self).__init__(cr, uid, name, context=context)

        self._cr = cr

        self.localcontext.update({
            'title': self.get_title,
            'get_data': self.get_data,
            'level': self.get_level,
        })

    def get_data(self, invoice_id):
        self._cr.execute(""" WITH t as (
            SELECT ac.code as L1, n2.code as L2,
            ROUND(SUM(price_subtotal*percentage/100), 2) as amount
            FROM funding_pool_distribution_line a
            INNER JOIN account_invoice_line i ON a.distribution_id = i.analytic_distribution_id
            INNER JOIN account_analytic_account n2 ON n2.id = a.cost_center_id
            INNER JOIN account_account ac ON ac.id = i.account_id
            WHERE i.invoice_id=%s
            GROUP BY ac.code, n2.code
            UNION ALL
            SELECT ac.code, n2.code, ROUND(SUM(price_subtotal*percentage/100), 2)
            FROM funding_pool_distribution_line a
            INNER JOIN account_invoice s ON s.analytic_distribution_id = a.distribution_id
            LEFT JOIN account_invoice_line i ON i.invoice_id = s.id AND i.analytic_distribution_id IS NULL
            INNER JOIN account_account ac ON ac.id = i.account_id
            INNER JOIN account_analytic_account n2 ON n2.id = a.cost_center_id
            WHERE s.id=%s
            GROUP BY ac.code, n2.code)
            SELECT L1,L2, amount FROM t
            UNION ALL
            SELECT L1,'',SUM(amount) FROM t
            GROUP BY L1
            UNION ALL
            SELECT NULL,'',SUM(amount) FROM t
            ORDER BY L1,L2""", (invoice_id, invoice_id))

        return self._cr.fetchall()

    def get_level(self, row):
        if row[0] is None:
            return -1
        elif row[1] == '':
            return 1
        else:
            return 2

    def get_title(self, invoice):

        invoice_types = {
            'out_invoice': 'Customer Invoice',
            'in_invoice': 'Supplier Invoice',
            'out_refund': 'Customer Refund',
            'in_refund': 'Supplier Refund'
            }

        return invoice_types[invoice.type]


SpreadsheetReport('report.allocation.synthesis.invoices', 'account.invoice', 'addons/account_override/report/allocation_synthesis_invoices_xls.mako', parser=report_allocation_synthesis_invoices)
