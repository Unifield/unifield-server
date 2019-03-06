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
from osv import osv
from report_webkit.webkit_report import WebKitParser as OldWebKitParser
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _
from purchase import PURCHASE_ORDER_STATE_SELECTION
from datetime import datetime

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
            dict_res.setdefault(m.line_number, {})
            if m.product_id.id not in dict_res[m.line_number]:
                dict_res[m.line_number][m.product_id.id] = 1

        for ln in dict_res.values():
            for p in ln.values():
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


class tender_report_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(tender_report_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(tender_report_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

tender_report_xls('report.tender_xls','tender','addons/msf_supply_doc_export/report/report_tender_xls.mako')

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


def get_back_browse(self, cr, uid, context):
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

    def getHeaderLine(self,obj):
        ''' format the header line for each PO object '''
        po_header = []
        po_header.append('Order ref: ' + obj.name)
        po_header.append('Status: ' + self._get_states().get(obj.state, ''))
        po_header.append('Created: ' + obj.date_order)
        po_header.append('Confirmed delivery date: ' + obj.delivery_confirmed_date)
        po_header.append('Nb items: ' + str(len(obj.order_line)))
        po_header.append('Estimated amount: ' + str(obj.amount_total))
        return po_header

    def getHeaderLine2(self,obj):
        ''' format the header line for each PO object '''
        po_header = {}
        po_header['ref'] = 'Order ref: ' + obj.name
        po_header['status'] = 'Status: ' + self._get_states().get(obj.state, '')
        po_header['created'] = 'Created: ' + obj.date_order
        po_header['deldate'] = 'Confirmed delivery date: ' + obj.delivery_confirmed_date
        po_header['items'] = 'Nb items: ' + str(len(obj.order_line))
        po_header['amount'] = 'Estimated amount: ' + str(obj.amount_total)
        line = po_header['ref'] + po_header['status'] + po_header['created'] + po_header['deldate'] + po_header['items'] + po_header['amount']
        return line

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
            report_line['qty_ordered'] = ''
            report_line['uom'] = ''
            report_line['qty_received'] = ''
            report_line['in'] = ''
            report_line['qty_backordered'] = ''
            report_line['unit_price'] = ''
            report_line['in_unit_price'] = ''
            report_line['delivery_requested_date'] = ''
            report_line['customer'] = ''
            report_line['customer_ref'] = ''
            report_line['source_doc'] = ''
            report_line['supplier'] = ''
            report_line['supplier_ref'] = ''
            report_line['order_type'] = ''
            report_line['currency'] = ''
            report_line['total_currency'] = ''
            report_line['total_func_currency'] = ''
            report_line['destination'] = analytic_line.get('destination')
            report_line['cost_centre'] = analytic_line.get('cost_center')
            res.append(report_line)

        return res

    def yieldPoLines(self, po_line_ids):
        for pol_id in po_line_ids:
            yield self.pool.get('purchase.order.line').browse(self.cr, self.uid, pol_id, context=self.localcontext)

        raise StopIteration

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
            context.update({'date': pol.closed_date})
        elif pol.confirmation_date:
            context.update({'date': pol.confirmation_date})
        elif pol.validation_date:
            context.update({'date': pol.validation_date})
        elif pol.create_date: # could be null, because not mandatory in DB
            context.update({'date': pol.create_date})
        else:
            context.update({'date': datetime.now().strftime('%Y-%m-%d')})

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
        if pol.state.startswith('cancel'):
            return '0.00'
        if not qty_ordered:
            return '0.00'
        try:
            qty_ordered = float(qty_ordered)
            qty_received = float(qty_received)
        except:
            return '0.00'

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


    def format_date(self, date):
        if not date:
            return ''
        time_tuple = time.strptime(date, '%Y-%m-%d')
        new_date = time.strftime('%d.%m.%Y', time_tuple)

        return new_date


    def getPOLines(self, po_id):
        ''' developer note: would be a lot easier to write this as a single sql and then use on-break '''
        po_obj = self.pool.get('purchase.order')
        pol_obj = self.pool.get('purchase.order.line')
        prod_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        get_sel = self.pool.get('ir.model.fields').get_selection
        po_line_ids = pol_obj.search(self.cr, self.uid, [('order_id','=',po_id)], order='line_number')
        report_lines = []
        order = po_obj.browse(self.cr, self.uid, po_id)
        for line in self.yieldPoLines(po_line_ids):
            analytic_lines = self.getAnalyticLines(line)
            same_product_same_uom = []
            same_product = []
            other_product = []

            for inl in self.getAllLineIN(line.id):
                if inl.get('product_id') and inl.get('product_id') == line.product_id.id:
                    if inl.get('product_uom') and inl.get('product_uom') == line.product_uom.id:
                        same_product_same_uom.append(inl)
                    else:
                        same_product.append(inl)
                else:
                    other_product.append(inl)

            first_line = True
            # Display information of the initial reception
            if not same_product_same_uom:
                report_line = {
                    'order_ref': order.name or '',
                    'order_created': self.format_date(order.date_order),
                    'order_confirmed_date': self.format_date(line.confirmed_delivery_date),
                    'delivery_requested_date': self.format_date(line.date_planned),
                    'raw_state': line.state,
                    'line_status': get_sel(self.cr, self.uid, 'purchase.order.line', 'state', line.state, {}) or '',
                    'state': line.state_to_display or '',
                    'order_status': self._get_states().get(order.state, ''),
                    'item': line.line_number or '',
                    'code': line.product_id.default_code or '',
                    'description': line.product_id.name or '',
                    'qty_ordered': line.product_qty or '',
                    'uom': line.product_uom.name or '',
                    'qty_received': '0.00',
                    'in': '',
                    'qty_backordered': self.get_qty_backordered(line.id, line.product_qty, 0.0, first_line),
                    'destination': analytic_lines[0].get('destination'),
                    'cost_centre': analytic_lines[0].get('cost_center'),
                    'unit_price': line.price_unit or '',
                    'in_unit_price': '',
                    'customer': line.linked_sol_id and line.linked_sol_id.order_id.partner_id.name or '',
                    'customer_ref': line.linked_sol_id and line.linked_sol_id.order_id.client_order_ref and '.' in line.linked_sol_id.order_id.client_order_ref and line.linked_sol_id.order_id.client_order_ref.split('.')[1] or '',
                    'source_doc': line.origin or '',
                    'supplier': line.order_id.partner_id.name or '',
                    'supplier_ref': line.order_id.partner_ref and '.' in line.order_id.partner_ref and line.order_id.partner_ref.split('.')[1] or '',
                    # new
                    'order_type': get_sel(self.cr, self.uid, 'purchase.order', 'order_type', line.order_id.order_type, {}) or '',
                    'currency': line.order_id.pricelist_id.currency_id.name or '',
                    'total_currency': '',
                    'total_func_currency': '',
                }
                report_lines.append(report_line)
                report_lines.extend(self.printAnalyticLines(analytic_lines))
                first_line = False

            for spsul in sorted(same_product_same_uom, key=lambda spsu: spsu.get('backorder_id'), reverse=True):
                report_line = {
                    'order_ref': order.name or '',
                    'order_created': self.format_date(order.date_order),
                    'order_confirmed_date': self.format_date(line.confirmed_delivery_date or order.delivery_confirmed_date),
                    'delivery_requested_date': self.format_date(line.date_planned),
                    'raw_state': line.state,
                    'order_status': self._get_states().get(order.state, ''),
                    'line_status': first_line and get_sel(self.cr, self.uid, 'purchase.order.line', 'state', line.state, {}) or '',
                    'state': line.state_to_display or '',
                    'item': line.line_number or '',
                    'code': line.product_id.default_code or '',
                    'description': line.product_id.name or '',
                    'qty_ordered': first_line and line.product_qty or '',
                    'uom': line.product_uom.name or '',
                    'qty_received': spsul.get('state') == 'done' and spsul.get('product_qty', '') or '0.00',
                    'in': spsul.get('name', '') or '',
                    'qty_backordered': self.get_qty_backordered(line.id, first_line and line.product_qty or 0.0, spsul.get('state') == 'done' and spsul.get('product_qty', 0.0) or 0.0, first_line),
                    'destination': analytic_lines[0].get('destination'),
                    'cost_centre': analytic_lines[0].get('cost_center'),
                    'unit_price': line.price_unit or '',
                    'in_unit_price': spsul.get('price_unit'),
                    'customer': line.linked_sol_id and line.linked_sol_id.order_id.partner_id.name or '',
                    'customer_ref': line.linked_sol_id and line.linked_sol_id.order_id.client_order_ref and '.' in line.linked_sol_id.order_id.client_order_ref and line.linked_sol_id.order_id.client_order_ref.split('.')[1] or '',
                    'source_doc': line.origin or '',
                    'supplier': line.order_id.partner_id.name or '',
                    'supplier_ref': line.order_id.partner_ref and '.' in line.order_id.partner_ref and line.order_id.partner_ref.split('.')[1] or '',
                    # new
                    'order_type': get_sel(self.cr, self.uid, 'purchase.order', 'order_type', line.order_id.order_type, {}) or '',
                    'currency': line.order_id.pricelist_id.currency_id.name or '',
                    'total_currency': self.get_total_currency(spsul.get('price_unit'), spsul.get('state') == 'done' and spsul.get('product_qty', '') or 0.0),
                    'total_func_currency': self.get_total_func_currency(
                        line.id,
                        spsul.get('price_unit', 0.0),
                        spsul.get('state') == 'done' and spsul.get('product_qty', 0.0) or 0.0
                    ),
                }

                report_lines.append(report_line)

                # if spsul.get('backorder_id') and spsul.get('state') != 'done':
                #     report_line['qty_backordered'] = spsul.get('product_qty', '')

                if first_line:
                    report_lines.extend(self.printAnalyticLines(analytic_lines))
                    first_line = False

            for spl in sorted(same_product, key=lambda spsu: spsu.get('backorder_id'), reverse=True):
                report_line = {
                    'order_ref': order.name or '',
                    'order_created': self.format_date(order.date_order),
                    'order_confirmed_date': self.format_date(line.confirmed_delivery_date or order.delivery_confirmed_date),
                    'delivery_requested_date': self.format_date(line.date_planned),
                    'raw_state': line.state,
                    'order_status': self._get_states().get(order.state, ''),
                    'line_status': first_line and get_sel(self.cr, self.uid, 'purchase.order.line', 'state', line.state, {}) or '',
                    'state': line.state_to_display or '',
                    'item': line.line_number or '',
                    'code': line.product_id.default_code or '',
                    'description': line.product_id.name or '',
                    'qty_ordered': first_line and line.product_qty or '',
                    'uom': uom_obj.read(self.cr, self.uid, spl.get('product_uom'), ['name'])['name'],
                    'qty_received': spl.get('state') == 'done' and spl.get('product_qty', '') or '0.00',
                    'in': spl.get('name', '') or '',
                    'qty_backordered': self.get_qty_backordered(line.id, first_line and line.product_qty or 0.0, spl.get('state') == 'done' and spl.get('product_qty', 0.0) or 0.0, first_line),
                    'destination': analytic_lines[0].get('destination'),
                    'cost_centre': analytic_lines[0].get('cost_center'),
                    'unit_price': line.price_unit or '',
                    'in_unit_price': spl.get('price_unit'),
                    'customer': line.linked_sol_id and line.linked_sol_id.order_id.partner_id.name or '',
                    'customer_ref': line.linked_sol_id and line.linked_sol_id.order_id.client_order_ref and '.' in line.linked_sol_id.order_id.client_order_ref and line.linked_sol_id.order_id.client_order_ref.split('.')[1] or '',
                    'source_doc': line.origin or '',
                    'supplier': line.order_id.partner_id.name or '',
                    'supplier_ref': line.order_id.partner_ref and '.' in line.order_id.partner_ref and line.order_id.partner_ref.split('.')[1] or '',
                    # new
                    'order_type': get_sel(self.cr, self.uid, 'purchase.order', 'order_type', line.order_id.order_type, {}) or '',
                    'currency': line.order_id.pricelist_id.currency_id.name or '',
                    'total_currency': self.get_total_currency(spl.get('price_unit'), spl.get('state') == 'done' and spl.get('product_qty', 0.0) or 0.0),
                    'total_func_currency': self.get_total_func_currency(
                        line.id,
                        spl.get('price_unit', 0.0),
                        spl.get('state') == 'done' and spl.get('product_qty', 0.0) or 0.0
                    ),
                }
                report_lines.append(report_line)

                # if spl.get('backorder_id') and spl.get('state') != 'done':
                #     report_line['qty_backordered'] = spl.get('product_qty', '')

                if first_line:
                    report_lines.extend(self.printAnalyticLines(analytic_lines))
                    first_line = False

            for ol in other_product:
                prod_brw = prod_obj.browse(self.cr, self.uid, ol.get('product_id'))
                report_line = {
                    'order_ref': order.name or '',
                    'order_created': self.format_date(order.date_order),
                    'order_confirmed_date': self.format_date(line.confirmed_delivery_date or order.delivery_confirmed_date),
                    'delivery_requested_date': self.format_date(line.date_planned),
                    'raw_state': line.state,
                    'order_status': self._get_states().get(order.state, ''),
                    'line_status': get_sel(self.cr, self.uid, 'purchase.order.line', 'state', line.state, {}) or '',
                    'state': line.state_to_display or '',
                    'item': line.line_number or '',
                    'code': prod_brw.default_code or '',
                    'description': prod_brw.name or '',
                    'qty_ordered': '',
                    'uom': uom_obj.read(self.cr, self.uid, ol.get('product_uom'), ['name'])['name'],
                    'qty_received': ol.get('state') == 'done' and ol.get('product_qty', '') or '0.00',
                    'in': ol.get('name', '') or '',
                    'qty_backordered': self.get_qty_backordered(line.id, first_line and line.product_qty or 0.0, ol.get('state') == 'done' and ol.get('product_qty', 0.0) or 0.0, first_line),
                    'destination': analytic_lines[0].get('destination'),
                    'cost_centre': analytic_lines[0].get('cost_center'),
                    'unit_price': line.price_unit or '',
                    'in_unit_price': ol.get('price_unit'),
                    'customer': line.linked_sol_id and line.linked_sol_id.order_id.partner_id.name or '',
                    'customer_ref': line.linked_sol_id and line.linked_sol_id.order_id.client_order_ref and '.' in line.linked_sol_id.order_id.client_order_ref and line.linked_sol_id.order_id.client_order_ref.split('.')[1] or '',
                    'source_doc': line.origin or '',
                    'supplier': line.order_id.partner_id.name or '',
                    'supplier_ref': line.order_id.partner_ref and '.' in line.order_id.partner_ref and line.order_id.partner_ref.split('.')[1] or '',
                    # new
                    'order_type': get_sel(self.cr, self.uid, 'purchase.order', 'order_type', line.order_id.order_type, {}) or '',
                    'currency': line.order_id.pricelist_id.currency_id.name or '',
                    'total_currency': self.get_total_currency(ol.get('price_unit'), ol.get('state') == 'done' and ol.get('product_qty', 0.0) or 0.0),
                    'total_func_currency': self.get_total_func_currency(
                        line.id,
                        ol.get('price_unit', 0.0),
                        ol.get('state') == 'done' and ol.get('product_qty', 0.0) or 0.0
                    ),
                }
                report_lines.append(report_line)

        return report_lines

    def getAnalyticLines(self,po_line):
        ccdl_obj = self.pool.get('cost.center.distribution.line')
        blank_dist = [{'cost_center': '','destination': ''}]
        if po_line.analytic_distribution_id.id:
            dist_id = po_line.analytic_distribution_id.id
        elif po_line.order_id.analytic_distribution_id:
            dist_id = po_line.order_id.analytic_distribution_id.id  # get it from the header
        else:
            return blank_dist
        ccdl_ids = ccdl_obj.search(self.cr, self.uid, [('distribution_id','=',dist_id)])
        ccdl_rows = ccdl_obj.browse(self.cr, self.uid, ccdl_ids)
        dist_lines = [{'cost_center': ccdl.analytic_id.code,'destination': ccdl.destination_id.code, 'raw_state': po_line.state} for ccdl in ccdl_rows]
        if not dist_lines:
            return blank_dist
        return dist_lines

    def getAllLineIN(self, po_line_id):
        self.cr.execute('''
            SELECT
                sm.id, sp.name, sm.product_id, sm.product_qty,
                sm.product_uom, sm.price_unit, sm.state,
                sp.backorder_id, sm.picking_id
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

        raise StopIteration

    def getReportHeaderLine1(self):
        return self.datas.get('report_header')[0]

    def getReportHeaderLine2(self):
        return self.datas.get('report_header')[1]

    def getPOLineHeaders(self):
        return [
            'Order Reference',
            'Supplier',
            'Order Type',
            'Line',
            'Product Code',
            'Product Description',
            'Qty ordered',
            'UoM',
            'Qty received',
            'IN Reference',
            'Qty backorder',
            'PO Unit Price (Currency)',
            'IN unit price (Currency)',
            'Currency',
            'Total value received (Currency)',
            'Total value received (Functional Currency)',
            'Created',
            'Delivery Requested Date',
            'Delivery Confirmed Date',
            'PO Line Status',
            'PO Document Status',
            'Customer',
            'Customer Reference',
            'Source Document',
            'Supplier Reference',
        ]


class parser_po_follow_up_xls(po_follow_up_mixin, report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(parser_po_follow_up_xls, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getHeaderLine': self.getHeaderLine,
            'getHeaderLine2': self.getHeaderLine2,
            'getReportHeaderLine1': self.getReportHeaderLine1,
            'getReportHeaderLine2': self.getReportHeaderLine2,
            'getAllLineIN': self.getAllLineIN,
            'getPOLines': self.getPOLines,
            'getPOLineHeaders': self.getPOLineHeaders,
            'getRunParms': self.getRunParms,
            'getLineStyle': self.getLineStyle,
        })




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
            'getHeaderLine2': self.getHeaderLine2,
            'getHeaderLine': self.getHeaderLine,
            'getReportHeaderLine1': self.getReportHeaderLine1,
            'getReportHeaderLine2': self.getReportHeaderLine2,
            'getRunParmsRML': self.getRunParmsRML,
        })


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
        catl_obj = self.pool.get('supplier.catalogue.line')
        curr_obj = self.pool.get('res.currency')
        lines = []

        self._nb_orders = len(wizard.pol_ids)

        self.cr.execute('''
            SELECT pl.id, pl.product_id, pl.line_number, pl.product_qty, pl.price_unit, pl.state, pl.create_date::timestamp(0), 
                pl.validation_date, pl.confirmation_date, pl.confirmed_delivery_date, pl.comment, p.name, 
                p.delivery_requested_date, pp.default_code, COALESCE(tr.value, pt.name), rp.name, rp.supplier_lt, c.id, 
                c.name, m.id, m.price_unit, m.product_qty, sp.name, sp.physical_reception_date, c2.id, al.id, al.price_unit, 
                a.number, a.name, c3.id
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
                LEFT JOIN account_invoice a ON a.picking_id = sp.id AND a.type = 'in_invoice' 
                    AND a.is_direct_invoice = 'f' AND a.is_inkind_donation = 'f' AND a.is_debit_note = 'f' 
                    AND a.is_intermission = 'f'
                LEFT JOIN account_invoice_line al ON al.invoice_id = a.id AND al.order_line_id = pl.id
                LEFT JOIN res_currency c3 ON c3.id = a.currency_id
            WHERE pl.id IN %s 
            ORDER BY p.id DESC, pl.line_number ASC
        ''', (self.localcontext.get('lang', 'en_MF'), tuple(wizard.pol_ids)))

        for line in self.cr.fetchall():
            # Catalogue
            cat_unit_price = '-'
            func_cat_unit_price = '-'
            if line[1]:
                supl_info_domain = [('product_id', '=', line[1]), ('active', '=', True), ('catalogue_id', '!=', False)]
                supl_info_ids = supl_info_obj.search(self.cr, self.uid, supl_info_domain, limit=1,
                                                     order='sequence asc', context=self.localcontext)
                if supl_info_ids:
                    catalogue = supl_info_obj.browse(self.cr, self.uid, supl_info_ids[0],
                                                     fields_to_fetch=['catalogue_id'], context=self.localcontext).catalogue_id
                    cat_line_domain = [('product_id', '=', line[1]), ('catalogue_id', '=', catalogue.id)]
                    cat_line_ids = catl_obj.search(self.cr, self.uid, cat_line_domain, limit=1, context=self.localcontext)
                    if cat_line_ids:
                        cat_unit_price = catl_obj.browse(self.cr, self.uid, cat_line_ids[0], fields_to_fetch=['unit_price'],
                                                         context=self.localcontext).unit_price
                        func_cat_unit_price = round(curr_obj.compute(self.cr, self.uid, catalogue.currency_id.id,
                                                                     wizard.company_currency_id.id, cat_unit_price,
                                                                     round=False, context=self.localcontext), 2)

            # Different unit prices
            in_unit_price, func_in_unit_price = '-', '-'
            if line[19]:
                in_unit_price = line[20] or 0.00
                func_in_unit_price = round(curr_obj.compute(self.cr, self.uid, line[24], wizard.company_currency_id.id,
                                                            in_unit_price, round=False, context=self.localcontext), 2)
            si_unit_price, func_si_unit_price = '-', '-'
            if line[25]:
                si_unit_price = line[26] or 0.00
                func_si_unit_price = round(curr_obj.compute(self.cr, self.uid, line[29], wizard.company_currency_id.id,
                                                            si_unit_price, round=False, context=self.localcontext), 2)
            func_pol_unit_price = round(curr_obj.compute(self.cr, self.uid, line[17], wizard.company_currency_id.id,
                                                         line[4], round=False, context=self.localcontext), 2)

            # Discrepancies
            discrep_in_po, discrep_si_po, func_discrep_in_po, func_discrep_si_po = '-', '-', '-', '-'
            if in_unit_price != '-':
                discrep_in_po = in_unit_price - line[4]
            if si_unit_price != '-':
                discrep_si_po = si_unit_price - line[4]
            if func_in_unit_price != '-':
                func_discrep_in_po = func_in_unit_price - func_pol_unit_price
            if func_si_unit_price != '-':
                func_discrep_si_po = func_si_unit_price - func_pol_unit_price

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
                'po_name': line[11],
                'in_ref': line[22] or '',
                'si_ref': line[27] or line[28] or '',
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
        trans_obj = self.pool.get('ir.translation')

        if key == 'action' and key2 == 'client_print_multi' and 'sale.order' in [x[0] for x in models]:
            new_act = []
            #field_orders_view = data_obj.get_object_reference(cr, uid, 'procurement_request', 'action_procurement_request')[1]
            for v in values:
                if context.get('procurement_request', False):
                    if v[2].get('report_name', False) in ('internal.request_xls', 'procurement.request.report') \
                            or v[2].get('report_name', False) in ('internal_request_export', 'procurement.request.report') \
                            or v[1] == 'action_open_wizard_import': # this is an internal request, we only display import lines for client_action_multi --- using the name of screen, and the name of the action is definitely the wrong way to go...
                        new_act.append(v)
                else:
                    if v[2].get('report_name', False) == 'msf.sale.order' \
                        or v[2].get('report_name', False) == 'sale.order_xls' \
                        or v[2].get('report_name', False) == 'sale.order.allocation.report' \
                        or v[1] == 'allocation.report' \
                            or v[1] == 'Order Follow Up': # this is a sale order, we only display Order Follow Up for client_action_multi --- using the name of screen, and the name of the action is definitely the wrong way to go...
                        new_act.append(v)
                values = new_act

        elif (context.get('_terp_view_name') or context.get('picking_type')) and key == 'action' and key2 == 'client_print_multi' and 'stock.picking' in [x[0] for x in models] and context.get('picking_type', False) != 'incoming_shipment':
            new_act = []
            Picking_Tickets = trans_obj.tr_view(cr, 'Picking Tickets', context)
            Picking_Ticket = trans_obj.tr_view(cr, 'Picking Ticket', context)
            Pre_Packing_Lists = trans_obj.tr_view(cr, 'Pre-Packing Lists', context)
            Pre_Packing_List = trans_obj.tr_view(cr, 'Pre-Packing List', context)
            Delivery_Orders = trans_obj.tr_view(cr, 'Delivery Orders', context)
            Delivery_Order = trans_obj.tr_view(cr, 'Delivery Order', context)
            Internal_Moves = trans_obj.tr_view(cr, 'Internal Moves', context)
            for v in values:
                if v[2].get('report_name', False) == 'picking.ticket' and (context.get('_terp_view_name') in (Picking_Tickets, Picking_Ticket) or context.get('picking_type') == 'picking_ticket') and context.get('picking_screen', False)\
                    or v[2].get('report_name', False) == 'pre.packing.list' and context.get('_terp_view_name') in (Pre_Packing_Lists, Pre_Packing_List) and context.get('ppl_screen', False)\
                    or v[2].get('report_name', False) == 'empty.picking.ticket' and (context.get('_terp_view_name') in (Pre_Packing_Lists, Pre_Packing_List) or context.get('picking_type', False) == 'picking_ticket')\
                    or v[2].get('report_name', False) == 'pre.packing.excel.export' and context.get('_terp_view_name') in (Pre_Packing_Lists, Pre_Packing_List) \
                    or v[2].get('report_name', False) == 'labels' and (context.get('_terp_view_name') in [Picking_Ticket, Picking_Tickets, Pre_Packing_List, Pre_Packing_Lists, Delivery_Orders, Delivery_Order] or context.get('picking_type', False) in ('delivery_order', 'picking_ticket'))\
                    or v[2].get('report_name', False) in ('internal.move.xls', 'internal.move') and (('_terp_view_name' in context and context['_terp_view_name'] in [Internal_Moves]) or context.get('picking_type') == 'internal_move') \
                        or v[2].get('report_name', False) == 'delivery.order' and (context.get('_terp_view_name') in [Delivery_Orders, Delivery_Order] or context.get('picking_type', False) == 'delivery_order'):
                    new_act.append(v)
                values = new_act
        elif context.get('_terp_view_name') and key == 'action' and key2 == 'client_print_multi' and 'shipment' in [x[0] for x in models]:
            new_act = []
            Packing_Lists = trans_obj.tr_view(cr, 'Packing Lists', context)
            Packing_List = trans_obj.tr_view(cr, 'Packing List', context)
            Shipment_Lists = trans_obj.tr_view(cr, 'Shipment Lists', context)
            Shipment_List = trans_obj.tr_view(cr, 'Shipment List', context)
            Shipments = trans_obj.tr_view(cr, 'Shipments', context)
            Shipment = trans_obj.tr_view(cr, 'Shipment', context)
            for v in values:
                if v[2].get('report_name', False) == 'packing.list' and context['_terp_view_name'] in (Packing_Lists, Packing_List) :
                    new_act.append(v)
                elif context['_terp_view_name'] in (Shipment_Lists, Shipment_List, Shipments, Shipment):
                    new_act.append(v)
                values = new_act
        elif key == 'action' and key2 == 'client_print_multi' and context.get('picking_screen') and context.get('from_so') and context.get('picking_type', False) != 'incoming_shipment':
            new_act = []
            for v in values:
                if v[2].get('report_name', False) :
                    if v[2].get('report_name', False) in ('picking.ticket', 'labels'):
                        new_act.append(v)
                values = new_act

        elif key == 'action' and key2 == 'client_print_multi' and 'composition.kit' in [x[0] for x in models]:
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
