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
        self.invoices = {}
        self.localcontext.update({
            'distribution_lines': self._get_distribution_lines,
            'shipment_number': self._get_shipment_number,
            'fo_number': self._get_fo_number,
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

    def _get_shipment_number(self, inv):
        """
        Returns the shipment number for Intermission Vouchers linked to a supply workflow
        """
        if self.invoices.get(inv.id, {}).get('shipment', None) is not None:
            return self.invoices[inv.id]['shipment']
        ship_or_out_ref = ''
        if inv.from_supply and inv.is_intermission:
            if inv.type == 'out_invoice':  # IVO
                if inv.name:
                    ship_or_out_ref = inv.name.split()[-1]
            elif inv.type == 'in_invoice':  # IVI
                if inv.picking_id:
                    ship_or_out_ref = inv.picking_id.shipment_ref or ''
        self.invoices.setdefault(inv.id, {}).update({'shipment': ship_or_out_ref})
        return ship_or_out_ref

    def _get_fo_number(self, inv):
        """
        Returns the FO number for Intermission Vouchers linked to a supply workflow
        """
        if self.invoices.get(inv.id, {}).get('fo', None) is not None:
            return self.invoices[inv.id]['fo']
        fo_number = ''
        if inv.from_supply and inv.is_intermission:
            if inv.type == 'out_invoice':  # IVO
                if inv.origin:
                    inv_source_doc_split = inv.origin.split(':')
                    if inv_source_doc_split:
                        fo_number = inv_source_doc_split[-1]
            elif inv.type == 'in_invoice':  # IVI
                if inv.main_purchase_id:
                    fo_number = inv.main_purchase_id.short_partner_ref or ''
        self.invoices.setdefault(inv.id, {}).update({'fo': fo_number})
        return fo_number


SpreadsheetReport('report.invoice.excel.export', 'account.invoice',
                  'addons/account/report/invoice_excel_export.mako', parser=invoice_excel_export)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
