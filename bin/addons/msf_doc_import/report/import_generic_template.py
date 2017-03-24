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

from report_webkit.webkit_report import XlsWebKitParser

XlsWebKitParser(
    'report.wizard.import.generic.template',
    'abstract.wizard.import',
    'addons/msf_doc_import/report/import_generic_template.mako',
)

XlsWebKitParser(
    'report.wizard.export.generic',
    'msf.import.export',
    'addons/msf_doc_import/report/export_generic.mako',
)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
