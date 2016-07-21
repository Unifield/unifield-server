# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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
from report_webkit.webkit_report import XlsWebKitParser
from ..wizard.wizard_import_batch import IMPORT_BATCH_HEADERS


class import_batch_template_parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(import_batch_template_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'header_columns': IMPORT_BATCH_HEADERS,
        })

XlsWebKitParser(
    'report.wizard.import.batch.template',
    'wizard.import.batch',
    'addons/msf_doc_import/report/import_batch_template.mako',
    parser=import_batch_template_parser)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
