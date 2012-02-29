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

import datetime

from report import report_sxw
import pooler
import locale
import csv
import StringIO

class report_liquidity_position(report_sxw.report_sxw):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)
    
    
    def create(self, cr, uid, ids, data, context=None):
        pool = pooler.get_pool(cr.dbname)
        # Create the header
        data = [['Journal Code', 'Journal Name', 'Ending Balance in register currency', 'Register Currency', 'Ending Balance in functional currency', 'Functional Currency']]

        # retrieve ids of latest, non-cheque, non-draft registers
        sql_register_ids = """
            SELECT abs.id FROM account_bank_statement abs
                LEFT JOIN account_journal aj ON abs.journal_id = aj.id
            WHERE 
                aj.type != 'cheque' AND abs.state != 'draft' AND abs.id not in (
                    SELECT prev_reg_id FROM account_bank_statement WHERE prev_reg_id is not null AND state != 'draft'
                )
        """
        cr.execute(sql_register_ids)
        register_ids = [x[0] for x in cr.fetchall()]
        
        for register in pool.get('account.bank.statement').browse(cr, uid, register_ids, context=context):
            functional_currency = register.journal_id.company_id.currency_id
            date_context = {'date': datetime.datetime.today().strftime('%Y-%m-%d')}
            converted_end_balance = pool.get('res.currency').compute(cr,
                                                                     uid,
                                                                     register.journal_id.currency.id,
                                                                     functional_currency.id, 
                                                                     register.balance_end or 0.0,
                                                                     round=True,
                                                                     context=date_context)
            register_values = [[register.journal_id.code,
                                register.journal_id.name,
                                register.balance_end,
                                register.journal_id.currency.name,
                                converted_end_balance,
                                functional_currency.name]]
            data += register_values
        
        buffer = StringIO.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
        for line in data:
            writer.writerow(line)
        out = buffer.getvalue()
        buffer.close()
        return (out, 'csv')

report_liquidity_position('report.liquidity.position', 'account.bank.statement', False, parser=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
