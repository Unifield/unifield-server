# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2020 TeMPO Consulting, MSF. All Rights Reserved
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


class invoice_excel_export(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(invoice_excel_export, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'distribution_lines': self._get_distribution_lines,
        })

    def _get_distribution_lines(self, inv_line):
        """
        Returns distrib. line data related to the invoice line in parameter, as a list of dicts
        """
        fp_distrib_line_obj = self.pool.get('funding.pool.distribution.line')
        distrib_lines = []
        distribution = False
        if inv_line.account_id.is_analytic_addicted:  # don't take header distrib for lines which shouldn't be linked to any AD
            distribution = inv_line.analytic_distribution_id or inv_line.invoice_id.analytic_distribution_id or False
        if distribution:
            distrib_ids = fp_distrib_line_obj.search(self.cr, self.uid, [('distribution_id', '=', distribution.id)])
            for distrib in fp_distrib_line_obj.browse(self.cr, self.uid, distrib_ids):
                distrib_lines.append(
                    {
                        'percentage': distrib.percentage,
                        'cost_center': distrib.cost_center_id.code or '',
                        'destination': distrib.destination_id.code or '',
                        'subtotal': inv_line.price_subtotal*distrib.percentage/100,
                    }
                )
        else:
            distrib_lines.append(
                {
                    'percentage': 100,
                    'cost_center': '',
                    'destination': '',
                    'subtotal': inv_line.price_subtotal,
                }
            )
        return distrib_lines


SpreadsheetReport('report.invoice.excel.export', 'account.invoice',
                  'addons/account/report/invoice_excel_export.mako', parser=invoice_excel_export)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
