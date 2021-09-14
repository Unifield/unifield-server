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
            'po_number': self._get_po_number,
        })

    def _get_distribution_lines(self, inv_line):
        """
        Returns distrib. line data related to the invoice line in parameter, as a list of dicts
        Note: it gives a result even for lines without AD: the line subtotal is retrieved in any cases
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
        Returns the "shipment" or "simple OUT" number having generated the IVO/STV if linked to a supply workflow
        Displayed for both the IVO/STV and the IVI.
        """
        if self.invoices.get(inv.id, {}).get('shipment', None) is not None:
            # process only once per invoice
            return self.invoices[inv.id]['shipment']
        ship_or_out_ref = ''
        if inv.from_supply:
            if inv.type == 'out_invoice' and not inv.is_debit_note:  # IVO/STV
                if inv.name:
                    ship_or_out_ref = inv.name.split()[-1]
            elif inv.is_intermission and inv.type == 'in_invoice':  # IVI
                if inv.picking_id:
                    ship_or_out_ref = inv.picking_id.shipment_ref or ''
        self.invoices.setdefault(inv.id, {}).update({'shipment': ship_or_out_ref})
        return ship_or_out_ref

    def _get_fo_number(self, inv):
        """
        Returns the FO number related to the IVO/STV if any.
        Displayed for both the IVO/STV and the IVI.
        """
        if self.invoices.get(inv.id, {}).get('fo', None) is not None:
            # process only once per invoice
            return self.invoices[inv.id]['fo']
        fo_number = ''
        if inv.from_supply:
            if inv.type == 'out_invoice' and not inv.is_debit_note:  # IVO/STV
                if inv.origin:
                    inv_source_doc_split = inv.origin.split(':')
                    if inv_source_doc_split:
                        fo_number = inv_source_doc_split[-1]
            elif inv.is_intermission and inv.type == 'in_invoice':  # IVI
                if inv.main_purchase_id:
                    fo_number = inv.main_purchase_id.short_partner_ref or ''
        self.invoices.setdefault(inv.id, {}).update({'fo': fo_number})
        return fo_number

    def _get_po_number(self, inv_line):
        """
        Returns the PO number for Intermission Voucher Lines linked to a supply workflow.
        For the IVO: PO to the external partner in order to buy the goods
        For the IVI: PO to the intermission partner which triggered the creation of the FO
        """
        inv = inv_line.invoice_id
        ivo_from_supply = inv.is_intermission and inv.type == 'out_invoice' and inv.from_supply
        if not ivo_from_supply and self.invoices.get(inv.id, {}).get('po', None) is not None:
            # process only once per invoice except for IVO from Supply where the check must be done line by line
            return self.invoices[inv.id]['po']
        po_number = ''
        po_line_obj = self.pool.get('purchase.order.line')
        if inv.from_supply and inv.is_intermission:
            if inv.type == 'out_invoice':  # IVO
                fo_line = inv_line.sale_order_line_id
                if fo_line and fo_line.type == 'make_to_order':  # the line is sourced on a PO
                    pol_ids = po_line_obj.search(self.cr, self.uid, [('sale_order_line_id', '=', fo_line.id)])
                    if pol_ids:
                        po_number = po_line_obj.browse(self.cr, self.uid, pol_ids[0], fields_to_fetch=['order_id']).order_id.name
            elif inv.type == 'in_invoice':  # IVI
                if inv.main_purchase_id:
                    po_number = inv.main_purchase_id.name
        self.invoices.setdefault(inv.id, {}).update({'po': po_number})
        return po_number


SpreadsheetReport('report.invoice.excel.export', 'account.invoice',
                  'addons/account/report/invoice_excel_export.mako', parser=invoice_excel_export)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
