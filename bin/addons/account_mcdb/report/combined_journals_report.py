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
from osv import osv
from tools.translate import _


class combined_journals_report(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(combined_journals_report, self).__init__(cr, uid, name, context=context)
        self.context = {}
        self.selector_id = False
        self.aml_domain = []
        self.aal_domain = []
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
        """
        Gets the domains to take into account for JIs and AJIs and stores them in self.aml_domain and self.aal_domain
        """
        selector_obj = self.pool.get('account.mcdb')
        self.context = data.get('context', {})
        self.selector_id = data.get('selector_id', False)
        if not self.selector_id:
            raise osv.except_osv(_('Warning'), _('Selector not found.'))
        # get the domain for the Journal Items
        aml_context = self.context.copy()
        aml_context.update({'selector_model': 'account.move.line'})  # Analytic axis will be excluded
        self.aml_domain = selector_obj._get_domain(self.cr, self.uid, self.selector_id, context=aml_context)
        # get the domain for the Analytic Journal Items
        aal_context = self.context.copy()
        aal_context.update({'selector_model': 'account.analytic.line'})
        aal_domain = selector_obj._get_domain(self.cr, self.uid, self.selector_id, context=aal_context)
        # exclude G/L journals and Entry Status
        for t in aal_domain:
            if t[0] not in ('journal_id', 'move_id.state'):
                self.aal_domain.append(t)
        # only take into account AJIs which are NOT linked to a JIs
        self.aal_domain.append(('move_id', '=', False))
        return super(combined_journals_report, self).set_context(objects, data, ids, report_type)


SpreadsheetReport('report.combined.journals.report.xls', 'account.mcdb',
                  'addons/account_mcdb/report/combined_journals_report.mako', parser=combined_journals_report)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
