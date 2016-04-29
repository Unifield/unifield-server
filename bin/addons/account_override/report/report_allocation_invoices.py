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

import time

from report import report_sxw


class allocation_invoice_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(allocation_invoice_report, self).__init__(cr, uid, name, context=context)

        self._cr = cr

        self.localcontext.update({
            'time': time,
            'get_data': self.get_data,
            'get_total_amount': self.get_total_amount,
        })

        self.total_amount = 0.0

    def get_data(self, invoice_id):
        self._cr.execute("""SELECT line_number,NULLIF('[' || default_code || '] ' || name_template, '[] ') as product,i.name as description, ac.code || ' ' || ac.name as account, quantity, ROUND(price_unit, 2) as price_unit, ROUND(percentage, 2) as percentage, ROUND(price_subtotal*percentage/100, 2) as sub_total, y.name as currency, n1.code as destination, n2.code as cost_center, n3.code as funding_pool
            FROM funding_pool_distribution_line a
            INNER JOIN account_invoice_line i ON a.distribution_id = i.analytic_distribution_id
            INNER JOIN account_invoice s ON s.id = i.invoice_id
            INNER JOIN account_analytic_account n1 ON n1.id = a.destination_id
            INNER JOIN account_analytic_account n2 ON n2.id = a.cost_center_id
            INNER JOIN account_analytic_account n3 ON n3.id = a.analytic_id
            INNER JOIN account_account ac ON ac.id = i.account_id
            LEFT JOIN product_product p ON p.id = i.product_id
            LEFT JOIN res_currency y ON y.id = s.currency_id
            WHERE i.invoice_id=%s
            UNION ALL
            SELECT line_number,NULLIF('[' || default_code || '] ' || name_template, '[] ') as product,i.name as description, ac.code || ' ' || ac.name as account, quantity, ROUND(price_unit, 2) as price_unit, ROUND(percentage, 2) as percentage, ROUND(price_subtotal*percentage/100, 2) as sub_total, y.name as currency, n1.code as destination, n2.code as cost_center, n3.code as funding_pool
            FROM funding_pool_distribution_line a
            INNER JOIN account_invoice s ON s.analytic_distribution_id = a.distribution_id
            LEFT JOIN account_invoice_line i ON i.invoice_id = s.id AND i.analytic_distribution_id IS NULL
            INNER JOIN account_account ac ON ac.id = i.account_id
            INNER JOIN account_analytic_account n1 ON n1.id = a.destination_id
            INNER JOIN account_analytic_account n2 ON n2.id = a.cost_center_id
            INNER JOIN account_analytic_account n3 ON n3.id = a.analytic_id
            INNER JOIN res_currency y ON y.id = s.currency_id
            LEFT JOIN product_product p ON p.id = i.product_id
            WHERE s.id=%s
            UNION ALL
            SELECT line_number,NULLIF('[' || default_code || '] ' || name_template, '[] ') as product,i.name as description, ac.code || ac.name as account, quantity, ROUND(price_unit, 2) as price_unit, NULL, ROUND(price_subtotal, 2) as sub_total, y.name as currency, NULL, NULL, NULL
            FROM account_invoice_line i
            INNER JOIN account_invoice s ON s.id = i.invoice_id
            INNER JOIN account_account ac ON ac.id = i.account_id
            INNER JOIN res_currency y ON y.id = s.currency_id
            LEFT JOIN product_product p ON p.id = i.product_id
            WHERE s.id=%s and is_analytic_addicted = False
            ORDER BY line_number, destination, cost_center, funding_pool
            """, (invoice_id, invoice_id, invoice_id))
        res = self._cr.fetchall()
        self.total_amount = sum([line[7] or 0.0 for line in res])
        return res

    def get_total_amount(self):
        return self.total_amount

report_sxw.report_sxw('report.allocation.invoices.report',
                      'account.invoice',
                      'addons/account_override/report/allocation_invoices_report.rml',
                      parser=allocation_invoice_report, header="landscape")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
