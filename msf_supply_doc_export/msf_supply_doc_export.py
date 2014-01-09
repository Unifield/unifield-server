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
from report_webkit.webkit_report import WebKitParser
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _

import pooler

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

# VALIDATED PURCHASE ORDER (Excel XML)
class validated_purchase_order_report_xls(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(validated_purchase_order_report_xls, self).__init__(cr, uid, name, context=context)

SpreadsheetReport('report.validated.purchase.order_xls', 'purchase.order', 'addons/msf_supply_doc_export/report/report_validated_purchase_order_xls.mako', parser=validated_purchase_order_report_xls)

# VALIDATE PURCHASE ORDER (Pure XML)
class parser_validated_purchase_order_report_xml(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(parser_validated_purchase_order_report_xml, self).__init__(cr, uid, name, context=context)

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
        trans_obj = self.pool.get('ir.translation')
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
        
        Internal_Requests = trans_obj.tr_view(cr, 'Internal Requests', context)
        Field_Orders = trans_obj.tr_view(cr, 'Sales Orders', context)
        if key == 'action' and key2 == 'client_print_multi' and 'sale.order' in [x[0] for x in models]:
            new_act = []
            #field_orders_view = data_obj.get_object_reference(cr, uid, 'procurement_request', 'action_procurement_request')[1]
            for v in values:
                if context.get('procurement_request', False):
                    if v[2]['report_name'] in ('internal.request_xls', 'procurement.request.report') \
                    or v[1] == 'action_open_wizard_import': # this is an internal request, we only display import lines for client_action_multi --- using the name of screen, and the name of the action is definitely the wrong way to go...
                        new_act.append(v)
                else:
                    if v[2]['report_name'] == 'msf.sale.order' \
                    or v[2]['report_name'] == 'sale.order_xls' \
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
                if v[2]['report_name'] == 'picking.ticket' and (context.get('_terp_view_name') in (Picking_Tickets, Picking_Ticket) or context.get('picking_type') == 'picking_ticket') and context.get('picking_screen', False)\
                or v[2]['report_name'] == 'pre.packing.list' and context.get('_terp_view_name') in (Pre_Packing_Lists, Pre_Packing_List) and context.get('ppl_screen', False)\
                or v[2]['report_name'] == 'labels' and (context.get('_terp_view_name') in [Picking_Ticket, Picking_Tickets, Pre_Packing_List, Pre_Packing_Lists, Delivery_Orders, Delivery_Order] or context.get('picking_type', False) in ('delivery_order', 'picking_ticket'))\
                or v[2]['report_name'] in ('internal.move.xls', 'internal.move') and (('_terp_view_name' in context and context['_terp_view_name'] in [Internal_Moves]) or context.get('picking_type') == 'internal_move') \
                or v[2]['report_name'] == 'delivery.order' and (context.get('_terp_view_name') in [Delivery_Orders, Delivery_Order] or context.get('picking_type', False) == 'delivery_order'):
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
                if v[2]['report_name'] == 'packing.list' and context['_terp_view_name'] in (Packing_Lists, Packing_List) :
                    new_act.append(v)
                elif context['_terp_view_name'] in (Shipment_Lists, Shipment_List, Shipments, Shipment):
                    new_act.append(v)
                values = new_act
        elif context.get('picking_screen') and context.get('from_so') and context.get('picking_type', False) != 'incoming_shipment':
            new_act = []
            for v in values:
                if v[2].get('report_name', False) :
                    if v[2]['report_name'] in ('picking.ticket', 'labels'):
                        new_act.append(v)
                values = new_act

        elif key == 'action' and key2 == 'client_print_multi' and 'composition.kit' in [x[0] for x in models]:
            new_act = []
            for v in values:
                if context.get('composition_type')=='theoretical' and v[2]['report_name'] in ('composition.kit.xls', 'kit.report'):
                    if v[2]['report_name'] == 'kit.report':
                        v[2]['name'] = _('Theoretical Kit')
                    new_act.append(v)
                elif context.get('composition_type')=='real' and v[2]['report_name'] in ('real.composition.kit.xls', 'kit.report'):
                    if v[2]['report_name'] == 'kit.report':
                        v[2]['name'] = _('Kit Composition')
                    new_act.append(v)
            values = new_act

        return values

ir_values()
