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

import time

from osv import osv
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.misc import Path
from tools.translate import _
import os
from mission_stock import mission_stock
import pooler
import base64


class stock_mission_report_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(stock_mission_report_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time
        })


class stock_mission_report_xls_parser(SpreadsheetReport):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(stock_mission_report_xls_parser, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):

        report_id = data.get('report_id', None)
        field_name = data.get('field_name', '')
        file_format = data.get('file_format', '')
        display_only_in_stock = data.get('display_only_in_stock', False)
        if display_only_in_stock:
            field_name += '_only_stock'
        file_name = mission_stock.STOCK_MISSION_REPORT_NAME_PATTERN % (report_id, field_name + '.%s' % file_format)


        # get the attachment_path
        pool = pooler.get_pool(cr.dbname)
        attachment_obj = pool.get('ir.attachment')
        attachments_path = attachment_obj.get_root_path(cr, uid, check=False)

        store_in_db = attachment_obj.store_data_in_db(cr, uid,
                                                      ignore_migration=True)

        create_missing_report = False
        if data.get('file_name') and data['file_name'] == 'consolidate_mission_stock.xls':
            file_name = 'consolidate_mission_stock.xls'
        if store_in_db:
            attachment_ids = attachment_obj.search(cr, uid, [('datas_fname', '=', file_name)], context=context)
            if not attachment_ids:
                create_missing_report = True
        else:
            path = os.path.join(attachments_path, file_name)
            if not os.path.exists(path):
                create_missing_report = True
        if create_missing_report and file_name != 'consolidate_mission_stock.xls':
            # if the requested attachment doesn't exist, create it
            msr_obj = pool.get('stock.mission.report')
            with_valuation = False
            if field_name.startswith('s_v_vals'):
                with_valuation = True

            msr_obj._get_export(cr, uid, report_id, {},
                                csv=file_format=='csv', xls=file_format=='xls',
                                with_valuation=with_valuation,
                                all_products=not display_only_in_stock,
                                display_only_in_stock=display_only_in_stock,
                                context=context)

        if store_in_db:
            # then get the attachment in the old way : in the database
            attachment_ids = attachment_obj.search(cr, uid, [('datas_fname', '=', file_name)],
                                                   context=context)
            if not attachment_ids or not attachment_obj.read(cr, uid, attachment_ids[0], ['datas'])['datas']:
                raise osv.except_osv(_('Error'),
                                     _("attachments_path %s doesn't exists and the report "\
                                       "has not been found in the database. Please check "\
                                       "the attachments configuration or update the MSR.") % attachments_path)
            datas = attachment_obj.read(cr, uid, attachment_ids[0], ['datas'])['datas']
            return (base64.b64decode(datas), file_format)
        else:
            path = os.path.join(attachments_path, file_name)
            if os.path.exists(path):
                return (Path(path, delete=False), file_format)
            else:
                raise osv.except_osv(_('Error'),
                                     _("File %s not found.\nMay be you need to update the Mission Stock Report data.") % path)

stock_mission_report_xls_parser(
    'report.stock.mission.report_xls',
    'mission.stock.wizard',
    'mission_stock/report/stock_mission_report_xls.mako',
    parser=stock_mission_report_parser,
    header='internal',
)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
