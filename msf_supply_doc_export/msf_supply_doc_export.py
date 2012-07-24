# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF, Smile. All Rights Reserved
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
from report_webkit.webkit_report import WebKitParser

def getIds(self, cr, uid, ids, context):
    if not context:
        context = {}
    if context.get('from_domain') and 'search_domain' in context:
        table_obj = pooler.get_pool(cr.dbname).get(self.table)
        ids = table_obj.search(cr, uid, context.get('search_domain'), limit=5000)
    return ids

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

class ir_values(osv.osv):
    """
    we override ir.values because we need to filter where the button to print report is displayed (this was also done in register_accounting/account_bank_statement.py)
    """
    _name = 'ir.values'
    _inherit = 'ir.values'

    def get(self, cr, uid, key, key2, models, meta=False, context=None, res_id_req=False, without_user=True, key2_req=True):
        if context is None:
            context = {}
        values = super(ir_values, self).get(cr, uid, key, key2, models, meta, context, res_id_req, without_user, key2_req)
# already defined in the module tender_flow
#        if context.get('_terp_view_name') and key == 'action' and key2 == 'client_print_multi' and 'purchase.order' in [x[0] for x in models]:
#            new_act = []
#            for v in values :
#                if v[2]['name'] == 'Purchase Order Excel Export' and context['_terp_view_name'] == 'Purchase Orders' \
#                or v[2]['report_name'] == 'purchase.msf.order' and context['_terp_view_name'] == 'Purchase Orders' \
#                or v[2]['report_name'] == 'purchase.order.merged' and context['_terp_view_name'] == 'Purchase Orders' \
#                or v[2]['report_name'] == 'po.line.allocation.report' and context['_terp_view_name'] == 'Purchase Orders' \
#                or v[2]['report_name'] == 'purchase.msf.quotation' and context['_terp_view_name'] == 'Requests for Quotation' \
#                or v[2]['report_name'] == 'request.for.quotation_xls' and context['_terp_view_name'] == 'Requests for Quotation' :
#                    new_act.append(v)
#                values = new_act
        if context.get('_terp_view_name') and key == 'action' and key2 == 'client_print_multi' and 'sale.order' in [x[0] for x in models]:
            new_act = []
            for v in values:
                if v[2]['report_name'] == 'internal.request_xls' and context['_terp_view_name'] == 'Internal Requests' \
                or v[2]['report_name'] == 'msf.sale.order' and context['_terp_view_name'] == 'Field Orders' \
                or v[2]['report_name'] == 'sale.order_xls' and context['_terp_view_name'] == 'Field Orders' :
                    new_act.append(v)
                values = new_act
                
        elif context.get('_terp_view_name') and key == 'action' and key2 == 'client_print_multi' and 'stock.picking' in [x[0] for x in models]:
            new_act = []
            for v in values:
                if v[2]['report_name'] == 'picking.ticket' and context['_terp_view_name'] == 'Picking Tickets' and context.get('picking_screen', False)\
                or v[2]['report_name'] == 'pre.packing.list' and context['_terp_view_name'] == 'Pre-Packing Lists' and context.get('ppl_screen', False)\
                or v[2]['report_name'] == 'labels' and context['_terp_view_name'] in ['Picking Tickets', 'Pre-Packing Lists'] :
                    new_act.append(v)
                values = new_act
                
        elif context.get('_terp_view_name') and key == 'action' and key2 == 'client_print_multi' and 'shipment' in [x[0] for x in models]:
            new_act = []
            for v in values:

                if v[2]['report_name'] == 'packing.list' and context['_terp_view_name'] == 'Packing Lists' :
                    new_act.append(v)
                elif context['_terp_view_name'] == 'Shipment Lists':
                    new_act.append(v)
                values = new_act
        elif context.get('picking_screen') and context.get('from_so'):
            new_act = []
            for v in values:
                if v[2].get('report_name', False) :
                    if v[2]['report_name'] == 'picking.ticket':
                        new_act.append(v)
                values = new_act
        return values

ir_values()
