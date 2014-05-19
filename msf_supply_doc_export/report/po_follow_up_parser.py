#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
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
import pooler
import csv
from report_webkit.webkit_report import WebKitParser
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
import zipfile
import tempfile
import os

limit_tozip = 15000

def getIds(self, cr, uid, ids, limit=5000, context=None):
    if not context:
        context = {}
    if context.get('from_domain') and 'search_domain' in context and not context.get('export_selected'):
        table_obj = pooler.get_pool(cr.dbname).get(self.table)
        ids = table_obj.search(cr, uid, context.get('search_domain'), limit=limit)
    return ids

def getObjects(self, cr, uid, ids, context):
    ids = getIds(self, cr, uid, ids, context)
    return super(self.__class__, self).getObjects(cr, uid, ids, context)

def getIterObjects(self, cr, uid, ids, context):
    if context is None:
        context = {}
    ids = getIds(self, cr, uid, ids, limit=65000, context=context)
    len_ids = len(ids)
    l = 0
    steps = 1000
    pool =  pooler.get_pool(cr.dbname)
    table_obj = pool.get(self.table)
    field_process = None
    back_browse = False
    if context.get('background_id'):
         back_browse = self.pool.get('memory.background.report').browse(cr, uid, context['background_id'])

    if hasattr(self, '_fields_process'):
        field_process = self._fields_process
    # we need to sort analytic line by account code
    if context.get('sort_by_account_code') and len_ids > 1:
        cr.execute('select an.id from account_analytic_line an left join account_analytic_account a on an.account_id = a.id where an.id in %s order by a.code', (tuple(ids), ))
        ids = []
        for i in cr.fetchall():
            ids.append(i[0])

    while l < len_ids:
        if back_browse:
            back_browse.update_percent(l/float(len_ids))
        old_l = l
        l = l + steps
        new_ids = ids[old_l:l]
        if new_ids:
            for o in table_obj.browse(cr, uid, new_ids, list_class=report_sxw.browse_record_list, context=context, fields_process=field_process):
                yield o
    raise StopIteration


class parser_account_move_line(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(parser_account_move_line, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            #'reconcile_name': self.reconcile_name,
            #'getSub': self.getSub,
        })



    def reconcile_name(self, r_id=None, context=None):
        if not r_id:
            return None
        res = self.pool.get('account.move.reconcile').name_get(self.cr, self.uid, [r_id])
        if res and res[0] and res[0][1]:
            return res[0][1]
        return None

po_follow_up_xls('po.follow.up_xls','purchase.order','unifield-wm/msf_supply_doc_export/report/report_po_follow_up_xls.mako', parser=parser_po_follow_up)



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
