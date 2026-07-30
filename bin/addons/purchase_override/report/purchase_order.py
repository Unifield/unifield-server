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
from osv import osv
from report import report_sxw
import pooler


def getIds(self, cr, uid, ids, context=None):
    if context is None:
        context = {}

    if context.get('from_domain') and 'search_domain' in context:
        table_obj = pooler.get_pool(cr.dbname).get(self.table)
        ids = table_obj.search(cr, uid, context.get('search_domain'), limit=5000)
    return ids


class order_parse(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(order_parse, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'to_time': self.str_to_time,
            'enumerate': enumerate,
            'getOrigin': self._get_origin,
            'filter_lines': self.filter_lines,
        })

    def filter_lines(self, o):
        if not o.order_line:
            return []

        return [x for x in o.order_line if x.state not in ('cancel', 'cancel_r')]

    def _get_origin(self, origin='', number=5):
        res = []
        if origin:
            split_orig = origin.split(';')
        else:
            split_orig = []
        i = 0
        tmp_orig = ''
        while i < len(split_orig):
            tmp_orig += split_orig[i]
            i += 1

            if i != len(split_orig):
                tmp_orig += ';'

            if i % number == 0:
                res.append(tmp_orig)
                tmp_orig = ''

        if len(split_orig) < number:
            res.append(tmp_orig)
            tmp_orig = ''

        return res

    def str_to_time(self, time):
        if isinstance(time, str):
            if time == 'False':
                time = False

        if time:
            return self.pool.get('date.tools').get_date_formatted(self.cr, self.uid, datetime=time)

        return ''


class order(report_sxw.report_sxw):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        ids = getIds(self, cr, uid, ids, context=context)
        if context is None:
            context = {}
        return super(order, self).create(cr, uid, ids, data, context=context)


order('report.msf.purchase.order', 'purchase.order', 'addons/purchase_override/report/purchase_order.rml', parser=order_parse, header=False)


class wizard_purchase_order_export(osv.osv_memory):
    _name = 'wizard.purchase.order.export'

    def print_report_pdf(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        po_ids = context.get('active_ids', [])
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'msf.purchase.order',
            'datas': {'ids': po_ids},
            'context': context,
        }


wizard_purchase_order_export()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
