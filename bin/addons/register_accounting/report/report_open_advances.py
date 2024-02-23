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

import time
import csv
import io
import pooler
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport

class report_open_advances(report_sxw.report_sxw):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def _enc(self, st):
        if isinstance(st, str):
            return st.encode('utf8')
        return st

    def create(self, cr, uid, ids, data, context=None):
        # Create the header
        header = [['Journal Code', 'Entry Sequence', 'Proprietary Instance', 'Reference', 'Document Date', 'Posting Date', 'Period', 'Account', 'Third Parties', 'Name', 'Booking Debit', 'Booking Credit', 'Booking Currency', 'Functional Debit', 'Functional Credit', 'Functional Currency']]

        # retrieve a big sql query with all information
        sql_open_advances = """
            SELECT DISTINCT journal.name, move.name, instance.code,
                   line.ref, line.document_date, line.date, period.name,
                   account.code || ' ' || account.name as account_name,
                   line.partner_txt, line.name,
                   line.debit_currency, line.credit_currency, booking_currency.name,
                   line.debit, line.credit, functional_currency.name
            FROM
                account_move_line line
                LEFT JOIN account_journal journal ON line.journal_id = journal.id
                LEFT JOIN account_account account ON line.account_id = account.id
                LEFT JOIN account_move move ON line.move_id = move.id
                LEFT JOIN account_period period ON line.period_id = period.id
                LEFT JOIN res_currency booking_currency ON line.currency_id = booking_currency.id
                LEFT JOIN res_company company ON line.company_id = company.id
                LEFT JOIN res_currency functional_currency ON company.currency_id = functional_currency.id
                LEFT JOIN msf_instance instance ON line.instance_id = instance.id
            WHERE
                account.type_for_register = 'advance' AND
                line.state = 'valid' AND
                line.reconcile_id IS NULL AND
                line.date <= %s
            ORDER BY account_name, booking_currency.name, line.partner_txt, line.date
        """
        cr.execute(sql_open_advances, (time.strftime('%Y-%m-%d'),))
        res = header + cr.fetchall()

        b = io.StringIO()
        writer = csv.writer(b, quoting=csv.QUOTE_ALL)
        for line in res:
            writer.writerow(list(map(self._enc,line)))
        out = b.getvalue()
        b.close()
        return (out, 'csv')

report_open_advances('report.open.advances', 'account.bank.statement', False, parser=False)

class report_open_advances2(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_open_advances2, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getLines':self.getLines,
        })

    def getLines(self,obj):
        ret = []
        obj_line = pooler.get_pool(self.cr.dbname).get('account.bank.statement.line')
        date = time.strftime('%Y-%m-%d')
        domain = [('account_id.type_for_register', '=', 'advance'),
                  ('state', 'in', ['temp', 'hard']),
                  ('reconciled', '=', False),
                  ('amount', '<=', 0.0),
                  ('date', '<=', date)]
        if obj.journal_id and obj.journal_id.currency:
            domain.append(('currency_id', '=', obj.journal_id.currency.id))
        ids = obj_line.search(self.cr, self.uid, domain, context={'check_advance_reconciled': True})
        for line in obj_line.browse(self.cr, self.uid, ids, context={'lang': self.localcontext.get('lang')}):
            ret.append(line)
        return ret

SpreadsheetReport('report.open.advances.2','account.bank.statement','addons/register_accounting/report/open_advances_xls.mako', parser=report_open_advances2)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
