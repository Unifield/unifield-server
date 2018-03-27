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

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class combined_journals_report(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(combined_journals_report, self).__init__(cr, uid, name, context=context)
        self.selector_id = False
        self.localcontext.update({
            'lines': self._get_lines,
        })

    def _get_lines(self):
        """
        Returns a list of dicts... (TODO)
        """
        res = []
        return res

    def set_context(self, objects, data, ids, report_type=None):
        self.context = data.get('context', {})
        self.selector_id = data.get('selector_id', False)
        return super(combined_journals_report, self).set_context(objects, data, ids, report_type)


SpreadsheetReport('report.combined.journals.report.xls', 'account.mcdb',
                  'addons/account_mcdb/report/combined_journals_report.mako', parser=combined_journals_report)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
