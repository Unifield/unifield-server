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


from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class kit_mass_import_export(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(kit_mass_import_export, self).__init__(cr, uid, name, context=context)
        self.cr = cr
        self.uid = uid
        self.localcontext.update({
        })


class kit_mass_import_export_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse,
                 header='external', store=False):
        super(kit_mass_import_export_xls, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(kit_mass_import_export_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')


kit_mass_import_export_xls(
    'report.kit_mass_import_export',
    'kit.mass.import',
    'addons/kit/report/kit_mass_import_export_xls.mako',
    parser=kit_mass_import_export,
    header=False)
