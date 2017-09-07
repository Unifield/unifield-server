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

class report_cheque_inventory(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_cheque_inventory, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getLines': self.getLines,
        })
        return

    def _keep_register_line(self, cr, uid, acc_bank_statement_line, min_posting_date, context=None):
        """
        Checks the move lines linked to the acc_bank_statement_line in parameter, and returns True if one of them is:
        - either reconciled partially or totally with at least one reconciliation leg having a posting date later than
          the min_posting_date in parameter
        - or not reconciled (but reconcilable)
        """
        if context is None:
            context = {}
        aml_obj = self.pool.get('account.move.line')
        if acc_bank_statement_line.move_ids and acc_bank_statement_line.state == 'hard':
            for move in acc_bank_statement_line.move_ids:
                for move_line in move.line_id:
                    if move_line.account_id.reconcile:
                        total_rec_ok = move_line.reconcile_id and \
                            aml_obj.search_exist(cr, uid,
                                                 [('reconcile_id', '=', move_line.reconcile_id.id),
                                                  ('date', '>', min_posting_date)], context=context)
                        partial_rec_ok = move_line.reconcile_partial_id and \
                            aml_obj.search_exist(cr, uid,
                                                 [('reconcile_partial_id', '=', move_line.reconcile_partial_id.id),
                                                  ('date', '>', min_posting_date)], context=context)
                        if not move_line.is_reconciled or total_rec_ok or partial_rec_ok:
                            return True
        return False

    def getLines(self, statement):
        """
        Return list of lines from given register and previous ones that are either not reconciled, or reconciled partially
        or totally with at least one reconciliation leg having a posting date belonging to a later period than the register one
        """
        # Prepare some values
        res = []
        absl_obj = self.pool.get('account.bank.statement.line')
        period_obj = self.pool.get('account.period')
        # Fetch all previous registers linked to this one
        prev_reg_ids = [statement.id]
        if statement.prev_reg_id:
            prev_reg_ids.append(statement.prev_reg_id.id)
            prev_reg_id = statement.prev_reg_id
            while prev_reg_id != False:
                prev_reg_id = prev_reg_id.prev_reg_id or False
                if prev_reg_id:
                    prev_reg_ids.append(prev_reg_id.id)
        absl_ids = absl_obj.search(self.cr, self.uid, [('statement_id', 'in', prev_reg_ids)])
        period_r = period_obj.read(self.cr, self.uid, statement.period_id.id,
                                   ['date_stop'])  # used not to format the date in the user language
        absl_ids_to_keep = []
        for absl in absl_obj.browse(self.cr, self.uid, absl_ids, fields_to_fetch=['move_ids', 'state']):
            if self._keep_register_line(self.cr, self.uid, absl, period_r['date_stop']):
                absl_ids_to_keep.append(absl.id)
        if absl_ids_to_keep:
            res = absl_obj.browse(self.cr, self.uid, absl_ids_to_keep)
        return res

SpreadsheetReport('report.cheque.inventory.2','account.bank.statement','addons/register_accounting/report/cheque_inventory_xls.mako', parser=report_cheque_inventory)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
