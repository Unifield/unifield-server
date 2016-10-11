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
import tools
from tools.translate import _
import os
from mission_stock import mission_stock
import pooler


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

        # get the attachment_path
        pool = pooler.get_pool(cr.dbname)
        res = pool.get('ir.model.data').get_object_reference(cr, uid,
                'base_setup', 'attachment_config_default')
        attachments_path = pool.get(res[0]).read(cr, uid, res[1],
                ['name'])['name']

        # check attachments_path
        if not attachments_path or not os.path.exists(attachments_path):
            raise osv.except_osv(_('Error'), _("attachments_path %s doesn't exists.") % attachments_path)

        report_id = data.get('report_id', None)
        field_name = data.get('field_name', '')
        file_format = data.get('file_format', '')
        file_name = mission_stock.STOCK_MISSION_REPORT_NAME_PATTERN % (report_id, field_name + '.%s' % file_format)
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
