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

from report import report_sxw
import pooler
import locale
import csv
import StringIO

class report_cheque_inventory(report_sxw.report_sxw):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def translate_state(self, cr, line):
        # Parse each budget line
        pool = pooler.get_pool(cr.dbname)
        register_states = dict(pool.get('account.bank.statement')._columns['state'].selection)
        if len(line) > 2 and line[2] in register_states:
            return list(line[:2]) + [register_states[line[2]]] + list(line[3:])
        else:
            return line

    def create(self, cr, uid, ids, data, context=None):
        # Create the header
        header = [['Register Name', 'Register Period', 'Register State', 'Document Date', 'Posting Date', 'Cheque Number', 'Sequence', 'Description', 'Reference', 'Account', 'Third Parties', 'Amount Out', 'Currency']]
        
        # retrieve a big sql query with all information
        sql_posted_moves = """
            SELECT DISTINCT abs.name, ap.name, abs.state,
                   st.document_date, st.date, st.cheque_number,
                   st.sequence_for_reference, st.name, st.ref,
                   ac.code || ' ' || ac.name as account_name,
                   COALESCE(tprp.name,tphe.name,tpabs.name,tpaj.name) as third_party,
                   -st.amount as amount_out, rc.name as currency FROM 
                account_bank_statement_line st
                LEFT JOIN account_bank_statement abs ON abs.id = st.statement_id
                LEFT JOIN account_bank_statement_line_move_rel rel ON rel.move_id = st.id
                LEFT JOIN account_move move ON rel.statement_id = move.id
                LEFT JOIN account_move_line line ON line.move_id = move.id
                LEFT JOIN account_account ac ON ac.id = line.account_id
                LEFT JOIN account_journal aj ON abs.journal_id = aj.id
                LEFT JOIN account_period ap ON abs.period_id = ap.id
                LEFT JOIN res_partner tprp ON st.partner_id = tprp.id
                LEFT JOIN hr_employee tphe ON st.employee_id = tphe.id
                LEFT JOIN res_currency rc ON aj.currency = rc.id
                LEFT JOIN account_bank_statement tpabs ON st.register_id = tpabs.id
                LEFT JOIN account_journal tpaj ON st.transfer_journal_id = tpaj.id
            WHERE 
                aj.type = 'cheque' AND st.amount < 0.0 AND
                rel.move_id is not null AND (move.state != 'posted' OR (line.reconcile_id IS NULL AND ac.reconcile='t'))
            ORDER BY st.date
        """
        cr.execute(sql_posted_moves)
        res = header + map((lambda x: self.translate_state(cr, x)), cr.fetchall())
        
        buffer = StringIO.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
        for line in res:
            writer.writerow(line)
        out = buffer.getvalue()    
        buffer.close()
        return (out, 'csv')

report_cheque_inventory('report.cheque.inventory', 'account.bank.statement', False, parser=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
