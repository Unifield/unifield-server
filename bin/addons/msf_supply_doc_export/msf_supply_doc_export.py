# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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

# !!! each time you create a new report the "name" in the xml file should be on the form "report.sale.order_xls" but WITHOUT "report" at the beginning)
# so in that case, only name="sale.order_xls" in the xml

from report import report_sxw
from report_webkit.webkit_report import WebKitParser as OldWebKitParser
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from purchase import PURCHASE_ORDER_STATE_SELECTION
from datetime import datetime
from osv import osv
from tools.translate import _
from base import currency_date
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from openpyxl.cell import WriteOnlyCell

import pooler
import time


class _int_noformat(report_sxw._int_format):
    def __str__(self):
        return str(self.val)


class _float_noformat(report_sxw._float_format):
    def __str__(self):
        return str(self.val)


_fields_process = {
    'integer': _int_noformat,
    'float': _float_noformat,
    'date': report_sxw._date_format,
    'datetime': report_sxw._dttime_format
}


def getIds(self, cr, uid, ids, context):
    if not context:
        context = {}
    if context.get('from_domain') and 'search_domain' in context:
        table_obj = pooler.get_pool(cr.dbname).get(self.table)
        ids = table_obj.search(cr, uid, context.get('search_domain'), limit=5000)
    return ids

class WebKitParser(OldWebKitParser):

    def getObjects(self, cr, uid, ids, context):
        table_obj = pooler.get_pool(cr.dbname).get(self.table)
        return table_obj.browse(cr, uid, ids, list_class=report_sxw.browse_record_list, context=context, fields_process=_fields_process)


# FIELD ORDER == INTERNAL REQUEST== SALE ORDER they are the same object
class sale_order_report_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(sale_order_report_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(sale_order_report_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')


sale_order_report_xls('report.sale.order_xls','sale.order','addons/msf_supply_doc_export/report/report_sale_order_xls.mako')


class internal_request_report_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(internal_request_report_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(internal_request_report_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')


internal_request_report_xls('report.internal.request_xls','sale.order','addons/msf_supply_doc_export/report/report_internal_request_xls.mako')


class internal_request_export(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(internal_request_export, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(internal_request_export, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

internal_request_export('report.internal_request_export','sale.order','addons/msf_supply_doc_export/internal_request_export_xls.mako')



class picking_ticket_parser(report_sxw.rml_parse):
    """
    Parser for the picking ticket report
    """

    def __init__(self, cr, uid, name, context=None):
        """
        Set the localcontext on the parser

        :param cr: Cursor to the database
        :param uid: ID of the user that runs this method
        :param name: Name of the parser
        :param context: Context of the call
        """
        super(picking_ticket_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'cr': cr,
            'uid': uid,
            'getStock': self.get_stock,
            'getNbItems': self.get_nb_items,
            'format_date': self.format_date,
        })


    def format_date(self, date):
        if not date:
            return ''
        struct_time = time.strptime(date, '%Y-%m-%d %H:%M:%S')
        return time.strftime('%Y-%m-%d', struct_time)

    def get_nb_items(self, picking):
        """
        Returns the number of different line number. If a line is split
        with a different product, this line count for +1
        """
        res = 0
        dict_res = {}
        for m in picking.move_lines:
            if m.state != 'cancel':
                dict_res.setdefault(m.line_number, {})
                if m.product_id.id not in dict_res[m.line_number]:
                    dict_res[m.line_number][m.product_id.id] = 1

        for ln in list(dict_res.values()):
            for p in list(ln.values()):
                res += p

        return res


    def get_stock(self, move=False):
        product_obj = self.pool.get('product.product')

        context = {}

        if not move:
            return 0.00

        if move.location_id:
            context = {
                'location': move.location_id.id,
                'location_id': move.location_id.id,
                'prodlot_id': move.prodlot_id and move.prodlot_id.id or False,
            }

        qty_available = product_obj.browse(
            self.cr,
            self.uid,
            move.product_id.id,
            context=context).qty_available

        return qty_available


class report_pick_export_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(report_pick_export_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(report_pick_export_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')


report_pick_export_xls('report.pick.export.xls','stock.picking','addons/msf_supply_doc_export/report/report_pick_export_xls.mako', parser=picking_ticket_parser)


class report_out_export_parser(XlsxReportParser):

    def add_cell(self, value=None, style='default_style', number_format=None):
        # None value set an xls empty cell
        # False value set the xls False()
        new_cell = WriteOnlyCell(self.workbook.active, value=value)
        new_cell.style = style
        if number_format:
            new_cell.number_format = number_format
        self.rows.append(new_cell)

    def generate(self, context=None):
        if context is None:
            context = {}

        move_obj = self.pool.get('stock.move')
        proc_move_obj = self.pool.get('outgoing.delivery.move.processor')

        out = self.pool.get('stock.picking').browse(self.cr, self.uid, self.ids[0], context=context)

        sheet = self.workbook.active

        sheet.column_dimensions['A'].width = 22.0
        sheet.column_dimensions['B'].width = 45.0
        sheet.column_dimensions['C'].width = 75.0
        sheet.column_dimensions['D'].width = 55.0
        sheet.column_dimensions['E'].width = 22.0
        sheet.column_dimensions['F'].width = 15.0
        sheet.column_dimensions['G'].width = 25.0
        sheet.column_dimensions['H'].width = 25.0
        sheet.column_dimensions['I'].width = 15.0
        sheet.column_dimensions['J'].width = 15.0
        sheet.column_dimensions['K'].width = 7.0
        sheet.column_dimensions['L'].width = 20.0
        sheet.column_dimensions['M'].width = 13.0
        sheet.column_dimensions['N'].width = 5.0
        sheet.column_dimensions['O'].width = 5.0
        sheet.column_dimensions['P'].width = 5.0

        # Styles
        line_header_style = self.create_style_from_template('line_header_style', 'A1')
        line_style = self.create_style_from_template('line_style', 'B1')
        line_left_style = self.create_style_from_template('line_left_style', 'C2')
        date_style = self.create_style_from_template('date_style', 'B3')
        int_style = self.create_style_from_template('int_style', 'A11')
        float_style = self.create_style_from_template('float_style', 'I11')

        sheet.title = _('OUT Export')
        # Header data
        cell_rh = WriteOnlyCell(sheet, value=_('Reference'))
        cell_rh.style = line_header_style
        cell_r = WriteOnlyCell(sheet, value=out.name)
        cell_r.style = line_style
        cell_rqh = WriteOnlyCell(sheet, value=_('Requestor'))
        cell_rqh.style = line_header_style
        sheet.append([cell_rh, cell_r, cell_rqh])

        cell_oh = WriteOnlyCell(sheet, value=_('Origin'))
        cell_oh.style = line_header_style
        cell_o = WriteOnlyCell(sheet, value=out.origin or '')
        cell_o.style = line_style
        cell_rq = WriteOnlyCell(sheet, value=out.requestor or '')
        cell_rq.style = line_left_style
        sheet.append([cell_oh, cell_o, cell_rq])

        cell_cdh = WriteOnlyCell(sheet, value=_('Creation Date'))
        cell_cdh.style = line_header_style
        cell_cd = WriteOnlyCell(sheet, value=out.date and datetime.strptime(out.date, '%Y-%m-%d %H:%M:%S') or '')
        cell_cd.style = date_style
        cell_cd.number_format = 'DD/MM/YYYY HH:MM'
        cell_dah = WriteOnlyCell(sheet, value=_('Delivery Address'))
        cell_dah.style = line_header_style
        sheet.append([cell_cdh, cell_cd, cell_dah])

        cell_ph = WriteOnlyCell(sheet, value=_('Partner'))
        cell_ph.style = line_header_style
        cell_p = WriteOnlyCell(sheet, value=out.partner_id and out.partner_id.name or '')
        cell_p.style = line_style
        da_contact = out.partner_id and out.partner_id.partner_type == 'internal' and _('Supply responsible') \
            or out.address_id and out.address_id.name or ''
        cell_dac = WriteOnlyCell(sheet, value=da_contact)
        cell_dac.style = line_left_style
        sheet.append([cell_ph, cell_p, cell_dac])

        cell_boh = WriteOnlyCell(sheet, value=_('Back Order ref.'))
        cell_boh.style = line_header_style
        cell_bo = WriteOnlyCell(sheet, value=out.backorder_id and out.backorder_id.name or '')
        cell_bo.style = line_style
        da_street = ''
        if out.address_id:
            if out.address_id.street:
                da_street += out.address_id.street + ' '
            if out.address_id.street2:
                da_street += out.address_id.street2 + ' '
            if out.address_id.zip:
                da_street += out.address_id.zip + ' '
            if out.address_id.city:
                da_street += out.address_id.city
        cell_dast = WriteOnlyCell(sheet, value=da_street)
        cell_dast.style = line_left_style
        sheet.append([cell_boh, cell_bo, cell_dast])

        cell_och = WriteOnlyCell(sheet, value=_('Order Category'))
        cell_och.style = line_header_style
        categ = out.order_category and self.pool.get('ir.model.fields').\
            get_selection(self.cr, self.uid, 'stock.picking', 'order_category', out.order_category, context=context) or ''
        cell_oc = WriteOnlyCell(sheet, value=categ)
        cell_oc.style = line_style
        cell_daci = WriteOnlyCell(sheet, value=out.address_id and out.address_id.city or '')
        cell_daci.style = line_left_style
        sheet.append([cell_och, cell_oc, cell_daci])

        cell_rth = WriteOnlyCell(sheet, value=_('Reason Type'))
        cell_rth.style = line_header_style
        cell_rt = WriteOnlyCell(sheet, value=out.reason_type_id and out.reason_type_id.complete_name or '')
        cell_rt.style = line_style
        cell_dap = WriteOnlyCell(sheet, value=out.address_id and out.address_id.phone or '')
        cell_dap.style = line_left_style
        sheet.append([cell_rth, cell_rt, cell_dap])

        cell_deh = WriteOnlyCell(sheet, value=_('Details'))
        cell_deh.style = line_header_style
        cell_de = WriteOnlyCell(sheet, value=out.details or '')
        cell_de.style = line_style
        sheet.append([cell_deh, cell_de])

        cell_esdh = WriteOnlyCell(sheet, value=_('Expected Ship Date'))
        cell_esdh.style = line_header_style
        cell_esd = WriteOnlyCell(sheet, value=out.min_date and datetime.strptime(out.min_date, '%Y-%m-%d %H:%M:%S') or '')
        cell_esd.style = date_style
        cell_esd.number_format = 'DD/MM/YYYY HH:MM'
        sheet.append([cell_esdh, cell_esd])

        row_headers = [
            (_('Item')),
            (_('Code')),
            (_('Description')),
            (_('Comment')),
            (_('Asset')),
            (_('Kit')),
            (_('Src. Location')),
            (_('Dest. Location')),
            (_('Ordered Qty')),
            (_('Qty to Process')),
            (_('UoM')),
            (_('Batch')),
            (_('Expiry Date')),
            (_('CC')),
            (_('DG')),
            (_('CS')),
        ]

        # Lines data
        row_header = []
        for header in row_headers:
            cell_t = WriteOnlyCell(sheet, value=header)
            cell_t.style = line_header_style
            row_header.append(cell_t)
        sheet.append(row_header)

        move_domain = [('picking_id', '=', out.id)]
        if out.state == 'assigned':  # Same behavior as Process popup, only available lines are exported
            move_domain.append(('state', '=', 'assigned'))
        move_line_ids = move_obj.search(self.cr, self.uid, move_domain, context=context)
        if move_line_ids:
            for move in move_obj.browse(self.cr, self.uid, move_line_ids, context=context):
                # Check if there is any existing saved OUT processor
                proc_move_domain = [('wizard_id.draft', '=', True), ('move_id', '=', move.id)]
                prod_move_ids = proc_move_obj.search(self.cr, self.uid, proc_move_domain, context=context)
                if prod_move_ids:
                    for proc_move in proc_move_obj.browse(self.cr, self.uid, prod_move_ids, context=context):
                        self.rows = []

                        self.add_cell(move.line_number, int_style)
                        self.add_cell(move.product_id and move.product_id.default_code or '', line_style)
                        self.add_cell(move.product_id and move.product_id.name or '', line_style)
                        self.add_cell(move.comment or '', line_style)
                        self.add_cell(proc_move.asset_id and proc_move.asset_id.name or '', line_style)
                        self.add_cell(proc_move.composition_list_id and proc_move.composition_list_id.composition_reference
                                      or '', line_style)
                        self.add_cell(move.location_id and move.location_id.name or '', line_style)
                        self.add_cell(move.location_dest_id and move.location_dest_id.name or '', line_style)
                        self.add_cell(proc_move.ordered_quantity, float_style)
                        self.add_cell(proc_move.quantity or 0.00, float_style)
                        self.add_cell(proc_move.uom_id and proc_move.uom_id.name or '', line_style)
                        self.add_cell(proc_move.prodlot_id and proc_move.prodlot_id.name or '', line_style)
                        self.add_cell(proc_move.expiry_date and datetime.strptime(proc_move.expiry_date, '%Y-%m-%d') or '',
                                      date_style, number_format='DD/MM/YYYY')
                        self.add_cell(move.kc_check and _('Yes') or _('No'), line_style)
                        self.add_cell(move.dg_check and _('Yes') or _('No'), line_style)
                        self.add_cell(move.np_check and _('Yes') or _('No'), line_style)

                        sheet.append(self.rows)
                else:
                    self.rows = []

                    self.add_cell(move.line_number, int_style)
                    self.add_cell(move.product_id and move.product_id.default_code or '', line_style)
                    self.add_cell(move.product_id and move.product_id.name or '', line_style)
                    self.add_cell(move.comment or '', line_style)
                    self.add_cell(move.asset_id and move.asset_id.name or '', line_style)
                    self.add_cell(move.composition_list_id and move.composition_list_id.composition_reference or '', line_style)
                    self.add_cell(move.location_id and move.location_id.name or '', line_style)
                    self.add_cell(move.location_dest_id and move.location_dest_id.name or '', line_style)
                    self.add_cell(move.product_qty, float_style)
                    self.add_cell(0.00, float_style)
                    self.add_cell(move.product_uom and move.product_uom.name or '', line_style)
                    self.add_cell(move.prodlot_id and move.prodlot_id.name or '', line_style)
                    self.add_cell(move.expired_date and datetime.strptime(move.expired_date, '%Y-%m-%d') or '',
                                  date_style, number_format='DD/MM/YYYY')
                    self.add_cell(move.kc_check and _('Yes') or _('No'), line_style)
                    self.add_cell(move.dg_check and _('Yes') or _('No'), line_style)
                    self.add_cell(move.np_check and _('Yes') or _('No'), line_style)

                    sheet.append(self.rows)


XlsxReport('report.report_out_export', parser=report_out_export_parser, template='addons/msf_supply_doc_export/report/report_out_export.xlsx')


# PURCHASE ORDER and REQUEST FOR QUOTATION are the same object
class purchase_order_report_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(purchase_order_report_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(purchase_order_report_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

purchase_order_report_xls('report.purchase.order_xls','purchase.order','addons/msf_supply_doc_export/report/report_purchase_order_xls.mako')


def getInstanceAddressG(self):
    part_addr = []
    deliv_addr = ''
    company_partner = self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id.partner_id
    for addr in company_partner.address:
        if addr.active:
            if addr.type == 'default':
                return addr.office_name or ''
            elif addr.type == 'delivery':
                deliv_addr = addr.office_name
            else:
                part_addr.append(addr.office_name)

    return deliv_addr or (part_addr and part_addr[0]) or ''

# VALIDATED PURCHASE ORDER (Excel XML)
class validated_purchase_order_report_xls(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        if context is None:
            context = {}
        context['lang'] = 'en_MF'
        super(validated_purchase_order_report_xls, self).__init__(cr, uid, name, context=context)
        self.cr = cr
        self.uid = uid
        self.localcontext.update({
            'time': time,
            'maxADLines': self.get_max_ad_lines,
            'getInstanceName': self.getInstanceName,
            'getCustomerAddress': self.getCustomerAddress,
            'getInstanceAddress': self.getInstanceAddress,
            'getContactName': self.getContactName,
        })

    def set_context(self, objects, data, ids, report_type = None):
        super(validated_purchase_order_report_xls, self).set_context(objects, data, ids, report_type=report_type)
        self.localcontext['need_ad'] = data.get('need_ad', True)

    def get_max_ad_lines(self, order):
        max_ad_lines = 0
        for line in order.order_line:
            if line.analytic_distribution_id:
                if len(line.analytic_distribution_id.cost_center_lines) > max_ad_lines:
                    max_ad_lines = len(line.analytic_distribution_id.cost_center_lines)

        return max_ad_lines

    def getInstanceName(self):
        return self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id.instance_id.instance

    def getInstanceAddress(self):
        return getInstanceAddressG(self)

    def getCustomerAddress(self, customer_id):
        part_addr_obj = self.pool.get('res.partner.address')
        part_addr_id = part_addr_obj.search(self.cr, self.uid, [('partner_id', '=', customer_id)], limit=1)[0]

        return part_addr_obj.browse(self.cr, self.uid, part_addr_id).name

    def getContactName(self, addr_id):
        res = ''
        if addr_id:
            res = self.pool.get('res.partner.address').read(self.cr, self.uid, addr_id)['office_name']
        return res


SpreadsheetReport('report.validated.purchase.order_xls', 'purchase.order', 'addons/msf_supply_doc_export/report/report_validated_purchase_order_xls.mako', parser=validated_purchase_order_report_xls)

# VALIDATE PURCHASE ORDER (Pure XML)
class parser_validated_purchase_order_report_xml(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        if context is None:
            context = {}
        context['lang'] = 'en_MF'
        super(parser_validated_purchase_order_report_xml, self).__init__(cr, uid, name, context=context)
        self.cr = cr
        self.uid = uid
        self.localcontext.update({
            'time': time,
            'maxADLines': self.get_max_ad_lines,
            'getInstanceName': self.getInstanceName,
            'getCustomerAddress': self.getCustomerAddress,
            'getContactName': self.getContactName,
            'getInstanceAddress': self.getInstanceAddress,
        })

    def set_context(self, objects, data, ids, report_type = None):
        super(parser_validated_purchase_order_report_xml, self).set_context(objects, data, ids, report_type=report_type)
        self.localcontext['need_ad'] = data.get('need_ad', True)

    def get_max_ad_lines(self, order):
        max_ad_lines = 0
        for line in order.order_line:
            if line.analytic_distribution_id:
                if len(line.analytic_distribution_id.cost_center_lines) > max_ad_lines:
                    max_ad_lines = len(line.analytic_distribution_id.cost_center_lines)

        return max_ad_lines

    def getInstanceName(self):
        return self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id.instance_id.instance

    def getCustomerAddress(self, customer_id):
        part_addr_obj = self.pool.get('res.partner.address')
        part_addr_id = part_addr_obj.search(self.cr, self.uid, [('partner_id', '=', customer_id)], limit=1)[0]

        return part_addr_obj.browse(self.cr, self.uid, part_addr_id).name

    def getContactName(self, addr_id):
        res = ''
        if addr_id:
            res = self.pool.get('res.partner.address').read(self.cr, self.uid, addr_id)['office_name']
        return res

    def getInstanceAddress(self):
        return getInstanceAddressG(self)


class validated_purchase_order_report_xml(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header = " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(validated_purchase_order_report_xml, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(validated_purchase_order_report_xml, self).create(cr, uid, ids, data, context)
        return (a[0], 'xml')

validated_purchase_order_report_xml('report.validated.purchase.order_xml', 'purchase.order', 'addons/msf_supply_doc_export/report/report_validated_purchase_order_xml.mako', parser=parser_validated_purchase_order_report_xml)

class request_for_quotation_report_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(request_for_quotation_report_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(request_for_quotation_report_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')


request_for_quotation_report_xls('report.request.for.quotation_xls','purchase.order','addons/msf_supply_doc_export/report/report_request_for_quotation_xls.mako')


class parser_tender_report_xls(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(parser_tender_report_xls, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'computePrice': self._compute_price,
        })

    def _compute_price(self, line_currency_id, tender_currency_id, price):
        cur_obj = self.pool.get('res.currency')
        return round(cur_obj.compute(self.cr, self.uid, line_currency_id, tender_currency_id, price, round=False, context=self.localcontext), 2)


class tender_report_xls(SpreadsheetReport):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(tender_report_xls, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(tender_report_xls, self).create(cr, uid, ids, data, context=context)
        return (a[0], 'xls')


tender_report_xls('report.tender_xls', 'tender', 'addons/msf_supply_doc_export/report/report_tender_xls.mako', parser=parser_tender_report_xls, header='internal')


class stock_cost_reevaluation_report_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(stock_cost_reevaluation_report_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(stock_cost_reevaluation_report_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

stock_cost_reevaluation_report_xls('report.stock.cost.reevaluation_xls','stock.cost.reevaluation','addons/msf_supply_doc_export/report/stock_cost_reevaluation_xls.mako')

class stock_inventory_report_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(stock_inventory_report_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(stock_inventory_report_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

stock_inventory_report_xls('report.stock.inventory_xls','stock.inventory','addons/msf_supply_doc_export/report/stock_inventory_xls.mako')

class stock_initial_inventory_report_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(stock_initial_inventory_report_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(stock_initial_inventory_report_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

stock_initial_inventory_report_xls('report.initial.stock.inventory_xls','initial.stock.inventory','addons/msf_supply_doc_export/report/stock_initial_inventory_xls.mako')

class product_list_report_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header = " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(product_list_report_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(product_list_report_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

product_list_report_xls('report.product.list.xls', 'product.list', 'addons/msf_supply_doc_export/report/product_list_xls.mako')

class composition_kit_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header = " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(composition_kit_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(composition_kit_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')
composition_kit_xls('report.composition.kit.xls', 'composition.kit', 'addons/msf_supply_doc_export/report/report_composition_kit_xls.mako')


class real_composition_kit_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header = " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(real_composition_kit_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(real_composition_kit_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

real_composition_kit_xls('report.real.composition.kit.xls', 'composition.kit', 'addons/msf_supply_doc_export/report/report_real_composition_kit_xls.mako')


class internal_move_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header = " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(internal_move_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(internal_move_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

internal_move_xls('report.internal.move.xls', 'stock.picking', 'addons/msf_supply_doc_export/report/report_internal_move_xls.mako')


class incoming_shipment_xls(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        if not context:
            context = {}
        context['lang'] = 'en_MF'
        super(incoming_shipment_xls, self).__init__(cr, uid, name, context=context)

SpreadsheetReport('report.incoming.shipment.xls', 'stock.picking', 'addons/msf_supply_doc_export/report/report_incoming_shipment_xls.mako', parser=incoming_shipment_xls)

class parser_incoming_shipment_xml(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(incoming_shipment_xls, self).__init__(cr, uid, name, context=context)

class incoming_shipment_xml(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header = " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(incoming_shipment_xml, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(incoming_shipment_xml, self).create(cr, uid, ids, data, context)
        return (a[0], 'xml')

incoming_shipment_xml('report.incoming.shipment.xml', 'stock.picking', 'addons/msf_supply_doc_export/report/report_incoming_shipment_xml.mako')


def get_back_browse(self, cr, uid, context=None):
    if context is None:
        context = {}

    background_id = context.get('background_id')
    if background_id:
        return self.pool.get('memory.background.report').browse(cr, uid, background_id)
    return False


class po_follow_up_mixin(object):

    def _get_states(self):
        states = {}
        for state_val, state_string in PURCHASE_ORDER_STATE_SELECTION:
            states[state_val] = state_string
        return states

    def getRunParms(self):
        return self.datas['report_parms']

    def getRunParmsRML(self,key):
        return self.datas['report_parms'][key]

    def printAnalyticLines(self, analytic_lines):
        res = []
        # if additional analytic lines print them here.
        for (index, analytic_line) in list(enumerate(analytic_lines))[1:]:
            report_line = {}
            report_line['order_ref'] = ''
            report_line['order_created'] = ''
            report_line['order_confirmed_date'] = ''
            report_line['raw_state'] = analytic_line.get('raw_state')
            report_line['line_status'] = ''
            report_line['state'] = ''
            report_line['order_status'] = ''
            report_line['item'] = ''
            report_line['code'] = ''
            report_line['description'] = ''
            report_line['qty_ordered'] = 0
            report_line['uom'] = ''
            report_line['qty_received'] = 0
            report_line['in'] = ''
            report_line['qty_backordered'] = 0
            report_line['unit_price'] = ''
            report_line['in_unit_price'] = ''
            report_line['delivery_requested_date'] = ''
            report_line['customer'] = ''
            report_line['customer_ref'] = ''
            report_line['source_doc'] = ''
            report_line['source_creation_date'] = ''
            report_line['supplier'] = ''
            report_line['supplier_ref'] = ''
            report_line['order_type'] = ''
            report_line['order_category'] = ''
            report_line['priority'] = ''
            report_line['currency'] = ''
            report_line['total_currency'] = ''
            report_line['total_func_currency'] = ''
            report_line['destination'] = analytic_line.get('destination')
            report_line['cost_centre'] = analytic_line.get('cost_center')
            report_line['mml_status'] = ''
            report_line['msl_status'] = ''
            res.append(report_line)

        return res

    def yieldPoLines(self, po_line_ids):
        if len(po_line_ids):
            self.cr.execute("""
                SELECT pl.id, pl.state, pl.line_number, adl.id, ppr.id, ppr.default_code, COALESCE(tr.value, pt.name), 
                    uom.id, uom.name, pl.confirmed_delivery_date, pl.date_planned, pl.product_qty, pl.price_unit, 
                    pl.linked_sol_id, spar.name, so.client_order_ref, pl.origin, pl.esti_dd, so.date_order, p.order_type
                FROM purchase_order_line pl
                    LEFT JOIN purchase_order p ON pl.order_id = p.id
                    LEFT JOIN analytic_distribution adl ON pl.analytic_distribution_id = adl.id
                    LEFT JOIN product_product ppr ON pl.product_id = ppr.id
                    LEFT JOIN product_template pt ON ppr.product_tmpl_id = pt.id
                    LEFT JOIN ir_translation tr ON tr.res_id = pt.id AND tr.name = 'product.template,name' AND tr.lang = %s
                    LEFT JOIN product_uom uom ON pl.product_uom = uom.id
                    LEFT JOIN sale_order_line sol ON pl.linked_sol_id = sol.id
                    LEFT JOIN sale_order so ON sol.order_id = so.id
                    LEFT JOIN res_partner spar ON so.partner_id = spar.id
                WHERE pl.id IN %s
                ORDER BY pl.line_number, pl.id
            """, (self.localcontext.get('lang', 'en_MF'), tuple(po_line_ids)))

            for pol in self.cr.fetchall():
                yield pol

        return

    def getLineStyle(self, line):
        return 'lgrey' if line.get('raw_state', '') in ['cancel', 'cancel_r'] else 'line'

    def get_total_currency(self, in_unit_price, qty_received):
        if not in_unit_price or not qty_received:
            return '0.00'
        try:
            in_unit_price = float(in_unit_price)
            qty_received = float(qty_received)
        except:
            return '0.00'
        return in_unit_price * qty_received

    def get_exchange_rate(self, pol_id):
        pol = self.pool.get('purchase.order.line').browse(self.cr, self.uid, pol_id)
        context = {}
        exchange_rate = 0.0
        if pol.closed_date:
            context.update({'currency_date': pol.closed_date})
        elif pol.confirmation_date:
            context.update({'currency_date': pol.confirmation_date})
        elif pol.validation_date:
            context.update({'currency_date': pol.validation_date})
        elif pol.create_date: # could be null, because not mandatory in DB
            context.update({'currency_date': pol.create_date})
        else:
            context.update({'currency_date': datetime.now().strftime('%Y-%m-%d')})

        currency_from = pol.order_id.pricelist_id.currency_id
        currency_to = self.pool.get('res.users').browse(self.cr, self.uid, self.uid, context=context).company_id.currency_id
        exchange_rate = self.pool.get('res.currency')._get_conversion_rate(self.cr, self.uid, currency_from, currency_to, context=context)

        return exchange_rate

    def get_total_func_currency(self, pol_id, in_unit_price, qty_received):
        ex_rate = self.get_exchange_rate(pol_id)
        total_currency = self.get_total_currency(in_unit_price, qty_received)
        total_currency = float(total_currency)

        return total_currency * ex_rate

    def get_qty_backordered(self, pol_id, qty_ordered, qty_received, first_line):
        pol = self.pool.get('purchase.order.line').browse(self.cr, self.uid, pol_id)
        if not qty_ordered or pol.state.startswith('cancel') or (pol.order_id.order_type == 'direct' and pol.state == 'done'):
            return 0.0
        try:
            qty_ordered = float(qty_ordered)
            qty_received = float(qty_received)
        except:
            return 0.0

        # Line partially received:
        in_move_done = self.pool.get('stock.move').search(self.cr, self.uid, [
            ('type', '=', 'in'),
            ('purchase_line_id', '=', pol.id),
            ('state', '=', 'done'),
        ])
        if first_line and in_move_done:
            total_done = 0.0
            for move in self.pool.get('stock.move').browse(self.cr, self.uid, in_move_done, fields_to_fetch=['product_qty','product_uom']):
                if pol.product_uom.id != move.product_uom.id:
                    total_done += self.pool.get('product.uom')._compute_qty(self.cr, self.uid, move.product_uom.id, move.product_qty, pol.product_uom.id)
                else:
                    total_done += move.product_qty
            return qty_ordered - total_done

        return qty_ordered - qty_received

    def get_mml_msl_status(self, pol_id):
        get_sel = self.pool.get('ir.model.fields').get_selection
        ftf = ['mml_status', 'msl_status']
        pol = self.pool.get('purchase.order.line').browse(self.cr, self.uid, pol_id, fields_to_fetch=ftf,
                                                          context=self.localcontext)
        return {
            'mml_status': get_sel(self.cr, self.uid, 'purchase.order.line', 'mml_status', pol.mml_status,
                                  context=self.localcontext) or '',
            'msl_status': get_sel(self.cr, self.uid, 'purchase.order.line', 'msl_status', pol.msl_status,
                                  context=self.localcontext) or '',
        }

    def format_date(self, date):
        if not date:
            return ''
        time_tuple = time.strptime(date, '%Y-%m-%d')
        new_date = time.strftime('%d.%m.%Y', time_tuple)

        return new_date


    def filter_pending_only(self, report_lines):
        res = []
        for line in report_lines:
            if line['qty_backordered'] > 0:
                res.append(line)
        return res

    def getPOLines(self, export_format, po_id, pending_only_ok=False):
        ''' developer note: would be a lot easier to write this as a single sql and then use on-break '''
        pol_obj = self.pool.get('purchase.order.line')
        prod_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        get_sel = self.pool.get('ir.model.fields').get_selection

        if self.datas['report_parms'].get('non_conform'):
            po_line_ids = self.pool.get('po.follow.up').get_line_ids_non_msl(self.cr, self.uid, po_id, context=self.localcontext)
        else:
            po_line_ids = pol_obj.search(self.cr, self.uid, [('order_id', '=', po_id)], order='line_number', context=self.localcontext)

        report_lines = []
        if not po_line_ids:
            return report_lines

        po = []
        self.cr.execute("""
            SELECT p.id, p.state, p.name, p.date_order, ad.id, ppar.name, p.partner_ref, p.order_type, c.name, 
                p.delivery_confirmed_date, p.details, p.delivery_requested_date_modified, p.categ, p.priority
            FROM purchase_order p
                LEFT JOIN analytic_distribution ad ON p.analytic_distribution_id = ad.id
                LEFT JOIN res_partner ppar ON p.partner_id = ppar.id
                LEFT JOIN product_pricelist pri ON p.pricelist_id = pri.id
                LEFT JOIN res_currency c ON pri.currency_id = c.id
            WHERE p.id = %s
        """, (po_id,))
        for p in self.cr.fetchall():
            po = p

        # Background
        if not self.localcontext.get('processed_pos'):
            self.localcontext['processed_pos'] = []

        po_state = get_sel(self.cr, self.uid, 'purchase.order', 'state', po[1], context=self.localcontext) or ''
        for line in self.yieldPoLines(po_line_ids):
            analytic_lines = self.getAnalyticLines(po, line)
            same_product_same_uom = []
            same_product = []
            other_product = []
            mml_msl_status = self.get_mml_msl_status(line[0])

            for inl in self.getAllLineIN(line[0]):
                if inl.get('date_expected'):
                    inl['date_expected'] = inl['date_expected'].split(' ')[0]
                if inl.get('product_id') and inl.get('product_id') == line[4]:
                    if inl.get('product_uom') and inl.get('product_uom') == line[7]:
                        same_product_same_uom.append(inl)
                    else:
                        same_product.append(inl)
                else:
                    other_product.append(inl)

            first_line = True
            edd = line[17] or po[11] or False
            # Display information of the initial reception
            if not same_product_same_uom:
                report_line = {
                    'order_ref': po[2] or '',
                    'order_created': po[3],
                    'order_confirmed_date': line[9],
                    'delivery_requested_date': line[10],
                    'estimated_delivery_date': edd,
                    'raw_state': line[1],
                    'line_status': get_sel(self.cr, self.uid, 'purchase.order.line', 'state', line[1],
                                           context=self.localcontext) or '',
                    'state': get_sel(self.cr, self.uid, 'purchase.order.line', 'state_to_display', line[1],
                                     context=self.localcontext) or '',
                    'order_status': po_state,
                    'item': line[2] or '',
                    'code': line[5] or '',
                    'description': line[6] or '',
                    'qty_ordered': line[11] or '',
                    'uom': line[8] or '',
                    'qty_received': line[1] == 'done' and line[19] == 'direct' and line[11] or '0.00',
                    'in': '',
                    'qty_backordered': self.get_qty_backordered(line[0], line[11], 0.0, first_line),
                    'destination': analytic_lines[0].get('destination'),
                    'cost_centre': analytic_lines[0].get('cost_center'),
                    'unit_price': line[12] or '',
                    'in_unit_price': '',
                    'customer': line[13] and line[14] or '',
                    'customer_ref': line[13] and line[15] and '.' in line[15] and line[15].split('.')[1] or '',
                    'source_doc': line[16] or '',
                    'source_creation_date': line[18] or '',
                    'supplier': po[5] or '',
                    'supplier_ref': po[6] and '.' in po[6] and po[6].split('.')[1] or '',
                    # new
                    'order_type': get_sel(self.cr, self.uid, 'purchase.order', 'order_type', po[7],
                                          context=self.localcontext) or '',
                    'order_category': get_sel(self.cr, self.uid, 'purchase.order', 'categ', po[12],
                                              context=self.localcontext) or '',
                    'priority': get_sel(self.cr, self.uid, 'purchase.order', 'priority', po[13],
                                        context=self.localcontext) or '',
                    'currency': po[8] or '',
                    'total_currency': '',
                    'total_func_currency': '',
                    'po_details': po[10] or '',
                    'mml_status': mml_msl_status['mml_status'],
                    'msl_status': mml_msl_status['msl_status'],
                }
                report_lines.append(report_line)
                if export_format != 'xls':
                    report_lines.extend(self.printAnalyticLines(analytic_lines))
                first_line = False

            for spsul in sorted(same_product_same_uom, key=lambda spsu: spsu.get('backorder_id') or 0, reverse=True):
                report_line = {
                    'order_ref': po[2] or '',
                    'order_created': po[3],
                    'order_confirmed_date': spsul.get('date_expected') or line[9] or po[9],
                    'delivery_requested_date': line[10],
                    'estimated_delivery_date': edd,
                    'raw_state': line[1],
                    'order_status': po_state,
                    'line_status': first_line and get_sel(self.cr, self.uid, 'purchase.order.line', 'state', line[1],
                                                          context=self.localcontext) or '',
                    'state': get_sel(self.cr, self.uid, 'purchase.order.line', 'state_to_display', line[1],
                                     context=self.localcontext) or '',
                    'item': line[2] or '',
                    'code': line[5] or '',
                    'description': line[6] or '',
                    'qty_ordered': first_line and line[11] or '',
                    'uom': line[8] or '',
                    'qty_received': spsul.get('state') == 'done' and spsul.get('product_qty', '') or '0.00',
                    'in': spsul.get('name', '') or '',
                    'qty_backordered': self.get_qty_backordered(line[0], first_line and line[11] or 0.0, spsul.get('state') == 'done' and spsul.get('product_qty', 0.0) or 0.0, first_line),
                    'destination': analytic_lines[0].get('destination'),
                    'cost_centre': analytic_lines[0].get('cost_center'),
                    'unit_price': line[12] or '',
                    'in_unit_price': spsul.get('price_unit'),
                    'customer': line[13] and line[14] or '',
                    'customer_ref': line[13] and line[15] and '.' in line[15] and line[15].split('.')[1] or '',
                    'source_doc': line[16] or '',
                    'source_creation_date': line[18] or '',
                    'supplier': po[5] or '',
                    'supplier_ref': po[6] and '.' in po[6] and po[6].split('.')[1] or '',
                    # new
                    'order_type': get_sel(self.cr, self.uid, 'purchase.order', 'order_type', po[7],
                                          context=self.localcontext) or '',
                    'order_category': get_sel(self.cr, self.uid, 'purchase.order', 'categ', po[12],
                                              context=self.localcontext) or '',
                    'priority': get_sel(self.cr, self.uid, 'purchase.order', 'priority', po[13],
                                        context=self.localcontext) or '',
                    'currency': po[8] or '',
                    'total_currency': self.get_total_currency(spsul.get('price_unit'), spsul.get('state') == 'done' and spsul.get('product_qty', '') or 0.0),
                    'total_func_currency': self.get_total_func_currency(
                        line[0],
                        spsul.get('price_unit', 0.0),
                        spsul.get('state') == 'done' and spsul.get('product_qty', 0.0) or 0.0
                    ),
                    'po_details': po[10] or '',
                    'mml_status': mml_msl_status['mml_status'],
                    'msl_status': mml_msl_status['msl_status'],
                }

                report_lines.append(report_line)

                # if spsul.get('backorder_id') and spsul.get('state') != 'done':
                #     report_line['qty_backordered'] = spsul.get('product_qty', '')

                if first_line:
                    if export_format != 'xls':
                        report_lines.extend(self.printAnalyticLines(analytic_lines))
                    first_line = False

            for spl in sorted(same_product, key=lambda spsu: spsu.get('backorder_id') or 0, reverse=True):
                report_line = {
                    'order_ref': po[2] or '',
                    'order_created': po[3],
                    'order_confirmed_date': spl.get('date_expected') or line[9] or po[9],
                    'delivery_requested_date': line[10],
                    'estimated_delivery_date': edd,
                    'raw_state': line[1],
                    'order_status': po_state,
                    'line_status': first_line and get_sel(self.cr, self.uid, 'purchase.order.line', 'state', line[1],
                                                          context=self.localcontext) or '',
                    'state': get_sel(self.cr, self.uid, 'purchase.order.line', 'state_to_display', line[1],
                                     context=self.localcontext) or '',
                    'item': line[2] or '',
                    'code': line[5] or '',
                    'description': line[6] or '',
                    'qty_ordered': first_line and line[11] or '',
                    'uom': uom_obj.read(self.cr, self.uid, spl.get('product_uom'), ['name'])['name'],
                    'qty_received': spl.get('state') == 'done' and spl.get('product_qty', '') or '0.00',
                    'in': spl.get('name', '') or '',
                    'qty_backordered': self.get_qty_backordered(line[0], first_line and line[11] or 0.0, spl.get('state') == 'done' and spl.get('product_qty', 0.0) or 0.0, first_line),
                    'destination': analytic_lines[0].get('destination'),
                    'cost_centre': analytic_lines[0].get('cost_center'),
                    'unit_price': line[12] or '',
                    'in_unit_price': spl.get('price_unit'),
                    'customer': line[13] and line[14] or '',
                    'customer_ref': line[13] and line[15] and '.' in line[15] and line[15].split('.')[1] or '',
                    'source_doc': line[16] or '',
                    'source_creation_date': line[18] or '',
                    'supplier': po[5] or '',
                    'supplier_ref': po[6] and '.' in po[6] and po[6].split('.')[1] or '',
                    # new
                    'order_type': get_sel(self.cr, self.uid, 'purchase.order', 'order_type', po[7],
                                          context=self.localcontext) or '',
                    'order_category': get_sel(self.cr, self.uid, 'purchase.order', 'categ', po[12],
                                              context=self.localcontext) or '',
                    'priority': get_sel(self.cr, self.uid, 'purchase.order', 'priority', po[13],
                                        context=self.localcontext) or '',
                    'currency': po[8] or '',
                    'total_currency': self.get_total_currency(spl.get('price_unit'), spl.get('state') == 'done' and spl.get('product_qty', 0.0) or 0.0),
                    'total_func_currency': self.get_total_func_currency(
                        line[0],
                        spl.get('price_unit', 0.0),
                        spl.get('state') == 'done' and spl.get('product_qty', 0.0) or 0.0
                    ),
                    'po_details': po[10] or '',
                    'mml_status': mml_msl_status['mml_status'],
                    'msl_status': mml_msl_status['msl_status'],
                }
                report_lines.append(report_line)

                # if spl.get('backorder_id') and spl.get('state') != 'done':
                #     report_line['qty_backordered'] = spl.get('product_qty', '')

                if first_line:
                    if export_format != 'xls':
                        report_lines.extend(self.printAnalyticLines(analytic_lines))
                    first_line = False

            for ol in other_product:
                prod_brw = prod_obj.browse(self.cr, self.uid, ol.get('product_id'),
                                           fields_to_fetch=['default_code', 'name'], context=self.localcontext)
                report_line = {
                    'order_ref': po[2] or '',
                    'order_created': po[3],
                    'order_confirmed_date': ol.get('date_expected') or line[9] or po[9],
                    'delivery_requested_date': line[10],
                    'estimated_delivery_date': edd,
                    'raw_state': line[1],
                    'order_status': po_state,
                    'line_status': get_sel(self.cr, self.uid, 'purchase.order.line', 'state', line[1],
                                           context=self.localcontext) or '',
                    'state': get_sel(self.cr, self.uid, 'purchase.order.line', 'state_to_display', line[1],
                                     context=self.localcontext) or '',
                    'item': line[2] or '',
                    'code': prod_brw.default_code or '',
                    'description': prod_brw.name or '',
                    'qty_ordered': '',
                    'uom': uom_obj.read(self.cr, self.uid, ol.get('product_uom'), ['name'])['name'],
                    'qty_received': ol.get('state') == 'done' and ol.get('product_qty', '') or '0.00',
                    'in': ol.get('name', '') or '',
                    'qty_backordered': self.get_qty_backordered(line[0], first_line and line[11] or 0.0, ol.get('state') == 'done' and ol.get('product_qty', 0.0) or 0.0, first_line),
                    'destination': analytic_lines[0].get('destination'),
                    'cost_centre': analytic_lines[0].get('cost_center'),
                    'unit_price': line[12] or '',
                    'in_unit_price': ol.get('price_unit'),
                    'customer': line[13] and line[14] or '',
                    'customer_ref': line[13] and line[15] and '.' in line[15] and line[15].split('.')[1] or '',
                    'source_doc': line[16] or '',
                    'source_creation_date': line[18] or '',
                    'supplier': po[5] or '',
                    'supplier_ref': po[6] and '.' in po[6] and po[6].split('.')[1] or '',
                    # new
                    'order_type': get_sel(self.cr, self.uid, 'purchase.order', 'order_type', po[7],
                                          context=self.localcontext) or '',
                    'order_category': get_sel(self.cr, self.uid, 'purchase.order', 'categ', po[12],
                                              context=self.localcontext) or '',
                    'priority': get_sel(self.cr, self.uid, 'purchase.order', 'priority', po[13],
                                        context=self.localcontext) or '',
                    'currency': po[8] or '',
                    'total_currency': self.get_total_currency(ol.get('price_unit'), ol.get('state') == 'done' and ol.get('product_qty', 0.0) or 0.0),
                    'total_func_currency': self.get_total_func_currency(
                        line[0],
                        ol.get('price_unit', 0.0),
                        ol.get('state') == 'done' and ol.get('product_qty', 0.0) or 0.0
                    ),
                    'po_details': po[10] or '',
                    'mml_status': mml_msl_status['mml_status'],
                    'msl_status': mml_msl_status['msl_status'],
                }
                report_lines.append(report_line)

            # Background
            if 'processed_pos' in self.localcontext and po_id not in self.localcontext['processed_pos']:
                self._order_iterator += 1
                self.localcontext['processed_pos'].append(po_id)
            if self.back_browse:
                percent = float(self._order_iterator) / float(self._nb_orders)
                self.pool.get('memory.background.report').update_percent(self.cr, self.uid, [self.back_browse.id], percent)

        if pending_only_ok:
            report_lines = self.filter_pending_only(report_lines)

        return report_lines

    def getAnalyticLines(self, po, po_line):
        ccdl_obj = self.pool.get('cost.center.distribution.line')
        blank_dist = [{'cost_center': '','destination': ''}]
        if po_line[3]:
            dist_id = po_line[3]
        elif po[4]:
            dist_id = po[4]  # get it from the header
        else:
            return blank_dist
        ccdl_ids = ccdl_obj.search(self.cr, self.uid, [('distribution_id','=',dist_id)])
        ccdl_rows = ccdl_obj.browse(self.cr, self.uid, ccdl_ids)
        dist_lines = [{'cost_center': ccdl.analytic_id.code,'destination': ccdl.destination_id.code, 'raw_state': po_line[1]} for ccdl in ccdl_rows]
        if not dist_lines:
            return blank_dist
        return dist_lines

    def getAllLineIN(self, po_line_id):
        self.cr.execute('''
            SELECT
                sm.id, sp.name, sm.product_id, sm.product_qty,
                sm.product_uom, sm.price_unit, sm.state,
                sp.backorder_id, sm.picking_id, sm.date_expected
            FROM
                stock_move sm, stock_picking sp
            WHERE
                sm.purchase_line_id = %s
              AND
                sm.type = 'in'
              AND
                sm.picking_id = sp.id
            ORDER BY
                sp.name, sp.backorder_id, sm.id asc''', tuple([po_line_id]))
        for res in self.cr.dictfetchall():
            yield res

        return

    def getReportHeaderLine1(self):
        return self.datas.get('report_header')[0]

    def getReportHeaderLine2(self):
        return self.datas.get('report_header')[1]

    def getPOLineHeaders(self):
        return [
            _('Order Reference'),
            _('Supplier'),
            _('Order Type'),
            _('Order Category'),
            _('Priority'),
            _('Line'),
            _('Product Code'),
            _('Product Description'),
            _('Qty ordered'),
            _('UoM'),
            _('Qty received'),
            _('IN Reference'),
            _('Qty backorder'),
            _('PO Unit Price (Currency)'),
            _('IN unit price (Currency)'),
            _('Currency'),
            _('Total value received (Currency)'),
            _('Total value received (Functional Currency)'),
            _('Created'),
            _('Requested Delivery Date'),
            _('Estimated Delivery Date'),
            _('Confirmed Delivery Date'),
            _('PO Line Status'),
            _('PO Document Status'),
            _('PO Details'),
            _('Customer'),
            _('Customer Reference'),
            _('Source Document'),
            _('Source Creation Date'),
            _('Supplier Reference'),
            _('MML'),
            _('MSL'),
        ]


class parser_po_follow_up_xls(po_follow_up_mixin, report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(parser_po_follow_up_xls, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getLang': self._get_lang,
            'getReportHeaderLine1': self.getReportHeaderLine1,
            'getReportHeaderLine2': self.getReportHeaderLine2,
            'getAllLineIN': self.getAllLineIN,
            'getPOLines': self.getPOLines,
            'getPOLineHeaders': self.getPOLineHeaders,
            'getRunParms': self.getRunParms,
            'getLineStyle': self.getLineStyle,
        })
        self._order_iterator = 0
        self._nb_orders = context.get('nb_orders', 0)

        if context.get('background_id'):
            self.back_browse = self.pool.get('memory.background.report').browse(self.cr, self.uid, context['background_id'])
        else:
            self.back_browse = None

    def _get_lang(self):
        return self.localcontext.get('lang', 'en_MF')


class po_follow_up_report_xls(SpreadsheetReport):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(po_follow_up_report_xls, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(po_follow_up_report_xls, self).create(cr, uid, ids, data, context=context)
        return (a[0], 'xls')


po_follow_up_report_xls('report.po.follow.up_xls', 'purchase.order', 'addons/msf_supply_doc_export/report/report_po_follow_up_xls.mako', parser=parser_po_follow_up_xls, header='internal')


class parser_po_follow_up_rml(po_follow_up_mixin, report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(parser_po_follow_up_rml, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getPOLines': self.getPOLines,
            'getReportHeaderLine1': self.getReportHeaderLine1,
            'getReportHeaderLine2': self.getReportHeaderLine2,
            'getRunParmsRML': self.getRunParmsRML,
        })
        self._order_iterator = 0
        self._nb_orders = context.get('nb_orders', 0)

        if context.get('background_id'):
            self.back_browse = self.pool.get('memory.background.report').browse(self.cr, self.uid, context['background_id'])
        else:
            self.back_browse = None


report_sxw.report_sxw('report.po.follow.up_rml', 'purchase.order', 'addons/msf_supply_doc_export/report/report_po_follow_up.rml', parser=parser_po_follow_up_rml, header=False)


class supplier_performance_report_parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(supplier_performance_report_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'parseDateXls': self._parse_date_xls,
            'getLines': self.get_lines,
        })

        self._order_iterator = 0
        self._nb_orders = 0
        if context.get('background_id'):
            self.back_browse = self.pool.get('memory.background.report').browse(self.cr, self.uid, context['background_id'])
        else:
            self.back_browse = None

    def _parse_date_xls(self, dt_str, is_datetime=True):
        if not dt_str or dt_str == 'False':
            return ''
        if is_datetime:
            dt_str = dt_str[0:10] if len(dt_str) >= 10 else ''
        if dt_str:
            dt_str += 'T00:00:00.000'
        return dt_str

    def get_diff_date_days(self, date1, date2):
        if not (self.isDate(date1) or self.isDateTime(date1)) or not (self.isDate(date2) or self.isDateTime(date2)):
            return '-'
        date1 = datetime.strptime(date1[0:10], '%Y-%m-%d')
        date2 = datetime.strptime(date2[0:10], '%Y-%m-%d')

        return (date2 - date1).days

    def get_lines(self, wizard):
        supl_info_obj = self.pool.get('product.supplierinfo')
        po_obj = self.pool.get('purchase.order')
        catl_obj = self.pool.get('supplier.catalogue.line')
        curr_obj = self.pool.get('res.currency')
        lines = []

        self._nb_orders = len(wizard.pol_ids)


        invoices = {}

        self.cr.execute('''
            select i.picking_id as pick_id, l.order_line_id as pol_id, i.number as inv_number, i.currency_id as curr_id, sum(l.price_unit*l.quantity) as price_total, sum(l.quantity) as qty,  i.date_invoice as date, i.document_date as document_date
            from
                account_invoice i, account_invoice_line l
            where
                i.type = 'in_invoice' and
                l.invoice_id = i.id and
                l.order_line_id in %s and
                i.state != 'cancel'
            group by i.currency_id, i.picking_id, l.order_line_id, i.number, i.date_invoice, i.document_date
        ''', (tuple(wizard.pol_ids),)
        )
        for inv in self.cr.dictfetchall():
            key = (inv['pick_id'], inv['pol_id'])
            if key not in invoices:
                invoices[key] = inv
            else:
                ex_curr = invoices[key]['curr_id']
                if inv['curr_id'] != ex_curr:
                    curr_date = currency_date.get_date(self, self.cr, inv['document_date'], inv['date'])
                    price = curr_obj.compute(self.cr, self.uid, inv['curr_id'], ex_curr, inv['price_total'], round=False,
                                             context={'currency_date': curr_date or time.strftime('%Y-%m-%d')})
                else:
                    price = inv['price_total']
                invoices[key]['price_total'] += price*inv['qty']
                invoices[key]['qty'] += inv['qty']


        po_type = dict(po_obj.fields_get(self.cr, self.uid, ['order_type'], context=self.localcontext)['order_type']['selection'])
        self.cr.execute('''
            SELECT
                pl.id, -- 0
                pl.product_id, -- 1
                pl.line_number, -- 2
                pl.product_qty, -- 3
                pl.price_unit, -- 4
                pl.state, -- 5
                pl.create_date::timestamp(0), -- 6
                pl.validation_date, -- 7
                pl.confirmation_date, -- 8
                pl.confirmed_delivery_date, -- 9
                pl.comment, -- 10
                p.name, -- 11
                p.delivery_requested_date, -- 12
                pp.default_code, -- 13
                COALESCE(tr.value, pt.name), -- 14
                rp.name, -- 15
                rp.supplier_lt, -- 16
                c.id, -- 17
                c.name, -- 18
                m.id, -- 19
                m.price_unit, -- 20
                m.product_qty, -- 21
                sp.name, -- 22
                sp.physical_reception_date, -- 23
                c2.id, -- 24
                rp.id, -- 25
                sp.id, -- 26
                p.order_type, -- 27
                fo_partner.name, -- 28
                COALESCE(pl.esti_dd, p.delivery_requested_date_modified), --29
                p.details --30
            FROM purchase_order_line pl
                LEFT JOIN purchase_order p ON p.id = pl.order_id
                LEFT JOIN product_product pp ON pp.id = pl.product_id
                LEFT JOIN res_partner rp ON rp.id = pl.partner_id
                LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
                LEFT JOIN ir_translation tr ON tr.res_id = pt.id AND tr.name = 'product.template,name' AND tr.lang = %s
                LEFT JOIN product_pricelist pr ON pr.id = p.pricelist_id
                LEFT JOIN res_currency c ON c.id = pr.currency_id
                LEFT JOIN stock_move m ON m.purchase_line_id = pl.id AND m.type = 'in'
                LEFT JOIN stock_picking sp ON sp.id = m.picking_id
                LEFT JOIN res_currency c2 ON c2.id = m.price_currency_id
                LEFT JOIN sale_order_line sol ON sol.id = pl.linked_sol_id
                LEFT JOIN sale_order so ON so.id = sol.order_id
                LEFT JOIN res_partner fo_partner ON fo_partner.id = so.partner_id
            WHERE pl.id IN %s
            ORDER BY p.id DESC, pl.line_number ASC, sp.id ASC
        ''', (self.localcontext.get('lang', 'en_MF'), tuple(wizard.pol_ids)))

        for line in self.cr.fetchall():
            # Catalogue
            cat_unit_price = '-'
            func_cat_unit_price = '-'
            if line[1]:
                supl_info_domain = [('product_id', '=', line[1]), ('active', '=', True), ('catalogue_id', '!=', False),
                                    ('catalogue_id.partner_id', '=', line[25]), ('catalogue_id.currency_id', '=', line[17])]
                supl_info_ids = supl_info_obj.search(self.cr, self.uid, supl_info_domain, limit=1,
                                                     order='sequence asc', context=self.localcontext)
                if supl_info_ids:
                    catalogue = supl_info_obj.browse(self.cr, self.uid, supl_info_ids[0],
                                                     fields_to_fetch=['catalogue_id'], context=self.localcontext).catalogue_id
                    cat_line_domain = [('product_id', '=', line[1]), ('catalogue_id', '=', catalogue.id)]
                    cat_line_ids = catl_obj.search(self.cr, self.uid, cat_line_domain, limit=1, context=self.localcontext)
                    if cat_line_ids:
                        cat_unit_price_raw = catl_obj.browse(self.cr, self.uid, cat_line_ids[0], fields_to_fetch=['unit_price'],
                                                             context=self.localcontext).unit_price
                        cat_unit_price = round(curr_obj.compute(self.cr, self.uid, catalogue.currency_id.id, line[17],
                                                                cat_unit_price_raw, round=False, context=self.localcontext), 2)
                        func_cat_unit_price = round(curr_obj.compute(self.cr, self.uid, catalogue.currency_id.id,
                                                                     wizard.company_currency_id.id, cat_unit_price_raw,
                                                                     round=False, context=self.localcontext), 2)

            # Different unit prices
            in_unit_price, func_in_unit_price = '-', '-'
            if line[19]:
                in_unit_price = line[20] or 0.00
                func_in_unit_price = round(curr_obj.compute(self.cr, self.uid, line[24], wizard.company_currency_id.id,
                                                            in_unit_price, round=False, context=self.localcontext), 2)
            si_unit_price, func_si_unit_price = '-', '-'
            si_ref = ''
            key = (line[26], line[0])
            if key in invoices and invoices[key]['qty']:
                si_ref = invoices[key]['inv_number'] or ''
                si_unit_price = invoices[key]['price_total'] / invoices[key]['qty']
                if invoices[key]['curr_id'] != line[24]:
                    curr_date = currency_date.get_date(self, self.cr, invoices[key]['document_date'], invoices[key]['date'])
                    si_unit_price = curr_obj.compute(self.cr, self.uid, invoices[key]['curr_id'], line[24], si_unit_price, round=False,
                                                     context={'currency_date': curr_date or time.strftime('%Y-%m-%d')})
                func_si_unit_price = round(curr_obj.compute(self.cr, self.uid, invoices[key]['curr_id'], wizard.company_currency_id.id,
                                                            si_unit_price, round=False, context=self.localcontext), 2)
            func_pol_unit_price = round(curr_obj.compute(self.cr, self.uid, line[17], wizard.company_currency_id.id,
                                                         line[4], round=False, context=self.localcontext), 2)

            # Discrepancies
            discrep_in_po, discrep_si_po, func_discrep_in_po, func_discrep_si_po = '-', '-', '-', '-'
            if in_unit_price != '-':
                discrep_in_po = round(in_unit_price - line[4], 4)
            if si_unit_price != '-':
                discrep_si_po = round(si_unit_price - line[4], 4)
            if func_in_unit_price != '-':
                func_discrep_in_po = round(func_in_unit_price - func_pol_unit_price, 4)
            if func_si_unit_price != '-':
                func_discrep_si_po = round(func_si_unit_price - func_pol_unit_price, 4)

            # Dates comparison and Actual Supplier Lead Time
            days_cdd_receipt, days_rdd_receipt, days_crea_receipt, act_sup_lt, discrep_lt_act_theo = '-', '-', '-', '-', '-'
            if line[18]:
                days_cdd_receipt = self.get_diff_date_days(line[9], line[23])
                days_rdd_receipt = self.get_diff_date_days(line[12], line[23])
                days_crea_receipt = self.get_diff_date_days(line[6], line[23])
                act_sup_lt = self.get_diff_date_days(line[7], line[23])

            if act_sup_lt != '-':
                discrep_lt_act_theo = act_sup_lt - line[16]

            lines.append({
                'partner_name': line[15],
                'details': line[30] or '',
                'po_name': line[11],
                'in_ref': line[22] or '',
                'si_ref': si_ref,
                'line_number': line[2],
                'p_code': line[13],
                'p_name': line[14],
                'state': line[5],
                'qty_ordered': line[3],
                'qty_received': line[21] or 0,
                'currency': line[18],
                'cat_unit_price': cat_unit_price,
                'po_unit_price': line[4],
                'in_unit_price': in_unit_price,
                'si_unit_price': si_unit_price,
                'discrep_in_po': discrep_in_po,
                'discrep_si_po': discrep_si_po,
                'func_cat_unit_price': func_cat_unit_price,
                'func_po_unit_price': func_pol_unit_price,
                'func_in_unit_price': func_in_unit_price,
                'func_si_unit_price': func_si_unit_price,
                'func_discrep_in_po': func_discrep_in_po,
                'func_discrep_si_po': func_discrep_si_po,
                'po_crea_date': line[6],
                'po_vali_date': line[7],
                'po_conf_date': line[8],
                'po_rdd': line[12],
                'po_edd': line[29],
                'po_cdd': line[9],
                'in_receipt_date': line[23],
                'days_crea_vali': self.get_diff_date_days(line[6], line[7]),
                'days_crea_conf': self.get_diff_date_days(line[6], line[8]),
                'days_cdd_receipt': days_cdd_receipt,
                'days_rdd_receipt': days_rdd_receipt,
                'days_crea_receipt': days_crea_receipt,
                'days_vali_receipt': act_sup_lt,
                'partner_lt': line[16],
                'discrep_lt_act_theo': discrep_lt_act_theo,
                'order_type': po_type.get(line[27], ''),
                'customer': line[27] == 'direct' and line[28] or '',
            })

            self._order_iterator += 1
            if self.back_browse:
                percent = float(self._order_iterator) / float(self._nb_orders)
                self.pool.get('memory.background.report').update_percent(self.cr, self.uid, [self.back_browse.id], percent)

        return lines


class supplier_performance_report_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse,
                 header='external', store=False):
        super(supplier_performance_report_xls, self).__init__(name, table,
                                                              rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(supplier_performance_report_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')


supplier_performance_report_xls(
    'report.supplier.performance.report_xls',
    'supplier.performance.wizard',
    'msf_supply_doc_export/report/supplier_performance_report_xls.mako',
    parser=supplier_performance_report_parser,
    header=False
)


class ir_values(osv.osv):
    """
    we override ir.values because we need to filter where the button to print report is displayed (this was also done in register_accounting/account_bank_statement.py)
    """
    _name = 'ir.values'
    _inherit = 'ir.values'


    def get(self, cr, uid, key, key2, models, meta=False, context=None, res_id_req=False, without_user=True, key2_req=True, view_id=False):
        if context is None:
            context = {}
        values = super(ir_values, self).get(cr, uid, key, key2, models, meta, context, res_id_req, without_user, key2_req, view_id=view_id)

        if key == 'action' and key2 == 'client_print_multi' and 'composition.kit' in [x[0] for x in models]:
            new_act = []
            for v in values:
                if context.get('composition_type')=='theoretical' and v[2].get('report_name', False) in ('composition.kit.xls', 'kit.report'):
                    if v[2].get('report_name', False) == 'kit.report':
                        v[2]['name'] = _('Theoretical Kit')
                    new_act.append(v)
                elif context.get('composition_type')=='real' and v[2].get('report_name', False) in ('real.composition.kit.xls', 'kit.report'):
                    if v[2].get('report_name', False) == 'kit.report':
                        v[2]['name'] = _('Kit Composition')
                    new_act.append(v)
            values = new_act

        return values

ir_values()
