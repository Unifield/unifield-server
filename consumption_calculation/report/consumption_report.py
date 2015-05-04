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
from osv import osv
from report_webkit.webkit_report import WebKitParser
from tools.translate import _

import pooler


def getIds(self, cr, uid, ids, context):
    if not context:
        context = {}
    if context.get('from_domain') and 'search_domain' in context:
        table_obj = pooler.get_pool(cr.dbname).get(self.table)
        ids = table_obj.search(cr, uid, context.get('search_domain'), limit=5000)
    return ids


class real_consumption_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header = " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(real_consumption_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(real_consumption_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

real_consumption_xls('report.real.consumption.xls', 'real.average.consumption', 'addons/consumption_calculation/report/report_real_consumption_xls.mako')
real_consumption_xls('report.incoming.consumption.xls', 'stock.picking', 'addons/consumption_calculation/report/report_incoming_consumption_xls.mako')


class monthly_consumption_xls(WebKitParser):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        report_xml.webkit_debug = 1
        report_xml.header = " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(monthly_consumption_xls, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context)
        a = super(monthly_consumption_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')
monthly_consumption_xls('report.monthly.consumption.xls', 'monthly.review.consumption', 'addons/consumption_calculation/report/report_monthly_consumption_xls.mako')


class wizard_incoming_xml_export(osv.osv_memory):
    _name = 'wizard.incoming.xml.export'

    def print_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        incoming_ids = context.get('active_ids', [])

        not_done = self.pool.get('stock.picking').search(cr, uid, [
            ('id', 'in', incoming_ids),
            ('state', '!=', 'done'),
        ], context=context)

        if not_done:
            raise osv.except_osv(
                _('Error'),
                _('The XML Export is only available for Closed Incoming Shipment'),
            )

        datas = {'ids':incoming_ids}

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'incoming.consumption.xls',
            'datas': datas,
            'context': context,
        }

wizard_incoming_xml_export()
