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

class report_pending_cheque(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_pending_cheque, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getLines':self.getLines,
        })
        return

    def getLines(self, register):
        if not register:
            return []
        # Prepare some values
        journal = register.journal_id
        account_ids = [journal.default_debit_account_id.id, journal.default_credit_account_id.id]
        import pooler
        pool = pooler.get_pool(self.cr.dbname)
        aml_obj = pool.get('account.move.line')

        # Search for all registers with the same Journal, and the same period or a previous period
        period_ids = self.pool.get('account.period').\
            search(self.cr, self.uid, [('date_start', '<=', register.period_id.date_start)])
        registers_ids = self.pool.get('account.bank.statement').\
            search(self.cr, self.uid, ['&', ('journal_id', '=', journal.id), ('period_id', 'in', period_ids)])

        # Search register lines
        aml_ids = aml_obj.search(self.cr, self.uid, [('statement_id', 'in', registers_ids), ('is_reconciled', '=', False), ('account_id', 'in', account_ids),], order='date DESC')
        if isinstance(aml_ids, (int, long)):
            aml_ids = [aml_ids]
        return aml_obj.browse(self.cr, self.uid, aml_ids)

SpreadsheetReport('report.pending.cheque','account.bank.statement','addons/register_accounting/report/pending_cheque_xls.mako', parser=report_pending_cheque)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
