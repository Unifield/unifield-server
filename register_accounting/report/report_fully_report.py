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
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
import pooler

class report_fully_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_fully_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getMoveLines': self.getMoveLines,
            'getAnalyticLines': self.getAnalyticLines,
        })
        return

    def getMoveLines(self, move_ids, regline_br):
        """
        Fetch all lines except the partner counterpart one
        """
        res = []
        if not move_ids:
            return res
        if isinstance(move_ids, (int, long)):
            move_ids = [move_ids]
        
        # US-69
        # - at JI level exclude the detail display of HR journal JIs/AJIs
        # (detail for payroll entries not wished (no JI AND AJI display))
        # - same process for register lines of account tax (imported from SI)
        # => as we not display JIs, related AJIs will not be displayed too
        
        # 1) exclude register line of account of given user_type
        excluded_regline_acc_type_codes = ['tax', 'cash', 'receivables', ]
        aat_obj = pooler.get_pool(self.cr.dbname).get('account.account.type')
        domain = [('code', 'in', excluded_regline_acc_type_codes)]
        excluded_regline_acc_type_ids = aat_obj.search(self.cr, self.uid,
            domain)
        if regline_br and regline_br.account_id and \
            regline_br.account_id.user_type and \
            regline_br.account_id.user_type.id in excluded_regline_acc_type_ids:
            return []
        
        # 2) get journals to exclude
        journal_obj = pooler.get_pool(self.cr.dbname).get('account.journal')
        domain = [('type', '=', 'hr')]
        excluded_journal_ids = journal_obj.search(self.cr, self.uid, domain)
        
        # 3) get JIs ids filtered by excluded journal
        am_obj = pooler.get_pool(self.cr.dbname).get('account.move')
        domain = [
            ('journal_id', 'not in', excluded_journal_ids),
            ('id', 'in', move_ids),
        ]
        move_ids = am_obj.search(self.cr, self.uid, domain)
        if not move_ids:
            return []
        
        # 4) We need move lines linked to the given move ID. Except the invoice counterpart.
        #+ Lines that have is_counterpart to True is the invoice counterpart. We do not need it.
        aml_obj = pooler.get_pool(self.cr.dbname).get('account.move.line')
        domain = [
            ('move_id', 'in', move_ids),
            ('is_counterpart', '=', False)
        ]
        aml_ids = aml_obj.search(self.cr, self.uid, domain)
        if aml_ids:
            res = aml_obj.browse(self.cr, self.uid, aml_ids)
            
        return sorted(res, key=lambda x: x.line_number)

    def getAnalyticLines(self, analytic_ids):
        """
        Get anlytic lines history from given analytic lines
        """
        res = []
        if not analytic_ids:
            return res
        if isinstance(analytic_ids, (int, long)):
            analytic_ids = [analytic_ids]
        al_obj = pooler.get_pool(self.cr.dbname).get('account.analytic.line')
        al_ids = al_obj.get_corrections_history(self.cr, self.uid, analytic_ids)
        if al_ids:
            res = al_obj.browse(self.cr, self.uid, al_ids)
        return res

SpreadsheetReport('report.fully.report','account.bank.statement','addons/register_accounting/report/fully_report_xls.mako', parser=report_fully_report)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
